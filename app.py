import os
from flask import Flask, request, jsonify
from ultralytics import YOLO
from flask_cors import CORS
import pymysql  
import cv2       
import numpy as np 

app = Flask(__name__)
CORS(app)

# =======================================================
# 1. 自动定位并配置垃圾分类模型（延迟加载）
# =======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')  

# 🌟 核心修复：声明全局模型缓存变量，不再在启动时硬加载，防止内存瞬间卡死
model = None

# 🌟 核心升级：连通 Railway 云端 MySQL 数据库
# 优先读取 Railway 生产环境变量，若本地测试则回退到默认凭证
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST", "mysql.railway.internal"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", "root"),
        database=os.getenv("MYSQLDATABASE", "railway"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )


def letterbox_resize(img_path, target_size=(640, 640)):
    """
    🆕 核心解决方案：保持宽高比等比例缩放图片，并用黑色填充到指定的 640x640 分辨率。
    此举能有效解决因图像尺寸不规整、比例失调带来的 YOLOv8 目标检测失败（Detection Failures）挑战。
    """
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"无法读取图片文件: {img_path}")

    h, w = img.shape[:2]
    th, tw = target_size

    # 计算自适应最佳缩放比例
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)

    # 等比例缩放图像
    img_resized = cv2.resize(img, (nw, nh))

    # 创建一个 640x640 的纯黑画布
    background = np.zeros((th, tw, 3), dtype=np.uint8)

    # 将缩放后的图像居中粘贴至黑色画布上，防止图像拉伸变形导致特征丢失
    dx = (tw - nw) // 2
    dy = (th - nh) // 2
    background[dy:dy+nh, dx:dx+nw] = img_resized

    # 覆盖保存为符合 640x640 标准分辨率的预处理图像
    cv2.imwrite(img_path, background)


# =======================================================
# 2. AI 预测扫描 ➔ 同步更新垃圾桶容量并生成历史记录
# =======================================================
@app.route('/predict', methods=['POST'])
def predict():
    global model  # 引用全局模型缓存
    
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file uploaded"}), 400
        
    file = request.files['image']
    
    # 🌟 修正：将 'uploads' 改为 'upload'，与本地目录及 .gitignore 保持严格一致
    upload_dir = os.path.join(BASE_DIR, 'upload')
    os.makedirs(upload_dir, exist_ok=True)
    img_path = os.path.join(upload_dir, file.filename)
    file.save(img_path)
    
    # =======================================================
    # 🌟 核心突破注入：当有请求进来时，才在内网初次延迟激活 YOLO 模型
    # =======================================================
    if model is None:
        print("⚙️ [AI Engine] Detected first request. Loading YOLOv8 weights into RAM...")
        try:
            model = YOLO(MODEL_PATH)
            print("🎯 [AI Engine] Model successfully weights loaded and cached!")
        except Exception as load_err:
            print(f"❌ [AI Engine Error] Lazy loading weights failed: {load_err}")
            return jsonify({"status": "error", "message": f"Model initialization error: {load_err}"}), 500
    # =======================================================
    
    # =======================================================
    # 执行 640 x 640 图像预处理与尺寸调整
    # =======================================================
    try:
        letterbox_resize(img_path, target_size=(640, 640))
        print(f"⚙️ [Preprocessing] Image successfully optimized and resized to 640x640: {file.filename}")
    except Exception as prep_err:
        print(f"⚠️ [Preprocessing Warning] Letterbox resize failed: {prep_err}")
    
    try:
        # 此时传入的图片已完美调整为标准 640x640 分辨率
        results = model.predict(source=img_path, conf=0.35, workers=0)
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
            
            db = None  # 在此处初始化，防止未定义数据库连接时触发 finally 报错
            try:
                db = get_db_connection()
                with db.cursor() as cursor:
                    # 动作 A：向历史大表实时写入扫描记录
                    sql_insert_record = """
                        INSERT INTO waste_records (username, record_type, material_type, image_path)
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert_record, ('Guest', 'AI_Scan', final_result, f"upload/{file.filename}"))

                    # 动作 B：用于驱动前端仪表盘饼图实时暴涨
                    sql_update_bin = """
                        UPDATE recycle_bins 
                        SET current_volume = LEAST(current_volume + 5, 100),
                            status = CASE WHEN current_volume + 5 >= 95 THEN 'Full' ELSE status END
                        WHERE LOWER(bin_name) = LOWER(%s)
                    """
                    cursor.execute(sql_update_bin, (final_result,))
                db.commit()
                print(f"✅ [MySQL] Record saved and bin storage capacity synchronized for: {final_result}")
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
# 3. 核心联动：提供数据拉取接口供前端可视化大屏和表格渲染
# =======================================================
@app.route('/api/dashboard_data', methods=['GET'])
def get_dashboard_data():
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 1. 查询所有垃圾桶当前的剩余容量与实时状态
            cursor.execute("SELECT bin_name, current_volume, max_capacity, status, last_updated FROM recycle_bins;")
            bins = cursor.fetchall()
            
            # 2. 查询最近 10 条垃圾扫描历史记录用来填满前端的表格
            cursor.execute("SELECT id, username, record_type, material_type, image_path, created_at FROM waste_records ORDER BY created_at DESC LIMIT 10;")
            records = cursor.fetchall()
            
        return jsonify({
            "success": True,
            "bins": bins,
            "recent_records": records
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: db.close()


# =======================================================
# 4. 保持原样：处理旧逻辑的兼容接口
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
# 5. 核心联动：前端点击 Cleared 按钮后直接请求这个接口清空容量
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
# 6. 自动化及外网服务发布配置
# =======================================================
if __name__ == '__main__':
    print("🚀 WasteScan Core AI Server (Production Mode) is initializing...")
    
    # 优先读取 Railway 分配的 PORT 环境变量，若本地测试则回退到 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"📍 Listening internally on port: {port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
