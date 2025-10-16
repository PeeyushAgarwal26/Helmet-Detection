import time
import threading
import serial
import requests

class CentralAlarm:
    """
    Manages the buzzer state based on violation statuses from all cameras.
    The buzzer turns on if any camera reports a violation and only turns
    off when all cameras are clear.
    """
    def __init__(self, config, violation_status):
        self.config = config
        self.violation_status = violation_status  # Shared dictionary {cam_id: bool}
        self.buzzer_state = False
        self.stop_event = threading.Event()
        self.ser = None
        self.serial_lock = threading.Lock()
        
        # Initialize serial port if WiFi is not used
        if not self.config.get('use_wifi', True):
            self._init_serial()

    def _init_serial(self):
        """Initializes the serial connection."""
        port = self.config.get('serial_port')
        if not port:
            print("[ALARM] Serial port not configured.")
            return
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            print(f"[ALARM] Serial connected on {port}")
        except Exception as e:
            self.ser = None
            print(f"🔴 [ALARM] Failed to open serial port {port}: {e}")

    def _send_command(self, state):
        """Sends the 'on' or 'off' command via WiFi or Serial."""
        command_str = 'on' if state else 'off'
        
        if self.config.get('use_wifi', True):
            esp_ip = self.config.get('esp_ip')
            if not esp_ip:
                print("🔴 [ALARM] WiFi is enabled but ESP IP is not configured.")
                return
            try:
                url = f"http://{esp_ip}/buzz_{command_str}"
                requests.get(url, timeout=1)
                print(f" [ALARM] WiFi command sent to {url}")
            except Exception as e:
                print(f"🔴 [ALARM] WiFi request failed: {e}")
        else:
            if self.ser and self.ser.is_open:
                cmd = f"buzz_{command_str}\n".encode()
                try:
                    with self.serial_lock:
                        self.ser.write(cmd)
                    print(f" [ALARM] Serial command sent: {cmd.strip()}")
                except Exception as e:
                    print(f"🔴 [ALARM] Serial write failed: {e}")
            else:
                print(" [ALARM] Serial port not open, can't send command.")

    def run(self):
        """
        The main loop for the alarm thread. Periodically checks the shared
        violation status and updates the buzzer accordingly.
        """
        print("[INFO] Central Alarm System started.")
        while not self.stop_event.is_set():
            try:
                # Check if any value in the dictionary is True
                is_any_violation = any(self.violation_status.values())

                if is_any_violation and not self.buzzer_state:
                    print(" [ALARM] Violation detected! Turning buzzer ON.")
                    self._send_command(True)
                    self.buzzer_state = True
                elif not is_any_violation and self.buzzer_state:
                    print(" [ALARM] All streams clear. Turning buzzer OFF.")
                    self._send_command(False)
                    self.buzzer_state = False

            except Exception as e:
                print(f"🔴 [ERROR] Unhandled error in alarm loop: {e}")

            time.sleep(1) # Check status every second

        print("[INFO] Central Alarm System stopping...")
        if self.buzzer_state: # Ensure buzzer is off on exit
            self._send_command(False)
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed.")

    def stop(self):
        """Signals the alarm thread to stop."""
        self.stop_event.set()