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


class CalibrationWidget(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        
        # Variáveis de Estado para Calibração Complexa
        self.calib_state = "IDLE" # IDLE, REST_WAIT, RESTING, PEAK_WAIT, PEAKING
        self.calib_timer_count = 0
        self.calib_sensor_target = ""
        self.calib_rest_val = 0.0
        self.calib_peak_val = 0.0
        self.temp_samples = []

        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Calibração Avançada 🎛️</h2>"))

        # Slider de Ajuste
        error_layout = QHBoxLayout()
        self.error_label = QLabel("Sensibilidade/Margem: 30%")
        self.error_slider = QSlider(Qt.Horizontal)
        self.error_slider.setRange(1, 99)
        self.error_slider.setValue(30)
        self.error_slider.valueChanged.connect(lambda: self.error_label.setText(f"Sensibilidade/Margem: {self.error_slider.value()}%"))
        error_layout.addWidget(self.error_label)
        error_layout.addWidget(self.error_slider)
        layout.addLayout(error_layout)

        layout.addWidget(QLabel("<b>SENSORES:</b>"))

        # Botões Flex (Calibração Simples)
        hbox_flex = QHBoxLayout()
        for i in range(1, 5):
            btn = QPushButton(f"Flex {i}")
            btn.clicked.connect(lambda _, idx=i: self.calibrate_simple(f"flex_dedo{idx}"))
            hbox_flex.addWidget(btn)
        layout.addLayout(hbox_flex)

        # Botões IMU (Calibração Complexa para Giroscópio)
        hbox_imu = QHBoxLayout()
        
        # Giroscópio com fluxo especial
        btn_gyro = QPushButton("Giroscópio (Dinâmico)")
        btn_gyro.setStyleSheet("background-color: #440044; color: cyan;")
        btn_gyro.clicked.connect(self.start_gyro_calibration_sequence)
        hbox_imu.addWidget(btn_gyro)

        # Outros simples
        for sensor in ["magnetometro_esq", "acelerometro_esq"]:
            btn = QPushButton(f"{sensor.split('_')[0].title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate_simple(s))
            hbox_imu.addWidget(btn)
        layout.addLayout(hbox_imu)

        layout.addWidget(QLabel("Console:"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        layout.addWidget(self.sensor_output)

        back_btn = QPushButton("⬅️ Voltar")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)

        self.setLayout(layout)
        
        # Timer da Interface (10Hz = 100ms)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(100)

    # --- Calibração Simples (Snapshot) ---
    def calibrate_simple(self, sensor_name):
        if not self.parent.comm.connected:
            self.log("ERRO: Conecte a luva primeiro!", "red")
            return

        val = self.parent.get_sensor_value_for_calibration(sensor_name)
        margem = self.error_slider.value() / 100.0
        
        # Para Flex, o 'trigger' geralmente é quando dobra (valor aumenta ou diminui dependendo do circuito)
        # Aqui assumimos um limiar simples
        limite = val * (1 - margem) 
        
        self.parent.calibrated_values[sensor_name] = limite
        self.log(f"<b>{sensor_name}</b> calibrado: Ref={val:.1f} | Limite={limite:.1f}")

    # --- Calibração Dinâmica (Repouso -> Pico) ---
    def start_gyro_calibration_sequence(self):
        if not self.parent.comm.connected:
            self.log("ERRO: Conecte a luva primeiro!", "red")
            return
            
        self.calib_sensor_target = "giroscopio_esq"
        self.calib_state = "REST_WAIT"
        self.calib_timer_count = 30 # 3 segundos (30 * 100ms)
        self.log("<b>PASSO 1:</b> Mantenha a mão IMÓVEL para calibrar o repouso...", "yellow")

    def process_calibration_state(self):
        if self.calib_state == "IDLE":
            return

        # Obtém magnitude atual
        raw = self.parent.comm.get_latest_data()
        curr_val = raw["gyro_magnitude"]

        # 1. Contagem regressiva para Repouso
        if self.calib_state == "REST_WAIT":
            self.calib_timer_count -= 1
            if self.calib_timer_count <= 0:
                self.calib_state = "RESTING"
                self.calib_timer_count = 20 # 2 segundos capturando média
                self.temp_samples = []
                self.log(">>> CAPTURANDO REPOUSO...", "lime")
        
        # 2. Capturando Repouso (Média)
        elif self.calib_state == "RESTING":
            self.temp_samples.append(curr_val)
            self.calib_timer_count -= 1
            if self.calib_timer_count <= 0:
                self.calib_rest_val = sum(self.temp_samples) / len(self.temp_samples)
                self.log(f"Repouso capturado: {self.calib_rest_val:.2f}", "white")
                
                self.calib_state = "PEAK_WAIT"
                self.calib_timer_count = 20 # 2 segundos para preparar
                self.log("<b>PASSO 2:</b> Prepare-se para fazer o MOVIMENTO MÁXIMO...", "yellow")

        # 3. Preparando para Pico
        elif self.calib_state == "PEAK_WAIT":
            self.calib_timer_count -= 1
            if self.calib_timer_count <= 0:
                self.calib_state = "PEAKING"
                self.calib_timer_count = 30 # 3 segundos de janela de movimento
                self.calib_peak_val = 0.0
                self.log(">>> MOVA AGORA!!! (Capturando Pico)", "red")

        # 4. Capturando Pico (Máximo)
        elif self.calib_state == "PEAKING":
            if curr_val > self.calib_peak_val:
                self.calib_peak_val = curr_val
            
            self.calib_timer_count -= 1
            if self.calib_timer_count <= 0:
                # FIM - Calcular Threshold
                rest = self.calib_rest_val
                peak = self.calib_peak_val
                sensibilidade = self.error_slider.value() / 100.0
                
                # Fórmula: O limiar é o repouso + X% da diferença para o pico
                threshold = rest + ((peak - rest) * sensibilidade)
                
                self.parent.calibrated_values[self.calib_sensor_target] = threshold
                
                self.log(f"<b>CALIBRAÇÃO CONCLUÍDA!</b>", "cyan")
                self.log(f"Repouso: {rest:.1f} | Pico: {peak:.1f}", "white")
                self.log(f"Limiar Definido: {threshold:.1f} (Sensibilidade {int(sensibilidade*100)}%)", "lime")
                self.calib_state = "IDLE"

    def update_loop(self):
        # Processa máquina de estados
        self.process_calibration_state()
        
        # Atualiza display apenas se conectado
        if not self.parent.comm.connected: return
        
        # Feedback visual em tempo real no rodapé (opcional)
        # Se não estiver calibrando, mostra dados live normalmente?
        if self.calib_state == "IDLE":
            data = self.parent.get_mapped_data()
            # Mostra apenas um resumo para não poluir se tiver muita coisa
            # Ou mantém o update anterior se preferir
            pass 

    def log(self, text, color="white"):
        self.sensor_output.append(f"<span style='color:{color}'>{text}</span>")
        # Auto-scroll
        self.sensor_output.moveCursor(QTextCursor.End)

    def go_back(self):
        self.timer.stop()
        self.parent.show_main_window()


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
