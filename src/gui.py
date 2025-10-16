import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import yaml
import subprocess
import threading
import queue
import os

CONFIG_PATH = "config/config.yaml"
if not os.path.exists("config"):
    os.makedirs("config")

class HelmetGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Factory Detection Control Panel")
        self.root.minsize(700, 600)

        # Load the logo image
        # try:
        #     self.logo_image = tk.PhotoImage(file="data/Axis_logo.png")
        #     self.root.iconphoto(True, self.logo_image) # Setting icon of the application
        # except tk.TclError:
        #     print("Logo image not found at 'data/Axis_logo.png'. Skipping logo.")
        #     self.logo_image = None # Set to None if image fails to load

        self.log_queue = queue.Queue()

        self.load_config()
        self.setup_ui()
        self.process_log_queue()

    def load_config(self):
        try:
            with open(CONFIG_PATH, 'r') as f:
                self.config = yaml.safe_load(f)
                if self.config is None:
                    self.config = {}
        except FileNotFoundError:
            # If the file doesn't exist, start with an empty config
            self.config = {}
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")
            self.root.quit()

    def save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(self.config, f)
        messagebox.showinfo("Success", "Configuration saved!")

    def _toggle_serial_port(self):
        """Callback to enable/disable serial port based on WiFi checkbox."""
        if self.use_wifi_var.get():
            # WiFi is checked: clear and disable the serial port entry
            self.serial_port_entry.delete(0, tk.END)
            self.serial_port_entry.config(state='disabled')
        else:
            # WiFi is unchecked: enable the serial port entry
            self.serial_port_entry.config(state='normal')

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        # Create a Label to display the logo at the top
        # if self.logo_image:
        #     logo_label = ttk.Label(main_frame, image=self.logo_image)
        #     logo_label.pack(side=TOP, pady=(5, 15)) # Add padding below the log

        # ==== Camera Input Fields ====
        cam_frame = ttk.LabelFrame(main_frame, text="Camera URLs", padding=10)
        cam_frame.pack(fill=X, padx=10, pady=5)

        self.camera_entries = []
        self.title_entries = []
        for i in range(4):
            frame = ttk.Frame(cam_frame)
            frame.pack(fill=X, pady=2)
            ttk.Label(frame, text=f"Camera {i+1}:", width=10).pack(side=LEFT)

            url_entry = ttk.Entry(frame)
            url_entry.pack(side=LEFT, padx=5, fill=X, expand=True)
            if i < len(self.config.get('camera_feeds', [])):
                url_entry.insert(0, self.config['camera_feeds'][i])
            self.camera_entries.append(url_entry)

            title_entry = ttk.Entry(frame, width=25)
            title_entry.pack(side=LEFT, padx=5)
            if i < len(self.config.get('camera_titles', [])):
                title_entry.insert(0, self.config['camera_titles'][i])
            self.title_entries.append(title_entry)

        btn_frame = ttk.Frame(cam_frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Update Cameras", command=self.update_camera_feeds, bootstyle="info").pack()

        # ==== Detection Model Selection ====
        model_frame = ttk.LabelFrame(main_frame, text="Detection Model", padding=10)
        model_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Label(model_frame, text="Select Model:").pack(side=LEFT, padx=(0, 5))
        
        self.model_var = tk.StringVar()
        model_choices = ["Helmet detection", "Person Detection", "Face Detection", "Vehicle detection"]
        self.model_combobox = ttk.Combobox(model_frame, textvariable=self.model_var, values=model_choices, state="readonly")
        
        current_model = self.config.get('detection_model', model_choices[0])
        self.model_combobox.set(current_model if current_model in model_choices else model_choices[0])

        self.model_combobox.pack(side=LEFT, fill=X, expand=True)

        # ==== ESP Settings ====
        esp_frame = ttk.LabelFrame(main_frame, text="ESP Settings", padding=10)
        esp_frame.pack(fill=X, padx=10, pady=5)

        ttk.Label(esp_frame, text="ESP IP:").pack(side=LEFT, padx=5)
        self.esp_ip_entry = ttk.Entry(esp_frame, width=20)
        self.esp_ip_entry.pack(side=LEFT)
        self.esp_ip_entry.insert(0, self.config.get('esp_ip', ''))

        self.use_wifi_var = tk.BooleanVar(value=self.config.get('use_wifi', False))
        ttk.Checkbutton(esp_frame, text="Use WiFi", variable=self.use_wifi_var, bootstyle="primary", command=self._toggle_serial_port).pack(side=LEFT, padx=10)

        ttk.Label(esp_frame, text="Serial Port:").pack(side=LEFT, padx=5)
        self.serial_port_entry = ttk.Entry(esp_frame, width=20)
        self.serial_port_entry.pack(side=LEFT)
        self.serial_port_entry.insert(0, self.config.get('serial_port', ''))

        ttk.Button(esp_frame, text="Update ESP & Model Config", command=self.update_esp_config, bootstyle="info").pack(side=LEFT, padx=10)

        self._toggle_serial_port()

        # ==== Run Button ====
        ttk.Button(main_frame, text="RUN", command=self.run_script, bootstyle="success").pack(pady=10, ipady=10, ipadx=20)

        # ==== Logs ====
        log_frame = ttk.LabelFrame(main_frame, text="Logs", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.log_output = ScrolledText(log_frame, height=10)
        self.log_output.pack(fill=BOTH, expand=True)
        self.log_output.config(state='disabled')

    def update_camera_feeds(self):
        self.config['camera_feeds'] = [e.get().strip() for e in self.camera_entries if e.get().strip()]
        self.config['camera_titles'] = [t.get().strip() for t in self.title_entries][:len(self.config['camera_feeds'])]
        self.save_config()

    def update_esp_config(self):
        self.config['detection_model'] = self.model_var.get()
        self.config['esp_ip'] = self.esp_ip_entry.get().strip()
        self.config['use_wifi'] = self.use_wifi_var.get()
        self.config['serial_port'] = self.serial_port_entry.get().strip()
        self.save_config()
        messagebox.showinfo("Saved", "ESP, Model, and Serial config updated")

    def process_log_queue(self):
        had_messages = False
        try:
            # Process all available messages in the queue
            while True:
                line = self.log_queue.get_nowait()
                if line and not had_messages:
                    self.log_output.config(state='normal')
                    had_messages = True
                self.log_output.insert(tk.END, line)
        except queue.Empty:
            pass
        
        if had_messages:
            self.log_output.see(tk.END)
            self.log_output.config(state='disabled')
            
        self.root.after(100, self.process_log_queue)

    def run_script(self):
        def runner():
            python_executable = "python" if os.name == 'nt' else "python3"
            self.log_queue.put(f"--- Starting process: {python_executable} main.py ---\n")
            try:
                process = subprocess.Popen(
                    [python_executable, "main.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    bufsize=1
                )
                for line in iter(process.stdout.readline, ''):
                    self.log_queue.put(line)
                
                process.stdout.close()
                process.wait()
                self.log_queue.put("--- Process finished ---\n")
            except FileNotFoundError:
                msg = f"Error: '{python_executable}' not found. Please ensure Python is in your PATH.\n"
                self.log_queue.put(msg)
            except Exception as e:
                self.log_queue.put(f"--- An unexpected error occurred: {e} ---\n")

        self.log_output.config(state='normal')
        self.log_output.delete(1.0, tk.END)
        self.log_output.config(state='disabled')
        
        threading.Thread(target=runner, daemon=True).start()

if __name__ == '__main__':
    root = ttk.Window(themename="cosmo")
    app = HelmetGUI(root)
    root.mainloop()