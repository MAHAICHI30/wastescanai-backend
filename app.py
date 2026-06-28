import os
import pymysql
import cv2
import numpy as np
from flask import Flask, request, jsonify
from ultralytics import YOLO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# =======================================================
# 1. 数据库连接（使用Railway环境变量）
# =======================================================
def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('MYSQLHOST', 'mysql.railway.internal'),
        user=os.environ.get('MYSQLUSER', 'root'),
        password=os.environ.get('MYSQLPASSWORD', 'VpUQTVAAjVaDLhqBcUZMfxoJhHEpPRKx'),
        database=os.environ.get('MYSQLDATABASE', 'railway'),
        port=int(os.environ.get('MYSQLPORT', 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

# =======================================================
# 2. 初始化数据库（自动建表）
# =======================================================
def init_database():
    """自动创建recycle_bins表（如果不存在）"""
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recycle_bins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bin_name VARCHAR(50) UNIQUE NOT NULL,
                    current_volume INT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'Normal'
                )
            """)
            # 插入默认数据（如果不存在）
            cursor.execute("""
                INSERT IGNORE INTO recycle_bins (bin_name, current_volume, status) 
                VALUES 
                    ('aluminium', 0, 'Normal'),
                    ('paper', 0, 'Normal'),
                    ('plastic', 0, 'Normal')
            """)
            db.commit()
            print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"⚠️ Database init warning: {e}")
    finally:
        if db: 
            db.close()

# =======================================================
# 3. 加载模型（best.pt在根目录）
# =======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')  # 注意：在根目录，不在models文件夹
model = YOLO(MODEL_PATH)

# 初始化数据库
init_database()

# =======================================================
# 4. 图片预处理函数
# =======================================================
def letterbox_resize(img_path, target_size=(640, 640)):
    """
    保持宽高比等比例缩放图片，并用黑色填充到指定的640x640分辨率
    """
    img = cv2.imread(img_path)
    if img is None:
        return

    h, w = img.shape[:2]
    th, tw = target_size

    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)

    img_resized = cv2.resize(img, (nw, nh))
    background = np.zeros((th, tw, 3), dtype=np.uint8)

    dx = (tw - nw) // 2
    dy = (th - nh) // 2
    background[dy:dy+nh, dx:dx+nw] = img_resized

    cv2.imwrite(img_path, background)

# =======================================================
# 5. AI预测接口
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
        letterbox_resize(img_path, target_size=(640, 640))
        print(f"⚙️ [Preprocessing] Image optimized: {file.filename}")
    except Exception as prep_err:
        print(f"⚠️ [Preprocessing Warning] {prep_err}")
    
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
                        class_name = model.names[class_id]

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
                    sql_update_bin = """
                        UPDATE recycle_bins 
                        SET current_volume = LEAST(current_volume + 5, 100),
                            status = CASE WHEN current_volume + 5 >= 95 THEN 'Full' ELSE status END
                        WHERE LOWER(bin_name) = LOWER(%s)
                    """
                    cursor.execute(sql_update_bin, (final_result,))
                db.commit()
                print(f"✅ [MySQL] Updated bin: {final_result}")
            except Exception as db_err:
                print(f"❌ [MySQL Error] {db_err}")
            finally:
                if db: 
                    db.close()
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
# 6. 请求回收接口
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
        
        print(f"🔥 [MySQL] Set {bin_type} to Dispatched")
        return jsonify({"success": True, "message": f"{bin_type} Bin已派单"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: 
            db.close()

# =======================================================
# 7. 重置垃圾桶接口
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
        
        print(f"🔄 [MySQL] Reset {bin_type} bin")
        return jsonify({"success": True, "message": f"{bin_type} Bin已重置"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: 
            db.close()

# =======================================================
# 8. 启动服务
# =======================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"🚀 WasteScan AI Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
