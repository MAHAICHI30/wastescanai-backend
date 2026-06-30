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

# 声明全局模型缓存变量，不再在启动时硬加载，防止内存瞬间卡死
model = None

# 连通 Railway 云端 MySQL 数据库
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


def letterbox_resize_matrix(img, target_size=(640, 640)):
    """
    🆕 内存级优化方案：直接对内存中的图像矩阵进行自适应等比例缩放和居中黑边填充，
    彻底告别因磁盘 I/O 延迟带来的图片读取不到的硬伤。
    """
    h, w = img.shape[:2]
    th, tw = target_size

    # 计算自适应最佳缩放比例
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)

    # 等比例缩放图像
    img_resized = cv2.resize(img, (nw, nh))

    # 创建一个 640x640 的纯黑画布
    background = np.zeros((th, tw, 3), dtype=np.uint8)

    # 将缩放后的图像居中粘贴至黑色画布上
    dx = (tw - nw) // 2
    dy = (th - nh) // 2
    background[dy:dy+nh, dx:dx+nw] = img_resized
    return background


# =======================================================
# 2. AI 预测扫描 ➔ 同步更新垃圾桶容量并生成历史记录
# =======================================================
@app.route('/predict', methods=['POST'])
def predict():
    global model  # 引用全局模型缓存
    
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file uploaded"}), 400
        
    file = request.files['image']
    file_name_raw = file.filename
    
    # 🌟 核心优化：直接在内存中把文件流解码为 OpenCV 矩阵，绝不发生 I/O 等待卡顿
    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img_mat = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img_mat is None:
            raise ValueError("Uploaded file is not a valid image")
    except Exception as img_err:
        return jsonify({"status": "error", "message": f"Image decode failed: {img_err}"}), 400

    # 延迟加载激活 YOLO 模型
    if model is None:
        print("⚙️ [AI Engine] Detected first request. Loading YOLOv8 weights into RAM...")
        try:
            model = YOLO(MODEL_PATH)
            print("🎯 [AI Engine] Model successfully weights loaded and cached!")
        except Exception as load_err:
            print(f"❌ [AI Engine Error] Lazy loading weights failed: {load_err}")
            return jsonify({"status": "error", "message": f"Model initialization error: {load_err}"}), 500
    
    # 执行 640 x 640 内存级图像等比例缩放与黑边填充
    try:
        img_ready = letterbox_resize_matrix(img_mat, target_size=(640, 640))
        
        # 将优化好的图片留存一份到本地 upload 目录中，供前端/历史记录查阅
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_ready)
        print(f"⚙️ [Preprocessing] Image successfully optimized and written to cache: {file_name_raw}")
    except Exception as prep_err:
        print(f"⚠️ [Preprocessing Warning] Letterbox optimization failed, fallback to raw: {prep_err}")
        # 如果预处理意外失败，回退并直接写盘
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_mat)
        img_ready = img_mat
    
    try:
        # 此时传入已完美转换为标准的 640x640 矩阵或原矩阵进行预测
        results = model.predict(source=img_ready, conf=0.35, workers=0)
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
                    sql_insert_record = """
                        INSERT INTO waste_records (username, record_type, material_type, image_path)
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert_record, ('Guest', 'AI_Scan', final_result, f"upload/{file_name_raw}"))

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
            cursor.execute("SELECT bin_name, current_volume, max_capacity, status, last_updated FROM recycle_bins;")
            bins = cursor.fetchall()
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
    port = int(os.environ.get("PORT", 8080))
    print(f"📍 Listening internally on port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
