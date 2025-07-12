import sys, json, time, pyautogui, keyboard, serial, serial.tools.list_ports, psutil, subprocess, importlib.util, re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QCheckBox, QSlider,
    QComboBox, QLineEdit, QPlainTextEdit, QHBoxLayout, QStackedWidget,
    QMessageBox
)
from PyQt6.QtGui import QFont, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer
from login import LoginPage

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "rgb": [255, 0, 0],
    "tolerance": 30,
    "delay": 100,
    "fov": 150,
    "resolution": "1920x1080",
    "smoothing": 1,
    "offset": [0, 0]
}

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(*pyautogui.size())
        self.fov = 150
        self.aim_on = False
        self.trig_on = False
        self.crosshair_on = True
        self.show()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width() // 2, self.height() // 2
        p.setPen(QColor(255, 255, 255, 150))
        p.drawEllipse(w - self.fov, h - self.fov, self.fov * 2, self.fov * 2)
        if self.crosshair_on:
            p.drawLine(w - 10, h, w + 10, h)
            p.drawLine(w, h - 10, w, h + 10)
        if self.aim_on or self.trig_on:
            p.setFont(QFont("Segoe UI", 14))
            p.setPen(QColor(0, 255, 0))
            status = " | ".join([s for s in ["Aimbot ON" if self.aim_on else "", "Trigger ON" if self.trig_on else ""] if s])
            p.drawText(30, 50, status)

class AimbotGUI(QWidget):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.setFixedSize(460, 920)
        self.setWindowTitle("🎯 DEBIAN NVIDIA Control Panel")
        self.setStyleSheet("background-color: #000; color: white;")
        self.config = DEFAULT_CONFIG.copy()
        self.overlay = Overlay()
        self.serial_port = None
        self.detecting = False
        self.ctrl_pressed = False
        self.pick_rgb_active = False
        self.rgb_label = QLabel("RGB: Not Picked")
        self.color1, self.color2 = self.config["rgb"], [0, 0, 0]
        self.build_ui()
        self.setup_timers()

    def build_ui(self):
        l = QVBoxLayout(self)
        l.addWidget(QLabel("Aimbot Control Panel", font=QFont("Segoe UI", 14, QFont.Weight.Bold)))

        self.aim_cb, self.trig_cb, self.safe_cb, self.cross_cb = QCheckBox("Enable Aimbot"), QCheckBox("Enable Triggerbot"), QCheckBox("Safe Mode (No Serial CMD)"), QCheckBox("Enable Crosshair")
        self.safe_cb.setChecked(True)
        self.cross_cb.setChecked(True)
        for cb in [self.aim_cb, self.trig_cb, self.safe_cb, self.cross_cb]:
            l.addWidget(cb)

        self.delay_slider = QSlider(Qt.Orientation.Horizontal); self.delay_slider.setRange(10, 1000); self.delay_slider.setValue(self.config["delay"])
        l.addWidget(QLabel("Trigger Delay (ms):")); l.addWidget(self.delay_slider)

        self.fov_combo = QComboBox(); self.fov_combo.addItems(map(str, [100, 150, 200, 250, 300])); self.fov_combo.setCurrentText(str(self.config["fov"]))
        l.addWidget(QLabel("FOV Circle Size:")); l.addWidget(self.fov_combo)

        self.port_combo = QComboBox(); self.refresh_ports()
        l.addWidget(QLabel("Arduino COM Port:")); l.addWidget(self.port_combo)

        self.resolution_input = QLineEdit(self.config["resolution"])
        l.addWidget(self.resolution_input)

        self.connect_btn = QPushButton("Connect Arduino", clicked=self.connect_arduino)
        self.auto_upload_btn = QPushButton("Auto Load Arduino", clicked=self.auto_upload)
        l.addWidget(self.connect_btn); l.addWidget(self.auto_upload_btn)

        self.rgb_btn = QPushButton("Pick RGB (CTRL)", clicked=self.enable_rgb_picker)
        l.addWidget(self.rgb_btn); l.addWidget(self.rgb_label)

        box_l = QHBoxLayout()
        self.color1_box, self.color2_box = QLabel(), QLabel()
        for b in [self.color1_box, self.color2_box]: b.setFixedSize(40, 40)
        self.color1_box.setStyleSheet(f"background-color: rgb({','.join(map(str, self.color1))}); border: 2px solid #00f;")
        self.color2_box.setStyleSheet(f"background-color: rgb({','.join(map(str, self.color2))}); border: 1px solid white;")
        box_l.addWidget(self.color1_box); box_l.addWidget(self.color2_box); l.addLayout(box_l)

        self.start_btn = QPushButton("Start Detection", clicked=self.start_detection)
        self.stop_btn = QPushButton("Stop Detection", clicked=self.stop_detection)
        l.addWidget(self.start_btn); l.addWidget(self.stop_btn)

        self.smooth_input = QLineEdit(str(self.config["smoothing"]))
        self.offset_input = QLineEdit(",".join(map(str, self.config["offset"])))
        l.addWidget(QLabel("Advanced Settings")); l.addWidget(self.smooth_input); l.addWidget(self.offset_input)

        self.help_btn = QPushButton("❓ Help / Guide", clicked=lambda: self.log("Pick RGB, Set Options, Start Detection"))
        self.save_btn = QPushButton("Save Config", clicked=self.save_config)
        l.addWidget(self.help_btn); l.addWidget(self.save_btn)

        self.proc_status = QLabel("Valorant: ⛔ | Vanguard: ⛔")
        self.status_label = QLabel("Status: Ready")
        l.addWidget(self.proc_status); l.addWidget(self.status_label)

        self.console_output = QPlainTextEdit(); self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background:#111; color:#0f0; font-family:Consolas;"); self.console_output.setFixedHeight(140)
        l.addWidget(QLabel("Console Output:")); l.addWidget(self.console_output)

        if self.username.lower() == "dev":
            self.keyauth_user = QLineEdit(placeholderText="KeyAuth Username")
            self.keyauth_pass = QLineEdit(placeholderText="KeyAuth Password")
            self.keyauth_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.keyauth_btn = QPushButton("🔐 Login with KeyAuth", clicked=self.load_keyauth_direct)
            l.addWidget(QLabel("KeyAuth Developer Login:"))
            l.addWidget(self.keyauth_user)
            l.addWidget(self.keyauth_pass)
            l.addWidget(self.keyauth_btn)

    def load_keyauth_direct(self):
        try:
            with open("temp_keyauth.py", "r", encoding="utf-8") as f:
                code = f.read()

            name = re.search(r'name\s*=\s*"([^"]+)"', code).group(1)
            ownerid = re.search(r'ownerid\s*=\s*"([^"]+)"', code).group(1)
            version = re.search(r'version\s*=\s*"([^"]+)"', code).group(1)

            ka_user = self.keyauth_user.text()
            ka_pass = self.keyauth_pass.text()
            if not ka_user or not ka_pass:
                self.log("KeyAuth fields cannot be empty.")
                return

            spec = importlib.util.spec_from_file_location("temp_keyauth", "temp_keyauth.py")
            temp_keyauth = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(temp_keyauth)

            success, msg = temp_keyauth.load_keyauth(ka_user, ka_pass, name, ownerid, version)
            self.log(msg)
            if success:
                QMessageBox.information(self, "✅ KeyAuth", msg)
                self.keyauth_btn.setText("✅ Connected")
                self.keyauth_btn.setEnabled(False)
            else:
                QMessageBox.critical(self, "❌ KeyAuth", msg)
        except Exception as e:
            self.log(f"[KeyAuth] Failed: {e}")
            QMessageBox.critical(self, "KeyAuth Error", str(e))

    def log(self, msg):
        t = time.strftime("%H:%M:%S")
        self.console_output.appendPlainText(f"[{t}] {msg}")

    def refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(p.device)

    def connect_arduino(self):
        try:
            port = self.port_combo.currentText()
            self.serial_port = serial.Serial(port, 9600, timeout=1)
            self.log(f"Arduino connected to {port}")
        except Exception as e:
            self.log(f"Connection error: {str(e)}")

    def auto_upload(self):
        port = self.port_combo.currentText()
        cmd = ["arduino-cli", "upload", "--port", port, "--fqbn", "arduino:avr:uno", "sketch"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.log("Upload: " + result.stdout.strip())
            if result.stderr:
                self.log("Error: " + result.stderr.strip())
        except Exception as e:
            self.log(f"Auto upload failed: {str(e)}")

    def enable_rgb_picker(self):
        self.pick_rgb_active = True
        self.ctrl_pressed = False
        self.rgb_label.setText("RGB: Waiting for CTRL...")

    def check_rgb(self):
        if self.pick_rgb_active and keyboard.is_pressed('ctrl'):
            if not self.ctrl_pressed:
                self.ctrl_pressed = True
                x, y = pyautogui.position()
                picked = pyautogui.screenshot().getpixel((x, y))
                self.color2, self.color1 = self.color1, list(picked)
                self.config["rgb"] = self.color1
                self.rgb_label.setText(f"RGB: {self.color1}")
                self.color1_box.setStyleSheet(f"background-color: rgb({','.join(map(str, self.color1))}); border: 2px solid #00f;")
                self.color2_box.setStyleSheet(f"background-color: rgb({','.join(map(str, self.color2))}); border: 1px solid white;")
                self.log(f"RGB picked: {self.color1}")
                self.pick_rgb_active = False
        elif not keyboard.is_pressed('ctrl'):
            self.ctrl_pressed = False

    def start_detection(self):
        if not self.detecting:
            self.detecting = True
            self.status_label.setText("Status: Detecting...")
            QTimer.singleShot(0, self.detection_loop)

    def stop_detection(self):
        self.detecting = False
        self.status_label.setText("Status: Stopped")

    def detection_loop(self):
        if not self.detecting: return
        screen = pyautogui.size()
        cx, cy = screen.width // 2, screen.height // 2
        fov = int(self.fov_combo.currentText())
        rgb, tol = self.config["rgb"], self.config["tolerance"]
        delay = self.delay_slider.value() / 1000
        ox, oy = map(int, self.offset_input.text().split(","))
        region = (cx - fov, cy - fov, fov * 2, fov * 2)
        shot = pyautogui.screenshot(region=region)
        for x in range(shot.width):
            for y in range(shot.height):
                r, g, b = shot.getpixel((x, y))
                if all(abs(c1 - c2) < tol for c1, c2 in zip((r, g, b), rgb)):
                    tx, ty = region[0] + x + ox, region[1] + y + oy
                    self.log(f"RGB Match at ({tx},{ty})")
                    if self.safe_cb.isChecked():
                        self.log(f"[SAFE] Would shoot at ({tx},{ty})")
                    elif self.serial_port:
                        if self.trig_cb.isChecked():
                            self.serial_port.write(b'1')
                        if self.aim_cb.isChecked():
                            self.serial_port.write(f"MOVE:{tx},{ty}\n".encode())
                    time.sleep(delay)
                    break
            else:
                continue
            break
        if self.detecting:
            QTimer.singleShot(10, self.detection_loop)

    def save_config(self):
        self.config.update({
            "delay": self.delay_slider.value(),
            "fov": int(self.fov_combo.currentText()),
            "resolution": self.resolution_input.text(),
            "smoothing": float(self.smooth_input.text()),
            "offset": list(map(int, self.offset_input.text().split(",")))
        })
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f)
        self.log("Config saved.")

    def setup_timers(self):
        self.timer = QTimer(); self.timer.timeout.connect(self.update_overlay); self.timer.timeout.connect(self.check_processes)
        self.timer.start(2000)
        self.rgb_timer = QTimer(); self.rgb_timer.timeout.connect(self.check_rgb)
        self.rgb_timer.start(100)

    def update_overlay(self):
        self.overlay.fov = int(self.fov_combo.currentText())
        self.overlay.aim_on = self.aim_cb.isChecked()
        self.overlay.trig_on = self.trig_cb.isChecked()
        self.overlay.crosshair_on = self.cross_cb.isChecked()
        self.overlay.repaint()

    def check_processes(self):
        names = [p.name().lower() for p in psutil.process_iter()]
        val = any("valorant.exe" in n for n in names)
        vgc = any("vgc.exe" in n for n in names)
        self.proc_status.setText(f"Valorant: {'✅' if val else '⛔'} | Vanguard: {'✅' if vgc else '⛔'}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    stack = QStackedWidget()

    def on_login_success(username):
        gui = AimbotGUI(username)
        stack.addWidget(gui)
        stack.setCurrentWidget(gui)

    login = LoginPage(stack, on_login_success)
    stack.addWidget(login)
    stack.setFixedSize(460, 920)
    stack.show()
    sys.exit(app.exec())