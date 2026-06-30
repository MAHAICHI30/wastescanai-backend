# =======================================================
# 2. AI 预测扫描 ➔ 同步更新垃圾桶容量、生成历史记录并更新用户活跃时间
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
    file_name_raw = file.filename
    
    # 🌟【核心修复】：动态接收 PHP 通过 Post 传过来的用户名与上传身份
    current_user = request.form.get('username', 'Guest')
    identity = request.form.get('identity', 'scan') # 如果没有传 identity，默认当成前端相机 scan
    
    # 映射标准 record_type（对齐你 history.php 里的逻辑）
    record_type = 'upload' if identity == 'gallery_upload' else 'scan'
    
    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img_mat = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img_mat is None:
            raise ValueError("Uploaded file is not a valid image")
    except Exception as img_err:
        return jsonify({"status": "error", "message": f"Image decode failed: {img_err}"}), 400
    
    try:
        img_ready = letterbox_resize_matrix(img_mat, target_size=(640, 640))
        
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_ready)
        print(f"⚙️ [Preprocessing] Image successfully optimized and written to cache: {file_name_raw}")
    except Exception as prep_err:
        print(f"⚠️ [Preprocessing Warning] Letterbox optimization failed, fallback to raw: {prep_err}")
        upload_dir = os.path.join(BASE_DIR, 'upload')
        os.makedirs(upload_dir, exist_ok=True)
        img_path = os.path.join(upload_dir, file_name_raw)
        cv2.imwrite(img_path, img_mat)
        img_ready = img_mat
    
    try:
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

                    # 🌟 时区补丁保持
                    tz_kl = timezone(timedelta(hours=8))  
                    local_now_str = datetime.now(tz_kl).strftime('%Y-%m-%d %H:%M:%S')

                    # 1. 插入扫描/上传记录历史（使用动态获取的 current_user 和 record_type）
                    sql_insert_record = """
                        INSERT INTO waste_records (username, record_type, material_type, image_path, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql_insert_record, (current_user, record_type, final_result, f"upload/{file_name_raw}", local_now_str))

                    # 2. 实时同步更新垃圾桶满载容量和状态
                    sql_update_bin = """
                        UPDATE recycle_bins  
                        SET current_volume = LEAST(current_volume + 5, 100),
                            status = CASE WHEN current_volume + 5 >= 95 THEN 'Full' ELSE status END
                        WHERE LOWER(bin_name) = LOWER(%s)
                    """
                    cursor.execute(sql_update_bin, (final_result,))

                    # 3. 更新用户最后活跃时间
                    sql_update_user_active = """
                        UPDATE users  
                        SET last_active = %s  
                        WHERE username = %s
                    """
                    cursor.execute(sql_update_user_active, (local_now_str, current_user))

                db.commit()
                print(f"✅ [MySQL] Strictly synchronized time {local_now_str} for user '{current_user}' ({record_type})")
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
