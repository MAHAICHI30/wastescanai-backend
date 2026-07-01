import os
import time
from flask import Flask, request, jsonify
from ultralytics import YOLO
from flask_cors import CORS
import pymysql  
import cv2        
import numpy as np 
from datetime import datetime, timezone, timedelta

# =======================================================
# 1. 核心应用初始化与模型预加载
# =======================================================
app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')  

print("⚙️ [Boot Initialization] Pre-loading YOLOv8 weights into memory...")
try:
    model = YOLO(MODEL_PATH)
    print("🎯 [Boot Initialization] YOLOv8 Model successfully pre-loaded and cached!")
except Exception as e:
    print(f"❌ [Boot Error] Failed to pre-load model weights: {e}")
    model = None


def get_db_connection():
    """建立自适应 Railway 拓扑结构的内网数据库会话并强制锁定 GMT+8 时区"""
    # 🌟 修复卡死：如果环境变量拿出来是空字符串，强行将其恢复为内网默认域名
    db_host = os.getenv("MYSQLHOST")
    if not db_host or db_host.strip() == "":
        db_host = "mysql.railway.internal"

    conn = pymysql.connect(
        host=db_host,
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", "root"),
        database=os.getenv("MYSQLDATABASE", "railway"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00';")
    return conn

def letterbox_resize_matrix(img, target_size=(640, 640)):
    """内存级自适应等比例缩放与纯黑画布居中填充算法"""
    h, w = img.shape[:2]
    th, tw = target_size
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    img_resized = cv2.resize(img, (nw, nh))
    background = np.zeros((th, tw, 3), dtype=np.uint8)
    dx = (tw - nw) // 2
    dy = (th - nh) // 2
    background[dy:dy+nh, dx:dx+nw] = img_resized
    return background


# =======================================================
# 2. AI 核心预测流控制（解耦并确保 100% 留痕入库）
# =======================================================
@app.route('/predict', methods=['POST'])
def predict():
    global model  
    
    if model is None:
        print("⚠️ [AI Engine Warning] Model is uninitialized. Trying to initialize now...")
        try:
            model = YOLO(MODEL_PATH)
        except Exception as err:
            return jsonify({"status": "error", "message": f"Model is totally unavailable: {err}"}), 500

    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file uploaded"}), 400
        
    file = request.files['image']
    
    # 🌟【文件名安全清洗与降级机制】：解决 PHP cURL 传输文件名丢失或带特殊字符导致 SQL 崩溃问题
    raw_filename = file.filename
    if not raw_filename or raw_filename.strip() == "" or raw_filename == "blob":
        # 降级方案：如果文件名为空或为前端 blob 默认词，自动生成防重名时间戳
        file_name_raw = f"scan_{int(time.time())}.jpg"
    else:
        # 清洗掉两端空格，并将可能导致 SQL 或文件路径报错的空格替换为下划线
        file_name_raw = os.path.basename(raw_filename.strip().replace(" ", "_"))
    
    # 🌟【对齐缩进 + 清洗防错】：强行去掉可能被 cURL 夹带的 \r \n 空格等所有隐形字符
    current_user = request.form.get('username', 'Guest').strip()
    identity = request.form.get('identity', 'scan').strip() 
    
    # 智能对齐数据字典映射：camera_scan -> scan, gallery_upload -> upload
    record_type = 'upload' if identity == 'gallery_upload' else 'scan'
    
    # 将上传的文件流直接解码到内存矩阵，告别磁盘死锁
    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img_mat = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img_mat is None:
            raise ValueError("Uploaded file is not a valid image")
    except Exception as img_err:
        return jsonify({"status": "error", "message": f"Image decode failed: {img_err}"}), 400
    
    # 图像预处理与本地缓存持久化
    try:
        img_ready = letterbox_resize_matrix(img_mat, target_size=(640, 640))
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_ready)
    except Exception as prep_err:
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_mat)
        img_ready = img_mat
    
    # 推理主循环与判定状态提取
    final_result = "unknown"
    final_box = [15, 15, 70, 70] 
    is_detected = False
    
    try:
        results = model.predict(source=img_ready, conf=0.35, workers=0)
        highest_conf = 0.0
        
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    conf_score = float(box.conf[0])
                    if conf_score > highest_conf:
                        highest_conf = conf_score
                        coords = box.xyxyn[0].tolist()
                        
                        final_result = model.names[int(box.cls[0])]
                        final_box = [coords[1] * 100, coords[0] * 100, (coords[3] - coords[1]) * 100, (coords[2] - coords[0]) * 100]
                        is_detected = True
                        
        if not is_detected:
            print(f"⚠️ [AI Engine] Object unrecognized. Fallback to 'unknown' record status.")
            
    except Exception as ai_err:
        print(f"❌ [AI Inference Error] Inference loop blocked: {ai_err}")

    # 🌟【业务层解耦控制】：独立封装数据库，无论 MySQL 报什么错，都绝对不会影响最下面的 return 回包
    db = None  
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            tz_kl = timezone(timedelta(hours=8))  
            local_now_str = datetime.now(tz_kl).strftime('%Y-%m-%d %H:%M:%S')

            # 1. 记入核心流水历史表
            sql_insert_record = """
                INSERT INTO waste_records (username, record_type, material_type, image_path, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql_insert_record, (current_user, record_type, final_result, f"upload/{file_name_raw}", local_now_str))

            # 2. 实时更新公共实体垃圾桶容量
            if is_detected:
                sql_update_bin = """
                    UPDATE recycle_bins  
                    SET current_volume = LEAST(current_volume + 5, 100),
                        status = CASE WHEN current_volume + 5 >= 95 THEN 'Full' ELSE status END
                    WHERE LOWER(bin_name) = LOWER(%s)
                """
                cursor.execute(sql_update_bin, (final_result,))

            # 3. 刷新安全用户表活跃时间戳
            sql_update_user_active = """
                UPDATE users  
                SET last_active = %s  
                WHERE username = %s
            """
            cursor.execute(sql_update_user_active, (local_now_str, current_user))

        db.commit()
        print(f"✅ [MySQL] Transaction synced successfully for user '{current_user}' ({final_result})!")
    except Exception as db_err:
        # 💡 核心提示：如果修改后依然没有历史记录，请在部署环境控制台查看这条报错的具体信息，如表不存在或字段不匹配！
        print(f"❌ [MySQL Error] Prediction transactional replication failed: {db_err}")
        if db:
            db.rollback()
    finally:
        if db:
            db.close()
            
    # 🌟【放至最外层】：无论上面的 MySQL 出错还是回滚，AI 预测响应结果必定秒回前端，彻底消灭无限转圈圈卡死！
    return jsonify({
        "status": "success",
        "prediction": final_result,
        "box": final_box  
    })


# =======================================================
# 3. 提供数据拉取接口（大屏及表单渲染）
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
# 4. 派单请求流转兼容接口
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
        return jsonify({"success": True, "message": f"{bin_type} Bin state已成功流转为派单状态！"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: db.close()


# =======================================================
# 5. 清空重置接口
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
        return jsonify({"success": True, "message": f"{bin_type} Bin reset success."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if db: db.close()


if __name__ == '__main__':
    print("🚀 WasteScan Core AI Server (Production Mode) is initializing...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
