import os
import pymysql  # 引入刚才成功安装的数据库连接库
from flask import Flask, request, jsonify
from ultralytics import YOLO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =======================================================
# 1. 自动定位并加载垃圾分类模型
# =======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')  # ✅ 修改：直接读取根目录的 best.pt
model = YOLO(MODEL_PATH)


# 快捷连接 MySQL 数据库的辅助函数
def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),      # ✅ 修改：从环境变量读取
        user=os.getenv('DB_USER', 'root'),           # ✅ 修改：从环境变量读取
        password=os.getenv('DB_PASSWORD', ''),       # ✅ 修改：从环境变量读取
        database=os.getenv('DB_NAME', 'wastescanaidb'), # ✅ 修改：从环境变量读取
        port=int(os.getenv('DB_PORT', '3306')),      # ✅ 修改：从环境变量读取
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
            
            db = None
            try:
                db = get_db_connection()
                with db.cursor() as cursor:
                    # 💡 核心修正：这里已经彻底砍掉了原有的 "sql_record" (INSERT INTO waste_records) 代码！
                    # 这样可以誓死捍卫 PHP 端对历史记录表写入渠道（Scan / Upload）的绝对控制权。
                    
                    # 🌟 动作 B 完美保留：用于驱动前端仪表盘饼图实时暴涨
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
# 5. 临时路由：用于初始化数据库表（仅首次部署使用）
# =======================================================
@app.route('/setup_db', methods=['GET'])
def setup_db():
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recycle_bins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bin_name VARCHAR(50) NOT NULL UNIQUE,
                    current_volume INT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'Normal'
                )
            """)
            # 插入初始数据
            cursor.execute("""
                INSERT INTO recycle_bins (bin_name, current_volume, status) VALUES 
                ('aluminium', 0, 'Normal'),
                ('paper', 0, 'Normal'),
                ('plastic', 0, 'Normal')
                ON DUPLICATE KEY UPDATE bin_name=bin_name
            """)
            db.commit()
        db.close()
        return jsonify({"status": "success", "message": "Database setup completed!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =======================================================
# 6. 自动化及外网服务发布配置
# =======================================================
if __name__ == '__main__':
    # 允许所有网络接口(0.0.0.0)访问，以便 Cloudflare Tunnel 正常进行本地请求的转发
    print("🚀 WasteScan Core AI Server (Production Mode) is initializing...")
    print("📍 Listening internally on port: 5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
