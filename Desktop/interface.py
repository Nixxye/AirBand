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


class CalibrationScreen(QWidget):
    """
    Tela de Calibração com Wizard.
    - Dedos: 3 Etapas (Repouso, Meio, Cheio) -> Mantido!
    - Batida: 2 Etapas (Repouso/Gravidade, Movimento) -> Adaptado para nova lógica.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent

        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        
        # Ações disponíveis
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Batida (Mestra)", "Batida (Escrava)"
        ]

        self.is_recording_peak = False
        self.current_peak_snapshot = {}
        self.current_peak_magnitude = -1.0

        # --- Layout Principal ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        # Tela 0: Menu
        self.main_menu_widget = self._create_main_menu_widget()
        self.stack.addWidget(self.main_menu_widget)

        # Tela 1: Wizard
        self.wizard_widget = self._create_wizard_widget()
        self.stack.addWidget(self.wizard_widget)

        # Área de Dados
        main_layout.addWidget(QLabel("<b>Dados Brutos (Tempo Real):</b>"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        self.sensor_output.setFixedHeight(150)
        main_layout.addWidget(self.sensor_output)

        self.setLayout(main_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)

    def _create_main_menu_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h2>Mapeamento e Calibração 🎛️</h2>"))
        layout.addWidget(QLabel("Selecione a Ação para Calibrar:"))

        self.action_labels = {}
        actions_group = QGroupBox("Ações Lógicas")
        actions_layout = QVBoxLayout()
        actions_group.setLayout(actions_layout)

        for action in self.logical_actions:
            hbox = QHBoxLayout()
            label = QLabel(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")
            self.action_labels[action] = label

            btn = QPushButton(f"Calibrar")
            btn.clicked.connect(lambda _, a=action: self.start_calibration_wizard(a))

            hbox.addWidget(label)
            hbox.addStretch()
            hbox.addWidget(btn)
            actions_layout.addLayout(hbox)

        layout.addWidget(actions_group)
        layout.addStretch()
        return widget

    def _create_wizard_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.wizard_title = QLabel("Calibrando...")
        self.wizard_title.setStyleSheet("font-size: 18px; color: #00FFFF;")
        
        self.wizard_instruction = QLabel("Instruções...")
        self.wizard_instruction.setStyleSheet("font-size: 14px;")
        
        self.wizard_capture_btn = QPushButton("Capturar")
        self.wizard_capture_btn.clicked.connect(self.process_wizard_step)
        self.wizard_capture_btn.setStyleSheet("font-size: 14px; padding: 10px;")

        self.wizard_cancel_btn = QPushButton("Cancelar")
        self.wizard_cancel_btn.clicked.connect(self.cancel_wizard)

        layout.addWidget(self.wizard_title)
        layout.addWidget(self.wizard_instruction)
        layout.addStretch()
        layout.addWidget(self.wizard_capture_btn)
        layout.addWidget(self.wizard_cancel_btn)
        return widget

    def start_timer(self):
        self.timer.start(30) # 33Hz
        self.update_calibration_status_labels()

    def stop_timer(self):
        self.timer.stop()

    def update_sensor_data(self):
        raw_data = self.main_app.communication.get_latest_data()
        if not raw_data: return

        # Display Debug
        texto = ""
        for key, value in sorted(raw_data.items()):
            if "adc" in key or "gyro" in key or "slave" in key:
                val_str = f"{value:.2f}" if isinstance(value, float) else f"{value}"
                texto += f"<span style='color:#00FFFF;'>{key}:</span> {val_str}\n"
        self.sensor_output.setHtml(texto)

        # Lógica de Captura de Pico (Para Batida)
        if self.is_recording_peak:
            # Detecta qual prefixo usar baseado na ação atual
            prefix = "slave_" if "Escrava" in self.current_calibration_action else "gyro_"
            
            # Helper de Magnitude
            def get_mag(d):
                ax = d.get(f"{prefix}ax", d.get(f"{prefix}gx", 0))
                ay = d.get(f"{prefix}ay", d.get(f"{prefix}gy", 0))
                az = d.get(f"{prefix}az", d.get(f"{prefix}gz", 0))
                return math.sqrt(ax**2 + ay**2 + az**2)

            # Usa o Rest salvo para subtrair (Delta)
            rest_snap = self.temp_snapshots.get("rest", {})
            
            # Aceleração Atual e Repouso
            curr_ax = raw_data.get(f"{prefix}ax", 0)
            rest_ax = rest_snap.get(f"{prefix}ax", 0)
            # (Simplificado: Magnitude do Delta direto)
            
            # Se a magnitude atual for maior que o pico registrado, salva
            mag = get_mag(raw_data)
            if mag > self.current_peak_magnitude:
                self.current_peak_magnitude = mag
                self.current_peak_snapshot = raw_data.copy()

    def update_calibration_status_labels(self):
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                data = self.main_app.sensor_mappings[action]
                info = data.get("key", data.get("key_prefix", "OK"))
                label.setText(f"<b>{action}:</b> <span style='color:#00FF00;'>[OK: {info}]</span>")
            else:
                label.setText(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")

    # =========================================================================
    # LÓGICA DO WIZARD
    # =========================================================================

    def start_calibration_wizard(self, action_name):
        if not self.main_app.communication.connected:
            QMessageBox.warning(self, "Erro", "Conecte a luva antes de calibrar.")
            return

        self.current_calibration_action = action_name
        self.current_calibration_step = 1
        self.temp_snapshots = {}
        self.is_recording_peak = False
        
        self.update_wizard_ui()
        self.stack.setCurrentWidget(self.wizard_widget)

    def update_wizard_ui(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        self.wizard_title.setText(f"Calibrando: {action}")

        # --- LÓGICA DE DEDOS (MANTIDA 3 ETAPAS) ---
        if "Dedo" in action:
            if step == 1:
                self.wizard_instruction.setText("1/3: Dedo em <b>REPOUSO</b> (Esticado).")
                self.wizard_capture_btn.setText("Capturar Repouso")
            elif step == 2:
                self.wizard_instruction.setText("2/3: Dedo <b>MEIO CURVADO</b>.")
                self.wizard_capture_btn.setText("Capturar Meio")
            elif step == 3:
                self.wizard_instruction.setText("3/3: Dedo <b>TOTALMENTE FECHADO</b>.")
                self.wizard_capture_btn.setText("Capturar Cheio")

        # --- LÓGICA DE BATIDA (ADAPTADA PARA NOVA LÓGICA) ---
        elif "Batida" in action:
            if step == 1:
                self.wizard_instruction.setText("1/2: <b>CALIBRAR GRAVIDADE</b>\n\nFique com a mão parada na posição de tocar.\nIsso define onde é 'Cima' e 'Baixo'.")
                self.wizard_capture_btn.setText("Capturar Gravidade (Repouso)")
            elif step == 2:
                self.wizard_instruction.setText("2/2: <b>DEFINIR FORÇA</b>\n\nClique em INICIAR e faça uma batida forte.\nO sistema vai gravar a intensidade máxima.")
                self.wizard_capture_btn.setText("INICIAR Captura de Movimento")
            elif step == 3:
                self.wizard_instruction.setText("<b>GRAVANDO MOVIMENTO...</b>\n\nFaça a batida agora!\nClique PARAR logo após.")
                self.wizard_capture_btn.setText("PARAR e Salvar")

    def process_wizard_step(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        snapshot = self.main_app.communication.get_latest_data()

        # --- DEDOS (MANTIDO) ---
        if "Dedo" in action:
            if step == 1: self.temp_snapshots["rest"] = snapshot
            if step == 2: self.temp_snapshots["half"] = snapshot
            if step == 3:
                self.temp_snapshots["full"] = snapshot
                self.finish_finger_calibration()
                return
            self.current_calibration_step += 1
            self.update_wizard_ui()

        # --- BATIDA (NOVA LÓGICA) ---
        elif "Batida" in action:
            if step == 1:
                # Captura Repouso (Vetor da Gravidade)
                self.temp_snapshots["rest"] = snapshot
                self.current_calibration_step = 2
                self.update_wizard_ui()
            
            elif step == 2:
                # Inicia Gravação de Pico
                self.current_peak_snapshot = snapshot # Inicializa
                self.current_peak_magnitude = 0
                self.is_recording_peak = True
                self.current_calibration_step = 3
                self.update_wizard_ui()
            
            elif step == 3:
                # Para Gravação e Finaliza
                self.is_recording_peak = False
                self.temp_snapshots["peak"] = self.current_peak_snapshot
                self.finish_strum_calibration()

    def finish_finger_calibration(self):
        """ Lógica original mantida para encontrar o melhor sensor ADC. """
        action = self.current_calibration_action
        
        # Encontra qual sensor ADC variou mais entre Repouso e Cheio
        best_key = None
        max_delta = -1
        
        rest = self.temp_snapshots["rest"]
        full = self.temp_snapshots["full"]
        
        for key in rest.keys():
            if "adc" in key:
                delta = abs(rest.get(key, 0) - full.get(key, 0))
                if delta > max_delta:
                    max_delta = delta
                    best_key = key
        
        if best_key and max_delta > 100: # Threshold mínimo de variação
            mapping = {
                "key": best_key,
                "rest": rest[best_key],
                "half": self.temp_snapshots["half"][best_key],
                "full": full[best_key]
            }
            self.main_app.sensor_mappings[action] = mapping
            self.main_app.save_mappings_to_file()
            QMessageBox.information(self, "Sucesso", f"Dedo Calibrado!\nSensor: {best_key}")
        else:
            QMessageBox.warning(self, "Falha", "Pouca variação detectada no sensor.")
        
        self.cancel_wizard()

    def finish_strum_calibration(self):
        """ Salva vetor de repouso (Gravidade) e limiar de força. """
        action = self.current_calibration_action
        
        prefix = "slave_" if "Escrava" in action else "gyro_" # "gyro_" na verdade pega o accel da mestra na logica principal
        
        # Helper para extrair vetor X,Y,Z
        def extract_vec(d):
            # Tenta accel primeiro, depois gyro
            return {
                "ax": d.get(f"{prefix}ax", d.get(f"{prefix}gx", 0)),
                "ay": d.get(f"{prefix}ay", d.get(f"{prefix}gy", 0)),
                "az": d.get(f"{prefix}az", d.get(f"{prefix}gz", 0))
            }
        
        rest_vec = extract_vec(self.temp_snapshots["rest"])
        
        # A magnitude máxima detectada durante o movimento
        # (Isso pode ser usado para definir sensibilidade dinâmica se quiser)
        peak_mag = self.current_peak_magnitude 

        mapping = {
            "key_prefix": prefix,
            "rest": rest_vec,    # CRÍTICO: Vetor da gravidade
            "peak_mag": peak_mag # Opcional: Para auto-ajuste de sensibilidade
        }
        
        self.main_app.sensor_mappings[action] = mapping
        self.main_app.save_mappings_to_file()
        
        QMessageBox.information(self, "Sucesso", f"Batida Calibrada!\nGravidade definida.")
        self.cancel_wizard()

    def cancel_wizard(self):
        self.stack.setCurrentWidget(self.main_menu_widget)
        self.is_recording_peak = False
        self.update_calibration_status_labels()

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
