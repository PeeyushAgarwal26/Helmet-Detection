import cv2
import threading
import time
from src.detector import load_detector_from_config
from src.camera_worker import camera_loop
from src.alarm import CentralAlarm

# --- ROI Drawing State ---
# These are global to be accessible by the mouse callback
drawing_state = {
    "drawing": False,
    "start_point": (-1, -1),
    "temp_end_point": (-1, -1),
    "cam_id": -1
}

def mouse_callback(event, x, y, flags, param):
    """
    Mouse callback function to handle drawing a Region of Interest (ROI)
    on a camera window.
    """
    # --- Unpack all three arguments passed in param ---
    cam_id, roi_dict, window_names = param
    global drawing_state

    # --- Bind all actions to the Left Mouse Button events ---
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing_state["drawing"] = True
        drawing_state["start_point"] = (x, y)
        drawing_state["temp_end_point"] = (x, y)
        drawing_state["cam_id"] = cam_id
        # Clear old ROI when starting a new one
        if cam_id in roi_dict:
            del roi_dict[cam_id]
            try:
                window_name = window_names.get(cam_id, f"Camera {cam_id}")
                cv2.destroyWindow(f"ROI for {window_name}")
            except (cv2.error, KeyError):
                pass

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing_state["drawing"] and drawing_state["cam_id"] == cam_id:
            drawing_state["temp_end_point"] = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        if drawing_state["drawing"] and drawing_state["cam_id"] == cam_id:
            x1, y1 = drawing_state["start_point"]
            x2, y2 = (x, y)
            roi_x = min(x1, x2)
            roi_y = min(y1, y2)
            roi_w = abs(x1 - x2)
            roi_h = abs(y1 - y2)

            if roi_w > 20 and roi_h > 20:  # Minimum size for a valid ROI
                roi_dict[cam_id] = (roi_x, roi_y, roi_w, roi_h)
                print(f"[INFO] ROI set for Cam {cam_id} at {roi_dict[cam_id]}")
        
        # Reset drawing state regardless of which window the mouse is released in
        drawing_state["drawing"] = False
        drawing_state["start_point"] = (-1, -1)
        drawing_state["temp_end_point"] = (-1, -1)
        drawing_state["cam_id"] = -1


def main():
    """
    Main function to initialize and run the multi-camera detection application.
    """
    print("[INFO] Main script started.")
    # Load configuration and the selected detector model
    detector_settings, config = load_detector_from_config()
    if not detector_settings:
        print("🔴 [FATAL] Could not load detector. Exiting.")
        return

    camera_feeds = config.get('camera_feeds', [])
    num_cameras = len(camera_feeds)
    if num_cameras == 0:
        print("🔴 [FATAL] No camera feeds found in config.yaml. Exiting.")
        return
    print(f"[INFO] Found {num_cameras} camera feeds. Starting threads...")

    # Initialize shared resources for threading
    shared_data = {
        'frame_dict': {},
        'roi_frame_dict': {},
        'lock': threading.Lock(),
        'stop_events': [threading.Event() for _ in range(num_cameras)],
        'violation_status': {i: False for i in range(num_cameras)},
        'roi_coords': {},
        'config': config
    }

    # Conditionally start the centralized alarm system
    alarm_system = None
    alarm_thread = None
    if detector_settings.get('perform_violation_check', False):
        print("[INFO] Helmet detection model selected. Starting alarm system.")
        alarm_system = CentralAlarm(config, shared_data['violation_status'])
        alarm_thread = threading.Thread(target=alarm_system.run, daemon=True)
        alarm_thread.start()
    else:
        print("[INFO] Non-helmet model selected. Alarm system is disabled.")


    # Start a worker thread for each camera feed
    threads = []
    for i, stream_url in enumerate(camera_feeds):
        thread = threading.Thread(target=camera_loop, args=(i, stream_url, detector_settings, shared_data), daemon=True)
        threads.append(thread)
        thread.start()

    # Main display loop
    window_names = {i: (config.get('camera_titles', [])[i] or f"Camera {i}") for i in range(num_cameras)}
    roi_windows_created = set() # Keep track of created ROI windows
    for i, name in window_names.items():
        cv2.namedWindow(name)
        cv2.setMouseCallback(name, mouse_callback, param=(i, shared_data['roi_coords'], window_names))
    print("[INFO] All threads started. Starting frame display loop.")
    
    try:
        while True:
            # Exit loop if all windows have been closed by the user
            if not window_names:
                print("[INFO] All camera windows closed. Exiting main loop.")
                for i in range(num_cameras): # Ensure all threads are stopped
                    shared_data['stop_events'][i].set()
                break

            # Use a copy of keys to allow safe dictionary modification during iteration
            active_camera_ids = list(window_names.keys())

            for i in active_camera_ids:
                name = window_names.get(i)
                if not name: continue

                # Check for main window closure BEFORE showing it
                is_main_window_open = True
                try:
                    if cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1:
                        is_main_window_open = False
                except cv2.error:
                    is_main_window_open = False
                
                if not is_main_window_open:
                    print(f"Window for '{name}' closed by user. Stopping thread {i}.")
                    shared_data['stop_events'][i].set()
                    del window_names[i]
                    continue 

                # If the main window is open, display its frame
                with shared_data['lock']:
                    frame = shared_data['frame_dict'].get(i)
                if frame is not None:
                    display_frame = frame.copy()
                    if drawing_state["drawing"] and drawing_state["cam_id"] == i:
                        start, end = drawing_state["start_point"], drawing_state["temp_end_point"]
                        cv2.rectangle(display_frame, start, end, (0, 255, 255), 2)
                    cv2.imshow(name, display_frame)

                # --- ROI window logic ---
                roi_name = f"ROI for {name}"
                is_roi_supposed_to_be_active = False
                with shared_data['lock']:
                    if i in shared_data['roi_coords']:
                        is_roi_supposed_to_be_active = True

                if is_roi_supposed_to_be_active:
                    with shared_data['lock']:
                        roi_frame = shared_data['roi_frame_dict'].get(i)

                    if roi_frame is not None:
                        if i not in roi_windows_created:
                            cv2.namedWindow(roi_name)
                            roi_windows_created.add(i)
                        
                        is_roi_window_actually_open = True
                        try:
                            if cv2.getWindowProperty(roi_name, cv2.WND_PROP_VISIBLE) < 1:
                                is_roi_window_actually_open = False
                        except cv2.error:
                            is_roi_window_actually_open = False

                        if is_roi_window_actually_open:
                            cv2.imshow(roi_name, roi_frame)
                        else:
                            # User closed the window, so we change the state
                            print(f"ROI window for '{name}' closed. Reverting to full frame.")
                            roi_windows_created.discard(i)
                            with shared_data['lock']:
                                if i in shared_data['roi_coords']:
                                    del shared_data['roi_coords'][i]
                                if i in shared_data['roi_frame_dict']:
                                    del shared_data['roi_frame_dict'][i]
            
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                print("[INFO] 'q' pressed. Shutting down all streams.")
                for i in range(num_cameras):
                    shared_data['stop_events'][i].set()
                break
    
    finally:
        # Cleanup all resources
        print("[EXIT] Cleaning up resources...")
        if alarm_system:
            alarm_system.stop()
        if alarm_thread and alarm_thread.is_alive():
            alarm_thread.join(timeout=2)
        for i, thread in enumerate(threads):
            shared_data['stop_events'][i].set()
            if thread.is_alive():
                thread.join(timeout=2)
        cv2.destroyAllWindows()
        print("[INFO] Main script finished.")

if __name__ == '__main__':
    main()