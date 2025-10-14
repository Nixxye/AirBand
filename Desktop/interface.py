import sys
import random
try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QSlider
)
from PyQt5.QtCore import QTimer, Qt


# ===================== Tela de calibração =====================
class CalibrationWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Calibração dos Sensores 🎛️</h2>"))

        # taxa de erro
        error_layout = QHBoxLayout()
        self.error_label = QLabel("Margem: 5%")
        self.error_slider = QSlider(Qt.Horizontal)
        self.error_slider.setRange(0, 30)
        self.error_slider.setValue(5)
        self.error_slider.setTickInterval(5)
        self.error_slider.setTickPosition(QSlider.TicksBelow)
        self.error_slider.valueChanged.connect(self.update_error_label)
        error_layout.addWidget(self.error_label)
        error_layout.addWidget(self.error_slider)
        layout.addLayout(error_layout)

        layout.addWidget(QLabel("<b>MÃO ESQUERDA:</b>"))

        # Botões de calibração — Mão Esquerda
        for i in range(1, 5):
            btn = QPushButton(f"Dedo {i}")
            btn.clicked.connect(lambda _, idx=i: self.calibrate(f"flex_dedo{idx}"))
            layout.addWidget(btn)

        for sensor in ["magnetometro_esq", "acelerometro_esq", "giroscopio_esq"]:
            btn = QPushButton(f"{sensor.replace('_', ' ').title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate(s))
            layout.addWidget(btn)

        layout.addWidget(QLabel("<b>MÃO DIREITA:</b>"))

        # Botões de calibração — Mão Direita
        for sensor in ["magnetometro_dir", "acelerometro_dir", "giroscopio_dir"]:
            btn = QPushButton(f"{sensor.replace('_', ' ').title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate(s))
            layout.addWidget(btn)

        layout.addWidget(QLabel("Dados dos Sensores:"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        layout.addWidget(self.sensor_output)

        back_btn = QPushButton("⬅️ Voltar")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)

        self.setLayout(layout)

        # Timer para atualizar dados
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_sensor_data)
        self.timer.start(1000)

    def update_error_label(self):
        self.error_label.setText(f"Margem: {self.error_slider.value()}%")

    def calibrate(self, sensor_name):
        if not self.parent.connected:
            self.sensor_output.append(
                "<span style='color:#FF4444;'>⚠️ Não é possível calibrar — luva desconectada.</span>"
            )
            return

        taxa = self.error_slider.value() / 100.0
        val = self.parent.get_random_sensor_value(sensor_name)
        limite = val * (1 - taxa)
        self.parent.calibrated_values[sensor_name] = limite
        self.sensor_output.append(
            f"<span style='color:#00FFFF;'>"
            f"{sensor_name.replace('_', ' ').title()} calibrado com valor {val:.2f} "
            f"(limite {limite:.2f}, erro {self.error_slider.value()}%)</span><br>"
        )

    def update_sensor_data(self):
        # Verifica se a luva está conectada
        if not self.parent.connected:
            self.sensor_output.setHtml(
                "<span style='color:#FF4444; font-weight:bold;'>⚠️ Luva desconectada — conecte para visualizar os sensores.</span>"
            )
            return

        # Gera e mostra dados normalmente
        data = self.parent.generate_sensor_data()
        texto = (
            "<b><span style='color:#00FF00;'>MÃO ESQUERDA:</span></b><br>"
            + "".join([f"<span>Dedo {i+1}: {data[f'flex_dedo{i+1}']}</span><br>" for i in range(4)])
            + f"Magnetômetro: X={data['magnetometro_esq'][0]}, Y={data['magnetometro_esq'][1]}, Z={data['magnetometro_esq'][2]}<br>"
            + f"Acelerômetro: X={data['acelerometro_esq'][0]}, Y={data['acelerometro_esq'][1]}, Z={data['acelerometro_esq'][2]}<br>"
            + f"Giroscópio: X={data['giroscopio_esq'][0]}, Y={data['giroscopio_esq'][1]}, Z={data['giroscopio_esq'][2]}<br>"
            "<hr>"
            "<b><span style='color:#00FF00;'>MÃO DIREITA:</span></b><br>"
            + f"Magnetômetro: X={data['magnetometro_dir'][0]}, Y={data['magnetometro_dir'][1]}, Z={data['magnetometro_dir'][2]}<br>"
            + f"Acelerômetro: X={data['acelerometro_dir'][0]}, Y={data['acelerometro_dir'][1]}, Z={data['acelerometro_dir'][2]}<br>"
            + f"Giroscópio: X={data['giroscopio_dir'][0]}, Y={data['giroscopio_dir'][1]}, Z={data['giroscopio_dir'][2]}<br>"
        )
        self.sensor_output.setHtml(texto)

    def go_back(self):
        self.timer.stop()
        self.parent.show_main_window()


# ===================== Tela principal =====================
class AirBandApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 600, 700)

        self.calibrated_values = {}

        # ----- Widgets principais -----
        self.instrument_label = QLabel("Selecione o instrumento:")
        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(["Guitarra", "Bateria"])

        self.output_label = QLabel("Selecione a saída:")
        self.output_combo = QComboBox()
        self.output_combo.addItems(["Teclado", "Joystick"])

        self.connect_btn = QPushButton("Conectar à Luva")
        self.connect_btn.clicked.connect(self.connect_glove)

        self.calibrate_btn = QPushButton("Calibrar Sensores")
        self.calibrate_btn.clicked.connect(self.open_calibration)

        self.status_label = QLabel("Status: Desconectado")

        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.instrument_label)
        layout.addWidget(self.instrument_combo)
        layout.addWidget(self.output_label)
        layout.addWidget(self.output_combo)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.calibrate_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Dados dos Sensores:"))
        layout.addWidget(self.sensor_output)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_sensor_data)
        self.connected = False

        self.gamepad = vg.VX360Gamepad() if HAS_VGAMEPAD else None

        self.setStyleSheet("""
            QMainWindow { background-color: #111; color: white; }
            QPushButton {
                background-color: #222;
                color: #FF00FF;
                font-size: 14px;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #FF00FF;
                color: black;
            }
            QComboBox {
                background-color: #333;
                color: #00FFFF;
                padding: 4px;
            }
            QLabel { color: #FFFFFF; font-weight: bold; }
            QTextEdit {
                background-color: #000;
                color: white;
                font-family: monospace;
            }
        """)

    # ============ troca de telas ============
    def open_calibration(self):
        self.calibration_screen = CalibrationWidget(self)
        self.setCentralWidget(self.calibration_screen)

    def show_main_window(self):
        self.setCentralWidget(None)
        self.__init__()
        self.show()

    # ============ simulação de sensores ============
    def generate_sensor_data(self):
        data = {}
        for i in range(1, 5):
            data[f"flex_dedo{i}"] = random.randint(0, 1023)

        def rand3d(a, b):
            return (round(random.uniform(a, b), 2),
                    round(random.uniform(a, b), 2),
                    round(random.uniform(a, b), 2))

        for s in ["magnetometro_esq", "magnetometro_dir",
                  "acelerometro_esq", "acelerometro_dir",
                  "giroscopio_esq", "giroscopio_dir"]:
            data[s] = rand3d(-50, 50)
        return data

    def get_random_sensor_value(self, sensor_name):
        if "flex" in sensor_name:
            return random.randint(0, 1023)
        else:
            return random.uniform(-50, 50)

    # ============ conexão com glove ============
    def connect_glove(self):
        if self.connected:
            self.timer.stop()
            self.status_label.setText("Status: Desconectado")
            self.connect_btn.setText("Conectar à Luva")
            self.connected = False
        else:
            self.status_label.setText("Status: Conectado")
            self.connect_btn.setText("Desconectar")
            self.timer.start(1000)
            self.connected = True

    def update_sensor_data(self):
        data = self.generate_sensor_data()
        texto = (
            "<b><span style='color:#00FF00;'>MÃO ESQUERDA:</span></b><br>"
            + "".join([f"<span>Dedo {i+1}: {data[f'flex_dedo{i+1}']}</span><br>" for i in range(4)])
            + f"Magnetômetro: X={data['magnetometro_esq'][0]}, Y={data['magnetometro_esq'][1]}, Z={data['magnetometro_esq'][2]}<br>"
            + f"Acelerômetro: X={data['acelerometro_esq'][0]}, Y={data['acelerometro_esq'][1]}, Z={data['acelerometro_esq'][2]}<br>"
            + f"Giroscópio: X={data['giroscopio_esq'][0]}, Y={data['giroscopio_esq'][1]}, Z={data['giroscopio_esq'][2]}<br>"
            "<hr>"
            "<b><span style='color:#00FF00;'>MÃO DIREITA:</span></b><br>"
            + f"Magnetômetro: X={data['magnetometro_dir'][0]}, Y={data['magnetometro_dir'][1]}, Z={data['magnetometro_dir'][2]}<br>"
            + f"Acelerômetro: X={data['acelerometro_dir'][0]}, Y={data['acelerometro_dir'][1]}, Z={data['acelerometro_dir'][2]}<br>"
            + f"Giroscópio: X={data['giroscopio_dir'][0]}, Y={data['giroscopio_dir'][1]}, Z={data['giroscopio_dir'][2]}<br>"
        )
        self.sensor_output.setHtml(texto)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AirBandApp()
    window.show()
    sys.exit(app.exec_())
