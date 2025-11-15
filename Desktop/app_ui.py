# app_ui.py
import sys
import math
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QStackedWidget
)
from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QIcon

from qfluentwidgets import (
    FluentWindow, NavigationInterface, NavigationItemPosition, 
    PrimaryPushButton, PushButton, ComboBox, CheckBox, 
    TextEdit, MessageBox, FluentIcon, TitleLabel, BodyLabel,
    InfoBar, InfoBarPosition
)

# Importa a lógica do outro arquivo
from app_logic import Communication, Emulator, Guitar, Drum

# ===================================================================
# 2. CLASSES DE INTERFACE (UI)
# ===================================================================

class Screen(QWidget):
    """ Classe base para todas as 'telas' da aplicação. """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent 

class InstructionsScreen(Screen):
    """ Tela de Instruções (Tela Inicial). """
    def __init__(self, parent):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.addWidget(TitleLabel("Bem-vindo ao Air Band 🤘"))
        layout.addWidget(BodyLabel("Instruções 📝"))
        
        instructions_text = """
        Este aplicativo permite emular uma Guitarra (com a luva) ou uma Bateria (com a câmera).
        
        <b>Guitarra (Luva):</b>
        <ol>
            <li><b>Conecte seu PC ao Wi-Fi da luva (SSID: ALuvaQueTePariu).</b></li>
            <li>No menu principal, clique em 'Conectar à Luva'.</li>
            <li>Vá para a tela de Calibração.</li>
            <li>Clique em "Calibrar Dedo 1" e siga as instruções (Repouso, Meio, Completo).</li>
            <li>Para "Batidas", clique em "INICIAR GRAVAÇÃO", faça o movimento, e clique "PARAR".</li>
            <li>O app irá <b>auto-detectar</b> qual sensor você usou.</li>
            <li>Os mapeamentos são salvos automaticamente.</li>
            <li>Retorne ao menu e toque!</li>
        </ol>
        
        <b>Bateria (Câmera):</b>
        <ol>
            <li>Posicione-se em frente à câmera.</li>
            <li>No menu principal, clique em 'Ver Retorno da Câmera'.</li>
        </ol>
        """
        layout.addWidget(QLabel(instructions_text)) # QLabel ainda funciona bem para HTML
        
        layout.addStretch() 
        
        self.continue_btn = PrimaryPushButton("Ir para o Menu Principal ➡️")
        self.continue_btn.clicked.connect(self.main_app.show_main_menu_screen)
        layout.addWidget(self.continue_btn)
        
        self.setLayout(layout)

class CalibrationScreen(Screen):
    """ 
    Tela de Calibração estilo Wizard. 
    Usa um QStackedWidget interno para o wizard.
    """
    def __init__(self, parent):
        super().__init__(parent)
        
        # --- Estado do Wizard ---
        self.current_calibration_action = None 
        self.current_calibration_step = 0 
        self.temp_snapshots = {} 
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Batida para Baixo", "Batida para Cima"
        ]
        
        self.is_recording_peak = False
        self.current_peak_snapshot = {}
        self.current_peak_magnitude = -1.0

        # --- Layout Principal ---
        main_layout = QVBoxLayout(self)
        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        # --- Tela 0: Menu de Calibração ---
        self.main_menu_widget = self._create_main_menu_widget()
        self.stack.addWidget(self.main_menu_widget)
        
        # --- Tela 1: Wizard de Captura ---
        self.wizard_widget = self._create_wizard_widget()
        self.stack.addWidget(self.wizard_widget)

        # --- Área de Dados Brutos (Sempre visível) ---
        main_layout.addWidget(BodyLabel("Dados Brutos (Tempo Real):"))
        self.sensor_output = TextEdit(self)
        self.sensor_output.setReadOnly(True)
        self.sensor_output.setFixedHeight(150)
        main_layout.addWidget(self.sensor_output)
        
        self.setLayout(main_layout)

        # Timer para atualizar dados
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)

    def _create_main_menu_widget(self):
        """ Cria o widget com a lista de botões de calibração. """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(TitleLabel("Mapeamento e Calibração 🎛️"))
        layout.addWidget(BodyLabel("Selecione a Ação para Calibrar:"))

        self.action_labels = {} 

        for action in self.logical_actions:
            hbox = QHBoxLayout()
            label = QLabel(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")
            self.action_labels[action] = label
            
            btn = PushButton(f"Calibrar {action}")
            btn.clicked.connect(lambda _, a=action: self.start_calibration_wizard(a))
            
            hbox.addWidget(label)
            hbox.addStretch()
            hbox.addWidget(btn)
            layout.addLayout(hbox)

        layout.addStretch()
        # Botão de voltar (agora desnecessário com a navegação, mas mantido)
        # self.back_btn = PushButton("⬅️ Voltar ao Menu")
        # self.back_btn.clicked.connect(self.go_back)
        # layout.addWidget(self.back_btn)
        return widget

    def _create_wizard_widget(self):
        """ Cria o widget para o wizard de captura passo-a-passo. """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.wizard_title = TitleLabel("Calibrando Ação...")
        self.wizard_instruction = BodyLabel("Siga as instruções e clique em 'Capturar'.")
        
        self.wizard_capture_btn = PrimaryPushButton("Capturar")
        self.wizard_capture_btn.clicked.connect(self.process_wizard_step)
        
        self.wizard_cancel_btn = PushButton("Cancelar")
        self.wizard_cancel_btn.clicked.connect(self.cancel_wizard)

        layout.addWidget(self.wizard_title)
        layout.addWidget(self.wizard_instruction)
        layout.addStretch()
        layout.addWidget(self.wizard_capture_btn)
        layout.addWidget(self.wizard_cancel_btn)
        return widget
        
    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start(100)
        self.update_calibration_status_labels()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()
        self.cancel_wizard() # Garante que o wizard pare ao trocar de tela

    def update_sensor_data(self):
        """ Atualiza o terminal de dados brutos E grava o pico se estiver no modo. """
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
            if not rest_data: # Segurança
                print("Erro: Gravação de pico iniciada sem dados de repouso.")
                self.is_recording_peak = False
                return

            sensor_prefixes = ["gyro_", "mag_"]
            
            for prefix in sensor_prefixes:
                if prefix != "gyro_":
                    continue
                
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
        """ Atualiza os labels do menu principal (ex: [OK: adc_v32]). """
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                key = self.main_app.sensor_mappings[action].get("key", 
                    self.main_app.sensor_mappings[action].get("key_prefix", "N/A"))
                label.setText(f"<b>{action}:</b> <span style='color:#00FF00;'>[OK: {key}]</span>")
            else:
                label.setText(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")

    # --- Lógica do Wizard (ATUALIZADA) ---

    def start_calibration_wizard(self, action_name):
        if not self.main_app.communication.connected:
            # Substitui QMessageBox
            w = MessageBox("Erro de Conexão", "Conecte a luva antes de calibrar.", self)
            w.exec()
            return
            
        self.current_calibration_action = action_name
        self.current_calibration_step = 1
        self.temp_snapshots = {} 
        self.update_wizard_ui()
        self.stack.setCurrentWidget(self.wizard_widget)

    def update_wizard_ui(self):
        """ ATUALIZADO: Altera o texto para a gravação de batidas. """
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
        """ ATUALIZADO: Salva o snapshot e avança, ou inicia/para a gravação. """
        action = self.current_calibration_action
        step = self.current_calibration_step
        
        snapshot = self.main_app.communication.get_latest_data()
        if not snapshot and step == 1: 
            w = MessageBox("Erro", "Luva desconectada no meio da calibração.", self)
            w.exec()
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
        """ (Sem mudanças) """
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
        """ (Sem mudanças) """
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
        """ (Sem mudanças, exceto QMessageBox) """
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
            w = MessageBox("Sucesso", f"Calibração para '{action}' salva!\nSensor detectado: {detected_key}", self)
            w.exec()
        else:
            w = MessageBox("Erro", "Nenhuma variação de sensor ADC detectada. Tente novamente.", self)
            w.exec()
        self.cancel_wizard()

    def finish_strum_calibration(self):
        """ (Sem mudanças, exceto QMessageBox) """
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
            w = MessageBox("Sucesso", f"Calibração para '{action}' salva!\nSensor detectado: {detected_prefix} (Aceleração)", self)
            w.exec()
        else:
            w = MessageBox("Erro", "Nenhuma variação de sensor de Aceleração detectada. Tente novamente.", self)
            w.exec()
        self.cancel_wizard()

    def cancel_wizard(self):
        """ (Sem mudanças) """
        self.stack.setCurrentWidget(self.main_menu_widget)
        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        self.is_recording_peak = False
        self.current_peak_snapshot = {}
        self.current_peak_magnitude = -1.0
        self.update_calibration_status_labels()

    def go_back(self):
        self.main_app.show_main_menu_screen()


class MainMenuScreen(Screen):
    """ Tela Principal de Emulação e Configuração. """
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        layout.addWidget(BodyLabel("<b>1. Selecione o Instrumento:</b>"))
        self.instrument_combo = ComboBox(self)
        self.instrument_combo.addItems(["Guitarra (Luva)", "Bateria (Camera)"])
        layout.addWidget(self.instrument_combo)
        
        layout.addWidget(BodyLabel("<b>2. Selecione a Saída:</b>"))
        self.output_combo = ComboBox(self)
        self.output_combo.addItems(["Teclado", "Joystick"])
        layout.addWidget(self.output_combo)
        
        layout.addWidget(TitleLabel("Controles da Guitarra 🎸"))
        
        self.connect_glove_btn = PrimaryPushButton("Conectar à Luva")
        self.connect_glove_btn.clicked.connect(self.main_app.toggle_glove_connection)
        layout.addWidget(self.connect_glove_btn)
        
        self.calibrate_btn = PushButton("Calibrar Sensores (Luva)") 
        self.calibrate_btn.clicked.connect(self.main_app.show_calibration_screen)
        layout.addWidget(self.calibrate_btn)
        
        self.status_label = BodyLabel("Status Luva: Desconectado")
        layout.addWidget(self.status_label)
        
        layout.addWidget(TitleLabel("Controles da Bateria 🥁"))
        self.camera_feedback_btn = PushButton("Ver Retorno da Câmera (Bateria)")
        self.camera_feedback_btn.clicked.connect(self.main_app.run_drum_simulation)
        layout.addWidget(self.camera_feedback_btn)
        
        # O botão de instruções foi movido para a barra de navegação
        # self.instructions_btn = PushButton("Ver Instruções 📝")
        # self.instructions_btn.clicked.connect(self.main_app.show_instructions_screen)
        # layout.addWidget(self.instructions_btn)

        self.debug_check = CheckBox("Habilitar Terminal de Debug (Luva)", self)
        self.debug_check.setChecked(False) 
        layout.addWidget(self.debug_check)
        
        self.debug_label = BodyLabel("Dados Brutos dos Sensores (Luva):")
        self.sensor_output = TextEdit(self)
        self.sensor_output.setReadOnly(True)
        layout.addWidget(self.debug_label)
        layout.addWidget(self.sensor_output)
        
        self.debug_check.toggled.connect(self.debug_label.setVisible)
        self.debug_check.toggled.connect(self.sensor_output.setVisible)
        self.debug_label.setVisible(False)
        self.sensor_output.setVisible(False)
        
        self.setLayout(layout)

    def update_sensor_data(self, raw_data):
        if not self.sensor_output.isVisible():
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
            if self.sensor_output.isVisible():
                self.sensor_output.clear()
        else:
            self.connect_glove_btn.setText("Conectar à Luva")
            if self.sensor_output.isVisible():
                self.sensor_output.setHtml(
                    f"<span style='color:#FF4444; font-weight:bold;'>⚠️ {status_message}</span>"
                )

class MainApplication(FluentWindow):
    """
    Classe principal da Interface (Agora é uma FluentWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 700, 800) # Janela um pouco maior
        
        self.sensor_mappings = {} 
        self.load_mappings_from_file()
        
        # Instancia as classes de lógica
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # Cria as telas (páginas)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self) 

        # Cria a interface de navegação
        self.navigationInterface = NavigationInterface(self, showMenuButton=True, showReturnButton=True)
        
        # --- INÍCIO DA CORREÇÃO ---
        
        # 1. Adicione manualmente as telas DIRETAMENTE à interface de navegação
        #    (Substituído: self.navigationInterface.stackedWidget.addWidget)
        self.navigationInterface.addWidget(self.instructions_screen)
        self.navigationInterface.addWidget(self.main_menu_screen)
        self.navigationInterface.addWidget(self.calibration_screen)
        
        # 2. Mude o 4º argumento de 'addItem' de um widget para um 'onClick' (lambda)
        #    A lambda agora chama 'setCurrentWidget' DIRETAMENTE na interface
        
        self.navigationInterface.addItem(
            'instructions',
            FluentIcon.INFO,
            "Instruções",
            # O 4º argumento é 'onClick'
            # (Substituído: self.navigationInterface.stackedWidget.setCurrentWidget)
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.instructions_screen),
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            'main_menu',
            FluentIcon.HOME,
            "Menu Principal",
            # O 4º argumento é 'onClick'
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.main_menu_screen)
        )

        self.navigationInterface.addItem(
            'calibration',
            FluentIcon.SETTINGS,
            "Calibração",
            # O 4º argumento é 'onClick'
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.calibration_screen)
        )
        
        # --- FIM DA CORREÇÃO ---
        
        # Define a interface de navegação como o widget central
        self.setCentralWidget(self.navigationInterface)
        
        # Inicia timers
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) 
        
        # Inicia na tela de instruções
        self.navigationInterface.setCurrentItem('instructions')
        self._check_network_status() 

    # ============ Funções de Controle (Sem Mudanças) ============
    
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
        self.main_menu_screen.update_connection_status(is_connected, status)

        # Mostra um InfoBar se a conexão falhar
        if not is_connected and ("Falha" in status or "Desconectado" in status or "Não foi possível" in status):
            InfoBar.warning("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)
        elif is_connected and "Conectado" in status:
            InfoBar.success("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)


    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ (Sem Mudanças) """
        raw_data = self.communication.get_latest_data()
        self.main_menu_screen.update_sensor_data(raw_data)
        
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
            self.guitar.process_data(
                logical_data, 
                self.sensor_mappings, 
                self.emulator
            )

    # ============ Troca de Telas (Adaptado para NavigationInterface) ============

    @Slot()
    def show_main_menu_screen(self):
        self.navigationInterface.setCurrentItem('main_menu')

    @Slot()
    def show_calibration_screen(self):
        self.navigationInterface.setCurrentItem('calibration')
        
    @Slot()
    def show_instructions_screen(self):
        self.navigationInterface.setCurrentItem('instructions')

    # ============ Estilo (Removido, agora é feito pela Fluent-Widgets) ============
    
    # def apply_stylesheet(self):
    #     pass # Não é mais necessário

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False 
        try:
            # Adiciona uma verificação caso self.drum não tenha sido totalmente inicializado
            if hasattr(self.drum, 'camera'):
                self.drum.camera.release()
        except Exception as e:
            print(f"Aviso: Não foi possível liberar a câmera. {e}")
        event.accept()
    """
    Classe principal da Interface (Agora é uma FluentWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 700, 800) # Janela um pouco maior
        
        self.sensor_mappings = {} 
        self.load_mappings_from_file()
        
        # Instancia as classes de lógica
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # Cria as telas (páginas)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self) 

        # Cria a interface de navegação
        self.navigationInterface = NavigationInterface(self, showMenuButton=True, showReturnButton=True)
        
        # --- INÍCIO DA CORREÇÃO ---
        
        # 1. Adicione manualmente as telas DIRETAMENTE à interface de navegação
        #    (Substituído: self.navigationInterface.stackedWidget.addWidget)
        self.navigationInterface.addWidget(self.instructions_screen)
        self.navigationInterface.addWidget(self.main_menu_screen)
        self.navigationInterface.addWidget(self.calibration_screen)
        
        # 2. Mude o 4º argumento de 'addItem' de um widget para um 'onClick' (lambda)
        #    A lambda agora chama 'setCurrentWidget' DIRETAMENTE na interface
        
        self.navigationInterface.addItem(
            'instructions',
            FluentIcon.INFO,
            "Instruções",
            # O 4º argumento é 'onClick'
            # (Substituído: self.navigationInterface.stackedWidget.setCurrentWidget)
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.instructions_screen),
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            'main_menu',
            FluentIcon.HOME,
            "Menu Principal",
            # O 4º argumento é 'onClick'
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.main_menu_screen)
        )

        self.navigationInterface.addItem(
            'calibration',
            FluentIcon.SETTINGS,
            "Calibração",
            # O 4º argumento é 'onClick'
            onClick=lambda: self.navigationInterface.setCurrentWidget(self.calibration_screen)
        )
        
        # --- FIM DA CORREÇÃO ---
        
        # Define a interface de navegação como o widget central
        self.setCentralWidget(self.navigationInterface)
        
        # Inicia timers
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) 
        
        # Inicia na tela de instruções
        self.navigationInterface.setCurrentItem('instructions')
        self._check_network_status() 

    # ============ Funções de Controle (Sem Mudanças) ============
    
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
        self.main_menu_screen.update_connection_status(is_connected, status)

        # Mostra um InfoBar se a conexão falhar
        if not is_connected and ("Falha" in status or "Desconectado" in status or "Não foi possível" in status):
            InfoBar.warning("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)
        elif is_connected and "Conectado" in status:
            InfoBar.success("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)


    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ (Sem Mudanças) """
        raw_data = self.communication.get_latest_data()
        self.main_menu_screen.update_sensor_data(raw_data)
        
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
            self.guitar.process_data(
                logical_data, 
                self.sensor_mappings, 
                self.emulator
            )

    # ============ Troca de Telas (Adaptado para NavigationInterface) ============

    @Slot()
    def show_main_menu_screen(self):
        self.navigationInterface.setCurrentItem('main_menu')

    @Slot()
    def show_calibration_screen(self):
        self.navigationInterface.setCurrentItem('calibration')
        
    @Slot()
    def show_instructions_screen(self):
        self.navigationInterface.setCurrentItem('instructions')

    # ============ Estilo (Removido, agora é feito pela Fluent-Widgets) ============
    
    # def apply_stylesheet(self):
    #     pass # Não é mais necessário

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False 
        try:
            # Adiciona uma verificação caso self.drum não tenha sido totalmente inicializado
            if hasattr(self.drum, 'camera'):
                self.drum.camera.release()
        except Exception as e:
            print(f"Aviso: Não foi possível liberar a câmera. {e}")
        event.accept()
    """
    Classe principal da Interface (Agora é uma FluentWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 700, 800) # Janela um pouco maior
        
        self.sensor_mappings = {} 
        self.load_mappings_from_file()
        
        # Instancia as classes de lógica
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # Cria as telas (páginas)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self) 

        # Cria a interface de navegação
        self.navigationInterface = NavigationInterface(self, showMenuButton=True, showReturnButton=True)
        
        # --- INÍCIO DA CORREÇÃO ---
        
        # 1. Adicione manualmente as telas ao QStackedWidget da interface
        #    (O QStackedWidget está em self.navigationInterface.stackedWidget)
        self.navigationInterface.stackedWidget.addWidget(self.instructions_screen)
        self.navigationInterface.stackedWidget.addWidget(self.main_menu_screen)
        self.navigationInterface.stackedWidget.addWidget(self.calibration_screen)
        
        # 2. Mude o 4º argumento de 'addItem' de um widget para um 'onClick' (lambda)
        
        self.navigationInterface.addItem(
            'instructions',
            FluentIcon.INFO,
            "Instruções",
            # O 4º argumento agora é 'onClick', não o widget
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.instructions_screen),
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            'main_menu',
            FluentIcon.HOME,
            "Menu Principal",
            # O 4º argumento agora é 'onClick'
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.main_menu_screen)
        )

        self.navigationInterface.addItem(
            'calibration',
            FluentIcon.SETTINGS,
            "Calibração",
            # O 4º argumento agora é 'onClick'
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.calibration_screen)
        )
        
        # --- FIM DA CORREÇÃO ---
        
        # Define a interface de navegação como o widget central
        self.setCentralWidget(self.navigationInterface)
        
        # Inicia timers
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) 
        
        # Inicia na tela de instruções
        # (Definindo o item atual, a função onClick associada será chamada)
        self.navigationInterface.setCurrentItem('instructions')
        self._check_network_status() 

    # ============ Funções de Controle (Sem Mudanças) ============
    
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
        self.main_menu_screen.update_connection_status(is_connected, status)

        # Mostra um InfoBar se a conexão falhar
        # (Verificação ajustada para ser mais robusta)
        if not is_connected and ("Falha" in status or "Desconectado" in status or "Não foi possível" in status):
            InfoBar.warning("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)
        elif is_connected and "Conectado" in status:
            InfoBar.success("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)


    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ (Sem Mudanças) """
        raw_data = self.communication.get_latest_data()
        self.main_menu_screen.update_sensor_data(raw_data)
        
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
            self.guitar.process_data(
                logical_data, 
                self.sensor_mappings, 
                self.emulator
            )

    # ============ Troca de Telas (Adaptado para NavigationInterface) ============

    @Slot()
    def show_main_menu_screen(self):
        self.navigationInterface.setCurrentItem('main_menu')

    @Slot()
    def show_calibration_screen(self):
        self.navigationInterface.setCurrentItem('calibration')
        
    @Slot()
    def show_instructions_screen(self):
        self.navigationInterface.setCurrentItem('instructions')

    # ============ Estilo (Removido, agora é feito pela Fluent-Widgets) ============
    
    # def apply_stylesheet(self):
    #     pass # Não é mais necessário

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False 
        self.drum.camera.release()
        event.accept()
    """
    Classe principal da Interface (Agora é uma FluentWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 700, 800) # Janela um pouco maior
        
        self.sensor_mappings = {} 
        self.load_mappings_from_file()
        
        # Instancia as classes de lógica
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # Cria as telas (páginas)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self) 

        # Cria a interface de navegação
        self.navigationInterface = NavigationInterface(self, showMenuButton=True, showReturnButton=True)

        self.navigationInterface.stackedWidget.addWidget(self.instructions_screen)
        self.navigationInterface.stackedWidget.addWidget(self.main_menu_screen)
        self.navigationInterface.stackedWidget.addWidget(self.calibration_screen)
        
        # 2. Mude o 4º argumento de 'addItem' de um widget para um 'onClick' (lambda)
        
        self.navigationInterface.addItem(
            'instructions',
            FluentIcon.INFO,
            "Instruções",
            # Antes: self.instructions_screen,
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.instructions_screen),
            position=NavigationItemPosition.BOTTOM
        )

        self.navigationInterface.addItem(
            'main_menu',
            FluentIcon.HOME,
            "Menu Principal",
            # Antes: self.main_menu_screen
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.main_menu_screen)
        )

        self.navigationInterface.addItem(
            'calibration',
            FluentIcon.SETTINGS,
            "Calibração",
            # Antes: self.calibration_screen
            onClick=lambda: self.navigationInterface.stackedWidget.setCurrentWidget(self.calibration_screen)
        )

        
        # Define a interface de navegação como o widget central
        self.setCentralWidget(self.navigationInterface)
        
        # Inicia timers
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) 
        
        # Inicia na tela de instruções
        self.navigationInterface.setCurrentItem('instructions')
        self._check_network_status() 

    # ============ Funções de Controle (Sem Mudanças) ============
    
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
        self.main_menu_screen.update_connection_status(is_connected, status)

        # Mostra um InfoBar se a conexão falhar
        if "Falha" in status or "Desconectado" in status:
            InfoBar.warning("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)
        elif "Conectado" in status:
            InfoBar.success("Conexão", status, parent=self, duration=3000, position=InfoBarPosition.TOP)


    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ (Sem Mudanças) """
        raw_data = self.communication.get_latest_data()
        self.main_menu_screen.update_sensor_data(raw_data)
        
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
            self.guitar.process_data(
                logical_data, 
                self.sensor_mappings, 
                self.emulator
            )

    # ============ Troca de Telas (Adaptado para NavigationInterface) ============

    @Slot()
    def show_main_menu_screen(self):
        self.navigationInterface.setCurrentItem('main_menu')

    @Slot()
    def show_calibration_screen(self):
        self.navigationInterface.setCurrentItem('calibration')
        
    @Slot()
    def show_instructions_screen(self):
        self.navigationInterface.setCurrentItem('instructions')

    # ============ Estilo (Removido, agora é feito pela Fluent-Widgets) ============
    
    # def apply_stylesheet(self):
    #     pass # Não é mais necessário

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False 
        self.drum.camera.release()
        event.accept()