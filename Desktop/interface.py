import sys
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QSlider
)
from PyQt5.QtCore import QTimer, Qt

from communication import Communication


class CalibrationWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Calibração Real 🎛️</h2>"))

        # Taxa de erro
        error_layout = QHBoxLayout()
        self.error_label = QLabel("Margem: 5%")
        self.error_slider = QSlider(Qt.Horizontal)
        self.error_slider.setRange(0, 50)
        self.error_slider.setValue(5)
        self.error_slider.valueChanged.connect(lambda: self.error_label.setText(f"Margem: {self.error_slider.value()}%"))
        error_layout.addWidget(self.error_label)
        error_layout.addWidget(self.error_slider)
        layout.addLayout(error_layout)

        layout.addWidget(QLabel("<b>SENSORES DISPONÍVEIS:</b>"))

        # Botões Flex
        hbox_flex = QHBoxLayout()
        for i in range(1, 5):
            btn = QPushButton(f"Flex {i}")
            btn.clicked.connect(lambda _, idx=i: self.calibrate(f"flex_dedo{idx}"))
            hbox_flex.addWidget(btn)
        layout.addLayout(hbox_flex)

        # Botões IMU
        hbox_imu = QHBoxLayout()
        for sensor in ["magnetometro_esq", "acelerometro_esq", "giroscopio_esq"]:
            btn = QPushButton(f"{sensor.split('_')[0].title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate(s))
            hbox_imu.addWidget(btn)
        layout.addLayout(hbox_imu)

        layout.addWidget(QLabel("Feedback:"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        layout.addWidget(self.sensor_output)

        back_btn = QPushButton("⬅️ Voltar")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(200)

    def calibrate(self, sensor_name):
        if not self.parent.comm.connected:
            self.sensor_output.append("<span style='color:red'>ERRO: Conecte a luva primeiro!</span>")
            return

        val = self.parent.get_sensor_value_for_calibration(sensor_name)
        taxa = self.error_slider.value() / 100.0
        limite = val * (1 - taxa)

        self.parent.calibrated_values[sensor_name] = limite

        self.sensor_output.append(
            f"<b style='color:cyan'>{sensor_name}</b>: Ref={val:.1f} | "
            f"Limite={limite:.1f} (Margem {self.error_slider.value()}%)"
        )

    def update_display(self):
        if not self.parent.comm.connected: return
        data = self.parent.get_mapped_data()
        msg = "<b>Valores em Tempo Real:</b><br>"
        msg += f"Flex 1: {data['flex_dedo1']:.0f}<br>"
        # Mostra magnitude para o usuário entender o que está sendo calibrado
        acc_vec = data['acelerometro_esq']
        acc_mag = math.sqrt(acc_vec[0]**2 + acc_vec[1]**2 + acc_vec[2]**2)
        msg += f"Acc Mag: {acc_mag:.1f}<br>"
        self.sensor_output.setHtml(msg)

    def go_back(self):
        self.timer.stop()
        self.parent.show_main_window()


class AirBandApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
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
        """Mapeia os nomes técnicos do communication.py para os nomes da GUI."""
        raw = self.comm.get_latest_data()

        return {
            "flex_dedo1": raw["adc_v32"],
            "flex_dedo2": raw["adc_v33"],
            "flex_dedo3": raw["adc_v34"],
            "flex_dedo4": raw["adc_v35"],
            # Tuplas (x, y, z)
            "acelerometro_esq": (raw["acc_x"], raw["acc_y"], raw["acc_z"]),
            "giroscopio_esq":   (raw["gyro_x"], raw["gyro_y"], raw["gyro_z"]),
            "magnetometro_esq": (raw["mag_mx"], raw["mag_my"], raw["mag_mz"]),
            # Dados extras já calculados
            "acc_magnitude": raw["acc_magnitude"],
            "gyro_magnitude": raw["gyro_magnitude"],

            "acelerometro_dir": (0,0,0), 
            "giroscopio_dir": (0,0,0),
            "magnetometro_dir": (0,0,0)
        }

    def get_sensor_value_for_calibration(self, sensor_name):
        """
        Retorna o valor escalar para calibração.
        Se for sensor 3D, usa a magnitude pré-calculada pelo Communication.
        """
        raw = self.comm.get_latest_data()

        if "acelerometro" in sensor_name:
            return raw["acc_magnitude"]
        elif "giroscopio" in sensor_name:
            return raw["gyro_magnitude"]
        elif "magnetometro" in sensor_name:
            # Magnetômetro geralmente não se calibra por magnitude simples dessa forma, 
            # mas mantendo lógica consistente:
            mx, my, mz = raw["mag_mx"], raw["mag_my"], raw["mag_mz"]
            return math.sqrt(mx**2 + my**2 + mz**2)

        # Flex sensores
        mapping = self.get_mapped_data()
        return float(mapping.get(sensor_name, 0.0))

    def update_ui(self):
        if not self.comm.connected: return

        raw = self.comm.get_latest_data()

        txt = "<b>MÃO ESQUERDA (Dados Reais):</b><br>"
        txt += f"Flex 1: {raw['adc_v32']:.0f}<br>"
        txt += f"Acc (XYZ): {raw['acc_x']}, {raw['acc_y']}, {raw['acc_z']}<br>"
        txt += f"Acc Mag: <span style='color:yellow'>{raw['acc_magnitude']:.1f}</span><br>"
        txt += f"Gyr (XYZ): {raw['gyro_x']}, {raw['gyro_y']}, {raw['gyro_z']}<br>"
        txt += f"Gyr Mag: <span style='color:cyan'>{raw['gyro_magnitude']:.1f}</span><br>"

        self.sensor_output.setHtml(txt)
        self.status_label.setText(f"Status: {self.comm.network_status_message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AirBandApp()
    window.show()
    sys.exit(app.exec_())
