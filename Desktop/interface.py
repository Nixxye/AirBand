import sys
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QSlider
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QTextCursor

# Importa a classe do arquivo separado
from communication import Communication


# ===================== MAIN APP =====================
class AirBandApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘 (UDP Real)")
        self.setGeometry(300, 200, 600, 700)
        
        self.comm = Communication()
        self.calibrated_values = {}

        self.connect_btn = QPushButton("Conectar à Luva")
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        self.calibrate_btn = QPushButton("Calibrar Sensores")
        self.calibrate_btn.clicked.connect(self.open_calibration)
        
        self.status_label = QLabel("Status: Parado")
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Controle:"))
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.calibrate_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Dados Recebidos:"))
        layout.addWidget(self.sensor_output)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)

        self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #ddd; }
            QPushButton { background-color: #333; color: #0ff; padding: 10px; border-radius: 5px; font-weight: bold;}
            QPushButton:hover { background-color: #0ff; color: #000; }
            QTextEdit { background-color: #000; color: #0f0; font-family: monospace; }
        """)

    def open_calibration(self):
        self.calibration_screen = CalibrationWidget(self)
        self.setCentralWidget(self.calibration_screen)

    def show_main_window(self):
        self.setCentralWidget(None)
        self.__init__() 
        self.comm.connected = True 
        self.comm.toggle_connection() 
        self.show()

    def toggle_connection(self):
        self.comm.toggle_connection()
        if self.comm.connected:
            self.connect_btn.setText("Desconectar")
            self.status_label.setText("Status: Ouvindo porta 8888...")
        else:
            self.connect_btn.setText("Conectar à Luva")
            self.status_label.setText("Status: Parado")

    def get_mapped_data(self):
        raw = self.comm.get_latest_data()
        return {
            "flex_dedo1": raw["adc_v32"],
            "flex_dedo2": raw["adc_v33"],
            "flex_dedo3": raw["adc_v34"],
            "flex_dedo4": raw["adc_v35"],
            "acelerometro_esq": (raw["acc_x"], raw["acc_y"], raw["acc_z"]),
            "giroscopio_esq":   (raw["gyro_x"], raw["gyro_y"], raw["gyro_z"]),
            "magnetometro_esq": (raw["mag_mx"], raw["mag_my"], raw["mag_mz"]),
            "acc_magnitude": raw["acc_magnitude"],
            "gyro_magnitude": raw["gyro_magnitude"],
        }

    def get_sensor_value_for_calibration(self, sensor_name):
        raw = self.comm.get_latest_data()
        if "acelerometro" in sensor_name: return raw["acc_magnitude"]
        elif "giroscopio" in sensor_name: return raw["gyro_magnitude"]
        elif "magnetometro" in sensor_name: 
            return math.sqrt(raw["mag_mx"]**2 + raw["mag_my"]**2 + raw["mag_mz"]**2)
        mapping = self.get_mapped_data()
        return float(mapping.get(sensor_name, 0.0))

    def update_ui(self):
        if not self.comm.connected: return
        raw = self.comm.get_latest_data()
        txt = "<b>MÃO ESQUERDA (Dados Reais):</b><br>"
        txt += f"Flex 1: {raw['adc_v32']:.0f}<br>"
        txt += f"Acc Mag: <span style='color:yellow'>{raw['acc_magnitude']:.1f}</span><br>"
        txt += f"Gyr Mag: <span style='color:cyan'>{raw['gyro_magnitude']:.1f}</span><br>"
        
        # Mostra se o gatilho está ativo baseado na calibração
        if "giroscopio_esq" in self.calibrated_values:
            limite = self.calibrated_values["giroscopio_esq"]
            status = "ATIVADO!" if raw["gyro_magnitude"] > limite else "..."
            txt += f"Trigger Gyro ({limite:.1f}): <b>{status}</b><br>"

        self.sensor_output.setHtml(txt)
        self.status_label.setText(f"Status: {self.comm.network_status_message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AirBandApp()
    window.show()
    sys.exit(app.exec_())
