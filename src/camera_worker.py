import cv2
import time
import os
from datetime import datetime

RESIZE_DIM = (640, 480)

def run_detection(model, frame, confidence):
    """
    Performs object detection on a single frame using the provided YOLO model.
    """
    results = model.predict(
        source=frame, 
        conf=confidence,
        stream=False, 
        verbose=False)[0]
    
    detections = []
    for box in results.boxes.data:
        x1, y1, x2, y2, conf, cls = box.tolist()
        class_id = int(cls)
        class_name = results.names[class_id]
        if class_name == "ignore":
            continue
        detections.append({
            'box': [x1, y1, x2, y2],
            'conf': conf,
            'class': class_name
        })
    return detections

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def log_violation(cam_id, violation_count):
    ensure_dir("logs")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("logs/alerts.log", "a") as f:
        f.write(
            f"[{now}] Camera {cam_id} | Violations in frame: {violation_count}\n")

def save_violation_images(frame, detection, cam_id, frame_count, violation_index):
    try:
        output_dir = "violations"
        ensure_dir(output_dir)
        x1, y1, x2, y2 = map(int, detection['box'])
        cropped_image = frame[y1:y2, x1:x2]
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(output_dir, f"cam{cam_id}_{now}_frame{frame_count}_viol{violation_index}.jpg")
        cv2.imwrite(filename, cropped_image)
    except Exception as e:
        print(f"🔴 [ERROR] Cam {cam_id}: Could not save violation image: {e}")

def camera_loop(cam_id, stream_url, detector_settings, shared_data):
    """
    Main loop for a single camera thread.
    Handles frame grabbing, detection, and updating shared data structures.
    """
    model = detector_settings['model']
    threshold = detector_settings['confidence']
    perform_violation_check = detector_settings['perform_violation_check']
    no_helmet_class = detector_settings.get('no_helmet_class')

    config = shared_data['config']
    lock = shared_data['lock']
    stop_event = shared_data['stop_events'][cam_id]
    
    image_save_cooldown = config.get('alarm_cooldown_sec', 15)

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print(f"❌ [ERROR] Cannot open camera {cam_id} at {stream_url}")
        return
        
    frame_count = 0
    last_image_save_time = 0
    
    print(f"[INFO] Thread for Cam {cam_id} started.")
    
    while not stop_event.is_set():
        try:
            ret, frame = cap.read()
            if not ret:
                print(f"⚠️  [WARNING] Camera {cam_id} disconnected. Retrying...")
                time.sleep(2)
                cap.release()
                cap = cv2.VideoCapture(stream_url)
                continue

            frame_count += 1
            start_time = time.time()
            resized_frame = cv2.resize(frame, RESIZE_DIM)
            
            with lock:
                roi = shared_data['roi_coords'].get(cam_id)
            
            process_frame = resized_frame
            roi_display_frame = None

            if roi:
                x, y, w, h = roi
                x, y, w, h = max(0,x), max(0,y), min(w, RESIZE_DIM[0]-x), min(h, RESIZE_DIM[1]-y)
                process_frame = resized_frame[y:y+h, x:x+w]
                cv2.rectangle(resized_frame, (x, y), (x + w, y + h), (255, 255, 0), 2)
            
            if process_frame.size == 0: continue

            detections = run_detection(model, process_frame, threshold)
            no_of_violations = 0

            if perform_violation_check:
                current_violations = [det for det in detections if det['class'] == no_helmet_class]
                no_of_violations = len(current_violations)
                violation_in_frame = no_of_violations > 0

                with lock:
                    shared_data['violation_status'][cam_id] = violation_in_frame
                
                if violation_in_frame:
                    current_time = time.time()
                    if current_time - last_image_save_time > image_save_cooldown:
                        log_violation(cam_id, no_of_violations)
                        for index, det in enumerate(current_violations):
                            save_violation_images(process_frame, det, cam_id, frame_count, index + 1)
                        last_image_save_time = current_time
            
            for det in detections:
                x1, y1, x2, y2 = map(int, det['box'])
                class_name = det['class']
                label = f"{class_name.upper()} {det['conf']:.2f}"
                
                color = (0, 0, 255) if perform_violation_check and class_name == no_helmet_class else (0, 255, 0)
                cv2.rectangle(process_frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(process_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            if roi:
                roi_display_frame = process_frame

            fps = 1 / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
            
            stat_text = f"FPS: {fps:.2f} | "
            stat_text += f"Violations: {no_of_violations}" if perform_violation_check else f"Detections: {len(detections)}"

            cv2.putText(resized_frame, stat_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            with lock:
                shared_data['frame_dict'][cam_id] = resized_frame.copy()
                if roi_display_frame is not None:
                    shared_data['roi_frame_dict'][cam_id] = roi_display_frame.copy()

        except Exception as e:
            print(f"🔴 [ERROR] An error occurred in camera_loop for Cam {cam_id}: {e}")
            time.sleep(5)

    print(f"[INFO] Thread for Camera {cam_id} finished. Cleaning up.")
    cap.release()