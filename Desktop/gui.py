import math
import json
from emulator import Emulator
from instruments import Guitar, Drum
from communication import Communication
import cv2          
import mediapipe as mp 
import numpy as np  
from PyQt5.QtGui import QImage, QPixmap


from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QSlider,
    QCheckBox, QStackedWidget, QFormLayout,
    QScrollArea, QLineEdit, QMessageBox,
    QGroupBox, QFrame, QTabWidget, QMainWindow
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot, pyqtSignal


class MainApplication(QMainWindow):
    """
    Classe principal da Interface (QMainWindow).
    Monta as abas e gerencia os timers e a lógica.
    """


    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 800, 700)

        self.sensor_mappings = {}
        self.load_mappings_from_file()

        # --- Instancia a lógica ---
        self.communication = Communication()
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # --- Cria QTabWidget ---
        self.tabs = QTabWidget(self)
        self.tabs.setMovable(True)

        # --- Instancia as abas ---
        self.instructions_tab = InstructionsScreen(self)
        self.main_menu_tab = MainMenuScreen(self)
        self.calibration_tab = CalibrationScreen(self)

        # --- Adiciona as abas ---
        self.tabs.addTab(self.instructions_tab, "🏠 Início")
        self.tabs.addTab(self.main_menu_tab, "⚙️ Controle")
        self.tabs.addTab(self.calibration_tab, "🎛️ Calibração")

        self.setCentralWidget(self.tabs)

        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- Timers Globais ---
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500)

        self._check_network_status()
        self.on_tab_changed(self.tabs.currentIndex())

    def on_tab_changed(self, index):
        """ Inicia/para o timer da aba de calibração quando ela é selecionada/desselecionada """
        current_widget = self.tabs.widget(index)

        if current_widget == self.calibration_tab:
            self.calibration_tab.start_timer()
        else:
            self.calibration_tab.stop_timer()

    # ============ Funções de Controle (colam a Lógica na UI) ============
    def load_mappings_from_file(self):
        try:
            with open('sensor_mappings.json', 'r') as f:
                self.sensor_mappings = json.load(f)
                print("Mapeamentos carregados de 'sensor_mappings.json'")
        except FileNotFoundError:
            print("Arquivo 'sensor_mappings.json' não encontrado. Começando com mapeamentos vazios.")
            self.sensor_mappings = {}
        except json.JSONDecodeError:
            print("Erro ao decodificar 'sensor_mappings.json'. Começando com mapeamentos vazios.")
            self.sensor_mappings = {}

    def save_mappings_to_file(self):
        try:
            with open('sensor_mappings.json', 'w') as f:
                json.dump(self.sensor_mappings, f, indent=4)
                print(f"Mapeamentos salvos em 'sensor_mappings.json'")
        except Exception as e:
            print(f"Erro ao salvar mapeamentos: {e}")

    def toggle_glove_connection(self):
        self.communication.toggle_connection()

    def _check_network_status(self):
        status = self.communication.get_status_message()
        is_connected = self.communication.connected
        # Passa o status para a aba de controle
        self.main_menu_tab.update_connection_status(is_connected, status)

    def update_glove_data(self):
        """ Pega dados da lógica e passa para a UI e processamento """
        raw_data = self.communication.get_latest_data()

        # Passa dados para o terminal na aba "Controle"
        self.main_menu_tab.update_sensor_data(raw_data)

        logical_data = {}
        if self.communication.connected:
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")
                key_prefix = mapping.get("key_prefix")

                if raw_key in raw_data:
                    logical_data[action] = raw_data[raw_key]
                elif key_prefix and raw_data.get(f"{key_prefix}ax") is not None:
                    logical_data[action] = {
                        "ax": raw_data.get(f"{key_prefix}ax", 0),
                        "ay": raw_data.get(f"{key_prefix}ay", 0),
                        "az": raw_data.get(f"{key_prefix}az", 0)
                    }

        if logical_data:
            # Passa dados para processamento da Guitarra
            self.guitar.process_data(
                logical_data,
                self.sensor_mappings,
                self.emulator
            )

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False
        event.accept()


class Screen(QWidget):
    """ 
    Classe base para todas as 'telas' da aplicação. 
    Agora ela é uma 'Aba' (Tab).
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent


class InstructionsScreen(Screen):
    """ Tela de Instruções (Aba 'Início'). """
    def __init__(self, parent):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20) 
        layout.setSpacing(15)
        layout.addWidget(QLabel("<h2>Bem-vindo ao Air Band 🤘</h2>"))
        layout.addWidget(QLabel("Instruções 📝"))

        instructions_text = """
        Este aplicativo permite emular uma Guitarra (com a luva) ou uma Bateria (com a câmera).

        <b>Guitarra (Luva):</b>
        <ol>
            <li><b>Conecte seu PC ao Wi-Fi da luva (SSID: ALuvaQueTePariu).</b></li>
            <li>Na aba 'Controle', clique em 'Conectar à Luva'.</li>
            <li>Vá para a aba 'Calibração'.</li>
            <li>Clique em "Calibrar Dedo 1" e siga as instruções (Repouso, Meio, Completo).</li>
            <li>Para "Batidas", clique em "Batida (Giroscópio)", depois "INICIAR GRAVAÇÃO", faça o movimento, e clique "PARAR".</li>
            <li>O app irá <b>auto-detectar</b> qual sensor você usou.</li>
            <li>Os mapeamentos são salvos automaticamente.</li>
            <li>Retorne à aba 'Controle' e toque!</li>
        </ol>

        <b>Bateria (Câmera):</b>
        <ol>
            <li>Posicione-se em frente à câmera.</li>
            <li>Na aba 'Controle', clique em 'Ver Retorno da Câmera'.</li>
        </ol>
        """
        layout.addWidget(QLabel(instructions_text))

        layout.addStretch()

        self.continue_btn = QPushButton("Ir para a Aba de Controle ➡️")
        self.continue_btn.clicked.connect(
            lambda: self.main_app.tabs.setCurrentWidget(self.main_app.main_menu_tab)
        )
        layout.addWidget(self.continue_btn)

        self.setLayout(layout)


class CalibrationScreen(Screen):
    """
    Tela de Calibração (Aba 'Calibração').
    """
    def __init__(self, parent):
        super().__init__(parent)

        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        
        # --- AQUI ESTAVA O ERRO: Adicionado "Batida (Giroscópio)" na lista ---
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Batida (Giroscópio)"
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

        # --- Tela 0: Menu de Calibração ---
        self.main_menu_widget = self._create_main_menu_widget()
        self.stack.addWidget(self.main_menu_widget)

        # --- Tela 1: Wizard de Captura ---
        self.wizard_widget = self._create_wizard_widget()
        self.stack.addWidget(self.wizard_widget)

        # --- Área de Dados Brutos (Sempre visível) ---
        main_layout.addWidget(QLabel("<b>Dados Brutos (Tempo Real):</b>"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        self.sensor_output.setFixedHeight(150)
        main_layout.addWidget(self.sensor_output)

        self.setLayout(main_layout)

        # Timer para atualizar dados
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)

    def _create_main_menu_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

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

            btn = QPushButton(f"Calibrar {action}")
            btn.clicked.connect(lambda _, a=action: self.start_calibration_wizard(a))

            hbox.addWidget(label)
            hbox.addStretch()
            hbox.addWidget(btn)
            actions_layout.addLayout(hbox)

        layout.addWidget(actions_group)
        layout.addStretch()

        back_btn = QPushButton("⬅️ Voltar ao Controle")
        back_btn.clicked.connect(
            lambda: self.main_app.tabs.setCurrentWidget(self.main_app.main_menu_tab)
        )
        layout.addWidget(back_btn)
        return widget

    def _create_wizard_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self.wizard_title = QLabel("Calibrando Ação...")
        self.wizard_title.setStyleSheet("font-size: 18px; color: #00FFFF;")

        self.wizard_instruction = QLabel("Siga as instruções e clique em 'Capturar'.")
        self.wizard_instruction.setStyleSheet("font-size: 14px;")

        self.wizard_capture_btn = QPushButton("Capturar")
        self.wizard_capture_btn.clicked.connect(self.process_wizard_step)

        self.wizard_cancel_btn = QPushButton("Cancelar")
        self.wizard_cancel_btn.clicked.connect(self.cancel_wizard)

        layout.addWidget(self.wizard_title)
        layout.addWidget(self.wizard_instruction)
        layout.addStretch()
        layout.addWidget(self.wizard_capture_btn)
        layout.addWidget(self.wizard_cancel_btn)
        return widget

    def start_timer(self):
        self.timer.start(100)
        self.update_calibration_status_labels()

    def stop_timer(self):
        self.timer.stop()

    def update_sensor_data(self):
        raw_data = self.main_app.communication.get_latest_data()
        if not raw_data:
            self.sensor_output.setHtml("<span style='color:#FF4444;'>Sem dados... conecte a luva.</span>")
            return

        texto = ""
        for key, value in sorted(raw_data.items()):
            if isinstance(value, (float)):
                texto += f"<span style='color:#00FFFF;'>{key}:</span> {value:.2f}\n"
            else:
                texto += f"<span style='color:#00FFFF;'>{key}:</span> {value}\n"
        self.sensor_output.setHtml(texto)

        if self.is_recording_peak:
            rest_data = self.temp_snapshots.get("rest", {})
            if not rest_data:
                print("Erro: Gravação de pico iniciada sem dados de repouso.")
                self.is_recording_peak = False
                return

            sensor_prefixes = ["gyro_"]
            for prefix in sensor_prefixes:
                try:
                    current_mag = math.sqrt(
                        float(raw_data.get(f"{prefix}ax", 0))**2 +
                        float(raw_data.get(f"{prefix}ay", 0))**2 +
                        float(raw_data.get(f"{prefix}az", 0))**2
                    )
                    rest_mag = math.sqrt(
                        float(rest_data.get(f"{prefix}ax", 0))**2 +
                        float(rest_data.get(f"{prefix}ay", 0))**2 +
                        float(rest_data.get(f"{prefix}az", 0))**2
                    )
                    current_deviation = abs(current_mag - rest_mag)

                    if current_deviation > self.current_peak_magnitude:
                        self.current_peak_magnitude = current_deviation
                        self.current_peak_snapshot = raw_data.copy()
                except (ValueError, TypeError):
                    continue 

    def update_calibration_status_labels(self):
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                key = self.main_app.sensor_mappings[action].get("key",
                    self.main_app.sensor_mappings[action].get("key_prefix", "N/A")
                )
                label.setText(f"<b>{action}:</b> <span style='color:#00FF00;'>[OK: {key}]</span>")
            else:
                label.setText(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")

    def start_calibration_wizard(self, action_name):
        if not self.main_app.communication.connected:
            QMessageBox.warning(self, "Erro", "Conecte a luva antes de calibrar.")
            return

        self.current_calibration_action = action_name
        self.current_calibration_step = 1
        self.temp_snapshots = {}
        self.update_wizard_ui()
        self.stack.setCurrentWidget(self.wizard_widget)

    def update_wizard_ui(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        self.wizard_title.setText(f"Calibrando: {action}")

        if "Dedo" in action:
            if step == 1:
                self.wizard_instruction.setText("1/3: Mantenha o dedo em <b>REPOUSO</b> (solto) e clique em 'Capturar'.")
                self.wizard_capture_btn.setText("Capturar Repouso")
            if step == 2:
                self.wizard_instruction.setText("2/3: Mantenha o dedo <b>MEIO PRESSIONADO</b> e clique em 'Capturar'.")
                self.wizard_capture_btn.setText("Capturar Meio")
            if step == 3:
                self.wizard_instruction.setText("3/3: Mantenha o dedo <b>COMPLETAMENTE PRESSIONADO</b> e clique em 'Capturar'.")
                self.wizard_capture_btn.setText("Capturar Completo")

        elif "Batida" in action:
            if step == 1:
                self.wizard_instruction.setText("1/2: Mantenha a mão em <b>REPOUSO</b> e clique em 'Capturar Repouso'.")
                self.wizard_capture_btn.setText("Capturar Repouso")
            if step == 2:
                self.wizard_instruction.setText("2/2: Prepare-se para a batida.\n\nClique em 'INICIAR' para começar a gravar.")
                self.wizard_capture_btn.setText("INICIAR GRAVAÇÃO")
            if step == 3:
                self.wizard_instruction.setText("<b>GRAVANDO...</b>\n\nFaça o movimento de batida (ex: palhetada) uma ou mais vezes.\n\nClique 'PARAR' quando terminar.")
                self.wizard_capture_btn.setText("PARAR GRAVAÇÃO")

    def process_wizard_step(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        snapshot = self.main_app.communication.get_latest_data()

        if not snapshot and step == 1:
            QMessageBox.warning(self, "Erro", "Luva desconectada no meio da calibração.")
            self.cancel_wizard()
            return

        if "Dedo" in action:
            if step == 1: self.temp_snapshots["rest"] = snapshot
            if step == 2: self.temp_snapshots["half"] = snapshot
            if step == 3:
                self.temp_snapshots["full"] = snapshot
                self.finish_finger_calibration()
                return

        elif "Batida" in action:
            if step == 1:
                self.temp_snapshots["rest"] = snapshot
                self.current_peak_snapshot = snapshot.copy() 
                self.current_calibration_step = 2
            elif step == 2:
                self.current_peak_snapshot = self.temp_snapshots["rest"].copy()
                self.current_peak_magnitude = -1.0
                self.is_recording_peak = True
                self.current_calibration_step = 3
            elif step == 3:
                self.is_recording_peak = False
                self.temp_snapshots["peak"] = self.current_peak_snapshot
                self.finish_strum_calibration() 
                return

        if self.current_calibration_step < 3:
            self.current_calibration_step += 1
        self.update_wizard_ui()

    def _find_best_sensor(self, snap_a, snap_b, sensor_prefix_filter):
        max_delta = -1
        detected_key = None
        for key in snap_a.keys():
            if not any(key.startswith(prefix) for prefix in sensor_prefix_filter):
                continue
            try:
                val_a = float(snap_a.get(key, 0.0))
                val_b = float(snap_b.get(key, 0.0))
                delta = abs(val_a - val_b)
            except ValueError:
                continue 
            if delta > max_delta:
                max_delta = delta
                detected_key = key
        return detected_key

    def _find_best_sensor_group(self, snap_a, snap_b, sensor_prefix_filter):
        max_delta_mag = -1
        detected_prefix = None
        for prefix in sensor_prefix_filter:
            try:
                mag_a = math.sqrt(
                    float(snap_a.get(f"{prefix}ax", 0))**2 +
                    float(snap_a.get(f"{prefix}ay", 0))**2 +
                    float(snap_a.get(f"{prefix}az", 0))**2
                )
                mag_b = math.sqrt(
                    float(snap_b.get(f"{prefix}ax", 0))**2 +
                    float(snap_b.get(f"{prefix}ay", 0))**2 +
                    float(snap_b.get(f"{prefix}az", 0))**2
                )
                delta_mag = abs(mag_b - mag_a)
                if delta_mag > max_delta_mag:
                    max_delta_mag = delta_mag
                    detected_prefix = prefix
            except (ValueError, TypeError):
                continue
        return detected_prefix

    def finish_finger_calibration(self):
        action = self.current_calibration_action
        detected_key = self._find_best_sensor(
            self.temp_snapshots["rest"],
            self.temp_snapshots["full"],
            sensor_prefix_filter=["adc_"]
        )
        if detected_key:
            mapping = {
                "key": detected_key,
                "rest": self.temp_snapshots["rest"][detected_key],
                "half": self.temp_snapshots["half"][detected_key],
                "full": self.temp_snapshots["full"][detected_key]
            }
            self.main_app.sensor_mappings[action] = mapping
            self.main_app.save_mappings_to_file()
            QMessageBox.information(self, "Sucesso", f"Calibração para '{action}' salva!\nSensor detectado: {detected_key}")
        else:
            QMessageBox.warning(self, "Erro", "Nenhuma variação de sensor ADC detectada. Tente novamente.")
        self.cancel_wizard()

    def finish_strum_calibration(self):
        action = self.current_calibration_action
        detected_prefix = self._find_best_sensor_group(
            self.temp_snapshots["rest"], 
            self.temp_snapshots["peak"],
            sensor_prefix_filter=["gyro_"] 
        )
        if detected_prefix:
            mapping = {
                "key_prefix": detected_prefix,
                "rest": {
                    "ax": self.temp_snapshots["rest"].get(f"{detected_prefix}ax", 0),
                    "ay": self.temp_snapshots["rest"].get(f"{detected_prefix}ay", 0),
                    "az": self.temp_snapshots["rest"].get(f"{detected_prefix}az", 0)
                },
                "peak": {
                    "ax": self.temp_snapshots["peak"].get(f"{detected_prefix}ax", 0),
                    "ay": self.temp_snapshots["peak"].get(f"{detected_prefix}ay", 0),
                    "az": self.temp_snapshots["peak"].get(f"{detected_prefix}az", 0)
                }
            }
            self.main_app.sensor_mappings[action] = mapping
            self.main_app.save_mappings_to_file()
            QMessageBox.information(self, "Sucesso", f"Calibração para '{action}' salva!\nSensor detectado: {detected_prefix} (Aceleração)")
        else:
            QMessageBox.warning(self, "Erro", "Nenhuma variação de sensor de Aceleração detectada. Tente novamente.")
        self.cancel_wizard()

    def cancel_wizard(self):
        self.stack.setCurrentWidget(self.main_menu_widget)
        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        self.is_recording_peak = False 
        self.current_peak_snapshot = {}
        self.current_peak_magnitude = -1.0
        self.update_calibration_status_labels()


class MainMenuScreen(Screen):
    """ Tela Principal (Aba 'Controle'). """
    def __init__(self, parent):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20) 

        # --- Coluna da Esquerda (Controles) ---
        left_column = QVBoxLayout()
        left_column.setSpacing(15) 

        # --- Bloco de Configuração ---
        config_group = QGroupBox("Configuração")
        config_layout = QFormLayout(config_group) 
        config_layout.setSpacing(10)

        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(["Guitarra (Luva)", "Bateria (Camera)"])
        config_layout.addRow(QLabel("<b>Instrumento:</b>"), self.instrument_combo)

        self.output_combo = QComboBox()
        self.output_combo.addItems(["Teclado", "Joystick"])
        config_layout.addRow(QLabel("<b>Saída:</b>"), self.output_combo)

        left_column.addWidget(config_group)

        # --- Bloco de Controles da Guitarra ---
        guitar_group = QGroupBox("Controles da Guitarra 🎸")
        guitar_layout = QVBoxLayout(guitar_group)
        guitar_layout.setSpacing(10)

        self.connect_glove_btn = QPushButton("Conectar à Luva")
        self.connect_glove_btn.clicked.connect(self.main_app.toggle_glove_connection)
        guitar_layout.addWidget(self.connect_glove_btn)

        self.calibrate_btn = QPushButton("Ir para Calibração") 
        self.calibrate_btn.clicked.connect(
            lambda: self.main_app.tabs.setCurrentWidget(self.main_app.calibration_tab)
        )
        guitar_layout.addWidget(self.calibrate_btn)

        self.status_label = QLabel("Status Luva: Desconectado")
        guitar_layout.addWidget(self.status_label)

        left_column.addWidget(guitar_group)

        # --- Bloco de Controles da Bateria ---
        drum_group = QGroupBox("Controles da Bateria 🥁")
        drum_layout = QVBoxLayout(drum_group)

        self.camera_feedback_btn = QPushButton("Ver Retorno da Câmera (Bateria)")
        self.camera_feedback_btn.clicked.connect(self.toggle_camera_feedback) 
        drum_layout.addWidget(self.camera_feedback_btn)

        left_column.addWidget(drum_group)

        # --- Bloco Geral ---
        general_group = QGroupBox("Geral")
        general_layout = QVBoxLayout(general_group)

        self.instructions_btn = QPushButton("Ver Instruções 📝")
        self.instructions_btn.clicked.connect(
            lambda: self.main_app.tabs.setCurrentWidget(self.main_app.instructions_tab)
        )
        general_layout.addWidget(self.instructions_btn)

        left_column.addWidget(general_group)
        left_column.addStretch() 

        # --- Coluna da Direita (Debug) ---
        right_column = QVBoxLayout()

        self.debug_group = QGroupBox("Terminal de Debug (Luva)")
        self.debug_group.setCheckable(True)  
        self.debug_group.setChecked(False) 

        debug_layout = QVBoxLayout(self.debug_group)

        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        debug_layout.addWidget(self.sensor_output)

        right_column.addWidget(self.debug_group)

        self.camera_widget = CameraWidget(self) 
        self.camera_widget.camera_data_signal.connect(self.update_camera_data)

        camera_frame = QGroupBox("Retorno da Câmera 🥁")
        camera_layout = QVBoxLayout(camera_frame)
        camera_layout.addWidget(self.camera_widget)

        right_column.addWidget(camera_frame)

        right_column.addStretch() 

        main_layout.addLayout(left_column, 1)
        main_layout.addLayout(right_column, 1)

        self.setLayout(main_layout)

    def update_sensor_data(self, raw_data):
        if not self.debug_group.isChecked():
            return
        texto = ""
        for key, value in sorted(raw_data.items()):
            if isinstance(value, (float)):
                texto += f"<span style='color:#00FF00;'>{key}:</span> {value:.2f}\n"
            else:
                texto += f"<span style='color:#00FF00;'>{key}:</span> {value}\n"
        self.sensor_output.setHtml(texto)

    def update_connection_status(self, is_connected, status_message):
        self.status_label.setText(f"Status Luva: {status_message}")
        if is_connected:
            self.connect_glove_btn.setText("Desconectar Luva")
            if self.debug_group.isChecked():
                self.sensor_output.clear()
        else:
            self.connect_glove_btn.setText("Conectar à Luva")
            if self.debug_group.isChecked():
                self.sensor_output.setHtml(
                    f"<span style='color:#FF4444; font-weight:bold;'>⚠️ {status_message}</span>"
                )

    def toggle_camera_feedback(self):
        # Verifica se a câmera está atualmente aberta (cap é o objeto cv2.VideoCapture)
        is_camera_on = self.camera_widget.cap is not None and self.camera_widget.cap.isOpened()

        if is_camera_on:
            # Se a câmera está LIGADA, vamos DESLIGAR
            self.camera_widget.stop_camera()
            self.camera_feedback_btn.setText("Ver Retorno da Câmera (Bateria)")
            # Opcional: Desliga a luz de fundo do QLabel
            self.camera_widget.video_label.setStyleSheet("") 

        else:
            # Se a câmera está DESLIGADA, vamos LIGAR
            self.camera_widget.start_camera()
            self.camera_feedback_btn.setText("Parar Retorno da Câmera (Bateria)")
            # Opcional: Adiciona um fundo escuro/preto para dar a impressão de que está ativo/pronto
            self.camera_widget.video_label.setStyleSheet("background-color: black;")

    def update_camera_data(self, data):
        """ Recebe os dados da câmera e os exibe no terminal de debug. """
        # Só atualiza se o terminal de debug estiver checado
        if not self.debug_group.isChecked():
            return

        texto = "<span style='color:#00FFFF;'>--- DADOS DA BATERIA (CÂMERA) ---</span>\n"

        # Formata os ângulos
        texto += f"<span style='color:#FFFF00;'>Vert. Esq:</span> {data['Angulo_Esq_Vert']:.1f}° (Lim: {data['Limite_Vert']:.1f}°)\n"
        texto += f"<span style='color:#FFFF00;'>Vert. Dir:</span> {data['Angulo_Dir_Vert']:.1f}°\n"
        texto += f"<span style='color:#00FF00;'>Cotov. Esq:</span> {data['Angulo_Esq_Cotovelo']:.1f}°\n"
        texto += f"<span style='color:#00FF00;'>Cotov. Dir:</span> {data['Angulo_Dir_Cotovelo']:.1f}°\n"

        # Formata os hits
        hit_color = "#FF4444" if data['Baterias_Ativadas'] != "Nenhuma" else "#AAAAAA"
        texto += f"<span style='color:{hit_color}; font-weight:bold;'>HITS:</span> {data['Baterias_Ativadas']}\n"

        # Atualiza o terminal
        self.sensor_output.setHtml(texto)

# =======================================================================
# --- LÓGICA DA CÂMERA INTEGRADA (PyQt + OpenCV + MediaPipe) ---
# =======================================================================


# Função auxiliar de cálculo de ângulo (do seu camera.py)
def calcular_angulo(a, b, c):
    angulo = math.degrees(
        math.atan2(c[1] - b[1], c[0] - b[0]) -
        math.atan2(a[1] - b[1], a[0] - b[0])
    )
    angulo = abs(angulo)
    if angulo > 180:
        angulo = 360 - angulo
    return angulo


def linha_tracejada(img, p1, p2, cor, espessura=1, tamanho_tracejado=10):
    p1 = np.array(p1)
    p2 = np.array(p2)
    dist = np.linalg.norm(p1 - p2)
    direcao = (p2 - p1) / dist
    for i in range(0, int(dist), tamanho_tracejado * 2):
        inicio = tuple(np.int32(p1 + direcao * i))
        fim = tuple(np.int32(p1 + direcao * (i + tamanho_tracejado)))
        cv2.line(img, inicio, fim, cor, espessura)


class CameraWidget(QWidget):
    """
    Widget que exibe o feed da câmera usando OpenCV e QTimer,
    processando o frame com MediaPipe.
    """
    camera_data_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.w, self.h = 640, 480 # Resolução padrão
        self.setFixedSize(self.w, self.h)

        # --- Configuração do Layout e Label ---
        layout = QVBoxLayout(self)
        self.video_label = QLabel("Aguardando Câmera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(self.w, self.h)
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        # --- Configuração da Câmera e MediaPipe ---
        self.cap = None
        self.mp_pose = mp.solutions.pose
        self.pose_processor = self.mp_pose.Pose(
            min_detection_confidence=0.5, 
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

        self.circulos = [
            {'center': [0.1, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
            {'center': [0.3, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
            {'center': [0.7, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
            {'center': [0.9, 0.8], 'raio': 40, 'cor': (255, 0, 0)}
        ] # Posições normalizadas e raio em pixels

        self.limite_angulo_vert = 130.0
        self.limite_angulo_cotovelo = 150.0
        self.delta_limite = 2.0

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def start_camera(self):
        """ Inicializa a captura da câmera e o timer. """
        if self.cap is None or not self.cap.isOpened():
            # Tenta abrir o dispositivo 0
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.video_label.setText("Erro ao abrir a câmera (cv2.VideoCapture(0))")
                return

        self.timer.start(30) # Aprox. 33ms para 30 FPS

    def stop_camera(self):
        """ Para o timer e libera o objeto de captura. """
        self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
            self.video_label.setText("Câmera Desligada")

    # Dentro da classe CameraWidget...

    def to_pixel(self, landmark, w, h):
        """ Converte coordenadas normalizadas do MediaPipe para pixels. """
        return int(landmark.x * w), int(landmark.y * h)

    @pyqtSlot()
    def update_frame(self):
        """ Lê, processa com MediaPipe (incluindo lógica de ângulos) e exibe. """
        ret, frame = self.cap.read()
        if not ret:
            self.stop_camera()
            return

        # 1. Pré-processamento
        frame = cv2.flip(frame, 1) # Espelha a imagem
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False

        # 2. Processamento MediaPipe
        results = self.pose_processor.process(image)

        # 3. Desenho e Lógica
        image.flags.writeable = True
        # Converter para BGR para que o OpenCV possa desenhar nele (incluindo o texto)
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        h, w, _ = image.shape
        pulso_esq = pulso_dir = (-100, -100) # Inicializa fora da tela

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            # Obtém Landmarks
            l_sh = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value], w, h)
            l_el = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value], w, h)
            l_wr = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value], w, h)
            r_sh = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value], w, h)
            r_el = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.RIGHT_ELBOW.value], w, h)
            r_wr = self.to_pixel(landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST.value], w, h)

            pulso_esq, pulso_dir = l_wr, r_wr # Atualiza a posição dos pulsos

            # CÁLCULOS DE ÂNGULO (Cotovelo e Vertical)
            ang_esq = calcular_angulo(l_sh, l_el, l_wr)
            ang_dir = calcular_angulo(r_sh, r_el, r_wr)

            l_vert = (l_sh[0], l_sh[1] - 150) # Ponto auxiliar vertical (fixo)
            r_vert = (r_sh[0], r_sh[1] - 150)
            ang_esq_vert = calcular_angulo(l_el, l_sh, l_vert)
            ang_dir_vert = calcular_angulo(r_el, r_sh, r_vert)

            # LÓGICA DE COR (Limites)
            cor_esq_vert = (0, 255, 128)
            cor_dir_vert = (255, 128, 0)

            if ang_esq_vert < self.limite_angulo_vert: # Se o ângulo está dentro do limite de toque
                cor_esq_vert = (0, 0, 255) # Cor de 'toque'
            if ang_dir_vert < self.limite_angulo_vert:
                cor_dir_vert = (0, 0, 255)

            cor_esq_cot = (0, 255, 0)
            cor_dir_cot = (0, 255, 255)
            if ang_esq > self.limite_angulo_cotovelo:
                cor_esq_cot = (255, 0, 255)
            if ang_dir > self.limite_angulo_cotovelo:
                cor_dir_cot = (255, 0, 255)

            # DESENHO DE LINHAS
            cv2.line(image, l_sh, l_el, (0, 255, 0), 3)
            cv2.line(image, l_el, l_wr, (0, 255, 0), 3)
            cv2.line(image, r_sh, r_el, (0, 255, 255), 3)
            cv2.line(image, r_el, r_wr, (0, 255, 255), 3)

            linha_tracejada(image, l_sh, l_vert, (200, 200, 200), espessura=1)
            linha_tracejada(image, r_sh, r_vert, (200, 200, 200), espessura=1)

            # DESENHO DE CÍRCULOS (Landmarks)
            cv2.circle(image, l_sh, 8, cor_esq_vert, -1)
            cv2.circle(image, l_el, 8, cor_esq_cot, -1)
            cv2.circle(image, l_wr, 8, (0, 200, 200), -1)
            cv2.circle(image, r_sh, 8, cor_dir_vert, -1)
            cv2.circle(image, r_el, 8, cor_dir_cot, -1)
            cv2.circle(image, r_wr, 8, (0, 200, 255), -1)

            # TEXTO DOS ÂNGULOS
            cv2.putText(image, f"{ang_esq:.1f}°", (l_el[0]+10, l_el[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_cot, 2)
            cv2.putText(image, f"{ang_esq_vert:.1f}°", (l_sh[0]+10, l_sh[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_vert, 2)
            cv2.putText(image, f"{ang_dir:.1f}°", (r_el[0]+10, r_el[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_cot, 2)
            cv2.putText(image, f"{ang_dir_vert:.1f}°", (r_sh[0]+10, r_sh[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_vert, 2)

            # TEXTO DE DEBUG NO CANTO
            cv2.putText(image, f"Vert Esq (ombro): {ang_esq_vert:.1f}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_vert, 2)
            cv2.putText(image, f"Vert Dir (ombro): {ang_dir_vert:.1f}", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_vert, 2)
            cv2.putText(image, f"Limite vertical: {self.limite_angulo_vert:.1f} graus", (10, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # DESENHO DOS TAMBORES VIRTUAIS
        for c in self.circulos:
            cx = int(c['center'][0] * w) # Usa o centro normalizado
            cy = int(c['center'][1] * h)
            cor = c['cor']

            # Checa a colisão do pulso com o tambor (adapte esta lógica de pulso para a sua simulação real)
            for pulso in [pulso_esq, pulso_dir]:
                dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                if dist <= c['raio']:
                    cor = (0, 0, 255) # Cor de 'hit'

        hits = [] # Inicializa a lista de hits UMA VEZ antes do loop
        for i, c in enumerate(self.circulos):
            cx = int(c['center'][0] * w) 
            cy = int(c['center'][1] * h)
            cor = c['cor'] # Cor padrão

            is_hit = False
            # Verifica se algum pulso (punho esquerdo ou direito) está dentro do raio
            for pulso in [pulso_esq, pulso_dir]:
                # Só checa se o pulso foi detectado (coordenadas positivas)
                if pulso[0] > 0 and pulso[1] > 0:
                    dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                    if dist <= c['raio']:
                        is_hit = True
                        break

            if is_hit:
                hits.append(f"Drum {i+1}") # Coleta o hit para o signal
                cor = (0, 0, 255) # Cor de 'hit' para o desenho (TODOS os hits)

            # Desenha o círculo no frame
            cv2.circle(image, (cx, cy), c['raio'], cor, 2)

        camera_data = {
            "Angulo_Esq_Cotovelo": ang_esq,
            "Angulo_Dir_Cotovelo": ang_dir,
            "Angulo_Esq_Vert": ang_esq_vert,
            "Angulo_Dir_Vert": ang_dir_vert,
            "Baterias_Ativadas": ", ".join(hits) if hits else "Nenhuma",
            "Limite_Vert": self.limite_angulo_vert,
            "Camera_Ativa": True
        }
        self.camera_data_signal.emit(camera_data)

        # 4. Exibir no Qt (agora convertendo o frame BGR para RGB novamente)
        rgb_display = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        bytes_per_line = 3 * w
        qt_image = QImage(rgb_display.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Redimensiona o pixmap para o tamanho do label
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), 
            Qt.KeepAspectRatio
        )
        self.video_label.setPixmap(scaled_pixmap)

    def closeEvent(self, event):
        """ Garante que a câmera seja liberada ao fechar o widget. """
        self.stop_camera()
        super().closeEvent(event)
