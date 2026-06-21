import os
import pymysql  # 引入用于连接数据库的库
from flask import Flask, request, jsonify
from ultralytics import YOLO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =======================================================
# 1. 自动定位并加载垃圾分类模型（已针对 Render CPU 服务器与根目录优化）
# =======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 🔥 直接从根目录读取 best.pt（不再去寻找不存在的 models 文件夹）
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')

print(f"🔄 Loading YOLOv8 model from: {MODEL_PATH}")
model = YOLO(MODEL_PATH)
model.to('cpu')  # 🔥 强制模型运行在 CPU 设备上，解决 CUDA 序列化报错
print("✅ Model loaded successfully on CPU.")


# 🔥 核心修正：完美对接你的 Awardspace 远程云端 MySQL 数据库配置
def get_db_connection():
    return pymysql.connect(
        host="fdb1030.awardspace.net",      # 👈 Awardspace 提供的 MySQL Host
        user="4574972_wastescanaidb",       # 👈 Awardspace 提供的 Database User
        password="0qm+.9i41TLk5yth",        # 👈 🔥 已经替换为你刚拿到的真实数据库密码
        database="4574972_wastescanaidb",   # 👈 Awardspace 提供的 Database Name
        port=3306,                         # 👈 指定标准 MySQL 端口
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


# =======================================================
# 2. AI 预测扫描 ➔ 仅更新垃圾桶状态（不再干扰历史总表）
# =======================================================
@app.route('/predict', methods=['POST'])
def predict():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file uploaded"}), 400
        
    file = request.files['image']
    
    upload_dir = os.path.join(BASE_DIR, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    img_path = os.path.join(upload_dir, file.filename)
    file.save(img_path)
    
    try:
        # workers=0 适合轻量级云服务器环境
        results = model.predict(source=img_path, conf=0.35, workers=0, device='cpu')
        best_detection = None
        highest_conf = 0.0
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf_score = float(box.conf[0])
                    
                    if conf_score > highest_conf:
                        highest_conf = conf_score
                        coords = box.xyxyn[0].tolist()
                        x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
                        
                        class_id = int(box.cls[0])
                        class_name = model.names[class_id]  # aluminium, paper, plastic

                        top_pct = y1 * 100
                        left_pct = x1 * 100
                        height_pct = (y2 - y1) * 100
                        width_pct = (x2 - x1) * 100

                        best_detection = {
                            "class_name": class_name,
                            "box_css": [top_pct, left_pct, height_pct, width_pct]
                        }
        
        if best_detection:
            final_result = best_detection["class_name"]
            final_box = best_detection["box_css"]
            
            db = None
            try:
                db = get_db_connection()
                with db.cursor() as cursor:
                    # 💡 核心逻辑：不向 waste_records 写入数据，全权交由 PHP 接管历史总表。
                    
                    # 🌟 动作 B 保留：驱动前端仪表盘饼图与容量实时暴涨
                    sql_update_bin = """
                        UPDATE recycle_bins 
                        SET current_volume = LEAST(current_volume + 5, 100),
                            status = CASE WHEN current_volume + 5 >= 95 THEN 'Full' ELSE status END
                        WHERE LOWER(bin_name) = LOWER(%s)
                    """
                    cursor.execute(sql_update_bin, (final_result,))
                db.commit()
                print(f"✅ [MySQL] Bin storage capacity synchronized successfully for: {final_result}")
            except Exception as db_err:
                print(f"❌ [MySQL Error] Prediction database synch failed: {db_err}")
            finally:
                if db: db.close()
                
        else:
            final_result = "unknown"
            final_box = [15, 15, 70, 70] 
        
        return jsonify({
            "status": "success",
            "prediction": final_result,
            "box": final_box  
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =======================================================
# 3. 保持原样：处理旧逻辑的兼容接口
# =======================================================
@app.route('/api/request_pickup', methods=['POST'])
def request_pickup():
    db = None
    try:
        data = request.get_json()
        bin_type = data.get('bin_type')
        db_bin_name = bin_type.lower()
        
        db = get_db_connection()
        with db.cursor() as cursor:
            sql = "UPDATE recycle_bins SET status = 'Dispatched' WHERE LOWER(bin_name) = %s"
            cursor.execute(sql, (db_bin_name,))
        db.commit()
        
        print(f"🔥 [MySQL] Successfully set {bin_type} status to 'Dispatched' in database.")
        return jsonify({"success": True, "message": f"{bin_type} Bin state已成功流转为派单状态！"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: db.close()


# =======================================================
# 4. 核心联动：前端点击 Cleared 按钮后直接请求这个接口清空容量
# =======================================================
@app.route('/api/reset_bin', methods=['POST'])
def reset_bin():
    db = None
    try:
        data = request.get_json()
        bin_type = data.get('bin_type')
        db_bin_name = bin_type.lower()
        
        db = get_db_connection()
        with db.cursor() as cursor:
            sql = "UPDATE recycle_bins SET current_volume = 0, status = 'Normal' WHERE LOWER(bin_name) = %s"
            cursor.execute(sql, (db_bin_name,))
        db.commit()
        
        print(f"🔄 [MySQL] Successfully reset {bin_type} Bin data back to 0% and 'Normal' status.")
        return jsonify({"success": True, "message": f"{bin_type} Bin reset success."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: db.close()


# =======================================================
# 5. 自动化及云端 service 发布配置（自适应 Render 端口映射）
# =======================================================
if __name__ == '__main__':
    # 动态读取云服务器分配的 PORT 环境变量，如果读取不到（比如本地运行），则默认使用 5001 端口
    port = int(os.environ.get('PORT', 5001))
    
    print("🚀 WasteScan Core AI Server (Production Mode) is initializing...")
    print(f"📍 Application is going to listen on port: {port}")
    
    # 允许所有网络接口(0.0.0.0)访问，以便云平台转发可以畅通访问
    app.run(host='0.0.0.0', port=port, debug=False)
