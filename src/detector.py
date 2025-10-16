import yaml
from ultralytics import YOLO

def load_detector_from_config(config_path="config/config.yaml"):
    """
    Loads the correct model and settings based on the 'detection_model'
    key in the config file. It only loads helmet-specific classes when the
    helmet model is selected, making the system flexible for other models.
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"🔴 [ERROR] Configuration file not found at {config_path}")
        return None, None
    except Exception as e:
        print(f"🔴 [ERROR] Failed to load or parse config file: {e}")
        return None, None

    selected_model_name = config.get('detection_model', '').strip()
    
    model_key_map = {
        "Helmet detection": "helmet",
        "Person Detection": "person",
        "Face Detection": "face",
        "Vehicle detection": "vehicle"
    }
    model_key = model_key_map.get(selected_model_name)

    if not model_key or model_key not in config.get('models', {}):
        print(f"🔴 [ERROR] Model '{selected_model_name}' is not configured in config.yaml under 'models'.")
        return None, None

    try:
        model_config = config['models'][model_key]
        model_path = model_config['model_path']
        class_file = model_config['class_file']

        print(f"[INFO] Loading model: {selected_model_name} from {model_path}")
        model = YOLO(model_path)

        with open(class_file, 'r') as f:
            class_data = yaml.safe_load(f)
        
        class_names = class_data.get('names', [])
        
        # --- Conditionally load helmet-specific keys ---
        perform_violation_check = (selected_model_name == "Helmet detection")
        helmet_class = None
        no_helmet_class = None

        if perform_violation_check:
            helmet_class = class_data.get('helmet_class')
            no_helmet_class = class_data.get('no_helmet_class')
            if not helmet_class or not no_helmet_class:
                print(f"🔴 [FATAL] Helmet model is selected, but 'helmet_class' or 'no_helmet_class' are missing in {class_file}.")
                return None, None
            print("[INFO] Violation checking is ENABLED.")
        else:
            print("[INFO] Violation checking is DISABLED for this model.")

        detector_settings = {
            "model": model,
            "class_names": class_names,
            "confidence": config.get('confidence_threshold', 0.5),
            "perform_violation_check": perform_violation_check,
            "helmet_class": helmet_class,
            "no_helmet_class": no_helmet_class,
        }
        
        return detector_settings, config

    except KeyError as e:
        print(f"🔴 [FATAL] Missing required key {e} in config for model '{selected_model_name}'.")
        return None, None
    except Exception as e:
        print(f"🔴 [FATAL] Failed to load model or class file for '{selected_model_name}': {e}")
        return None, None