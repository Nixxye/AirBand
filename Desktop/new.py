import sys
import random
import cv2
import mediapipe as mp
import math
import socket
import threading
import time
import json  # Importado para decodificar dados da ESP

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QSlider,
    QCheckBox, QStackedWidget, QFormLayout,
    QScrollArea
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot

# ===================================================================
# 1. CLASSES DE LÓGICA (NÃO-UI)
# ===================================================================

class Communication:
    """ 
    Gerencia a conexão REAL com a luva (ESP32) via Wi-Fi (TCP Socket).
    """
    
    ESP_HOST = '192.168.4.1' 
    ESP_PORT = 8888 

    def __init__(self):
        self.connected = False
        self.sock = None
        self.receiver_thread = None
        self.data_lock = threading.Lock()
        self.network_status_message = "Desconectado"
        
        # Armazena os dados brutos e achatados (ex: {"adc_v32": 1023, "gyro_ax": 1.2})
        self.last_sensor_data = {}

    def toggle_connection(self):
        """ Inicia ou para a thread de conexão. """
        if self.connected:
            self.connected = False
            if self.receiver_thread:
                self.receiver_thread.join() 
            if self.sock:
                self.sock.close()
            self.network_status_message = "Desconectado"
        else:
            self.connected = True
            self.network_status_message = "Conectando..."
            self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receiver_thread.start()

    def _receive_loop(self):
        """ Loop principal da thread de rede. """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0) 
            print(f"Tentando conectar a {self.ESP_HOST}:{self.ESP_PORT}...")
            self.sock.connect((self.ESP_HOST, self.ESP_PORT))
            self.sock.settimeout(1.0) 
            
            self.network_status_message = "Conectado"
            print("Conectado à ESP32!")
            
            buffer = ""
            while self.connected:
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        print("Servidor (ESP32) fechou a conexão.")
                        break
                    
                    buffer += data.decode('utf-8')
                    
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self._parse_data(line)

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Erro no loop de recebimento: {e}")
                    time.sleep(0.5)

        except socket.error as e:
            print(f"Falha na conexão com a ESP32: {e}")
            print("Verifique se o PC está no Wi-Fi 'ALuvaQueTePariu'.")
            self.network_status_message = f"Falha: {e}"
        finally:
            if self.sock:
                self.sock.close()
            self.connected = False
            if "Conectado" in self.network_status_message:
                self.network_status_message = "Desconectado (servidor fechou)"
            print("Thread de rede finalizada.")

    def _parse_data(self, line):
        """ 
        Decodifica o JSON da ESP e o "achata" (flatten) em um dicionário.
        Ex: {"adc": {"v32": 1023}, "gyro": {"ax": 1.2}} 
        vira: {"adc_v32": 1023, "gyro_ax": 1.2}
        """
        line = line.strip()
        if not line:
            return
            
        try:
            json_data = json.loads(line)
            
            flattened_data = {}
            for main_key, value_dict in json_data.items():
                # main_key = "adc", value_dict = {"v32": 1023, ...}
                if isinstance(value_dict, dict):
                    for sub_key, sub_value in value_dict.items():
                        # new key = "adc_v32"
                        flattened_data[f"{main_key}_{sub_key}"] = sub_value
                else:
                    flattened_data[main_key] = value_dict
            
            with self.data_lock:
                self.last_sensor_data = flattened_data
                
        except json.JSONDecodeError:
            print(f"Dado recebido mal formatado (não é JSON): '{line}'")
        except Exception as e:
            print(f"Erro ao decodificar dados: {e}")

    def get_latest_data(self):
        """ Retorna a cópia mais recente dos dados achatados. """
        with self.data_lock:
            return self.last_sensor_data.copy()

    def get_live_sensor_value(self, sensor_key):
        """ Obtém o valor ATUAL de um sensor bruto específico. """
        with self.data_lock:
            return self.last_sensor_data.get(sensor_key, 0)

    def get_status_message(self):
        return self.network_status_message

class Emulator:
    """ Gerencia a saída de emulação. (Sem mudanças) """
    def __init__(self):
        self.gamepad = vg.VX360Gamepad() if HAS_VGAMEPAD else None
        if HAS_VGAMEPAD:
            print("Controlador Virtual (vgamepad) conectado.")
        else:
            print("vgamepad não encontrado. Emulação de joystick desabilitada.")

    def process_guitar_action(self, action):
        pass

    def process_drum_action(self, action):
        pass

class Camera:
    """ Gerencia a captura da câmera. (Sem mudanças) """
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

    @staticmethod
    def calcular_angulo(a, b, c):
        angulo = math.degrees(
            math.atan2(c[1] - b[1], c[0] - b[0]) -
            math.atan2(a[1] - b[1], a[0] - b[0])
        )
        angulo = abs(angulo)
        if angulo > 180:
            angulo = 360 - angulo
        return angulo

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()


class InputData:
    """ Classe base que agrupa as fontes de entrada. (Sem mudanças) """
    def __init__(self):
        self.camera = Camera()
        self.communication = Communication() 

class Instrument(InputData):
    """ Classe base para um instrumento. (Sem mudanças) """
    def __init__(self):
        super().__init__()

class Drum(Instrument):
    """ Implementação da Bateria. (Sem mudanças) """
    def __init__(self):
        super().__init__()
    
    def run_simulation(self):
        # ... (código da câmera/bateria omitido por brevidade) ...
        print("Simulação de bateria iniciada... (Pressione 'q' na janela OpenCV para sair)")
        pass # A lógica de simulação permanece a mesma

class Guitar(Instrument):
    """ Implementação da Guitarra. """
    def __init__(self):
        pass

    def process_data(self, logical_data, mappings, emulator: Emulator):
        """
        (LÓGICA FUTURA) Processa os dados lógicos da luva.
        
        logical_data: Dicionário com dados atuais. 
                      Ex: {"Dedo 1": 1023, "Palhetada": 50.5}
                      
        mappings: Dicionário com os limiares (thresholds) definidos.
                  Ex: {"Dedo 1": {"key": "adc_v32", "threshold": 800, "type": "lt"},
                       "Palhetada": {"key": "gyro_gx", "threshold": 40.0, "type": "gt"}}
        """
        
        for action, value in logical_data.items():
            if action not in mappings:
                continue # Ação não mapeada

            mapping = mappings[action]
            threshold = mapping["threshold"]
            activation_type = mapping["type"] # "lt" (menor que) ou "gt" (maior que)

            # Lógica de ativação
            is_active = False
            if activation_type == "lt" and value < threshold:
                is_active = True
            elif activation_type == "gt" and value > threshold:
                is_active = True

            # (LÓGICA FUTURA) Enviar comando para o emulador
            if is_active:
                if action == "Dedo 1":
                    # print("Dedo 1 Ativado!") 
                    # emulator.process_guitar_action("GREEN_NOTE_ON")
                    pass
                elif action == "Palhetada":
                    # print("Palhetada!")
                    # emulator.process_guitar_action("STRUM_DOWN")
                    pass
            else:
                # (LÓGICA FUTURA) Enviar comando de "soltar"
                if action == "Dedo 1":
                    # emulator.process_guitar_action("GREEN_NOTE_OFF")
                    pass

# ===================================================================
# 2. CLASSES DE INTERFACE (PyQt5 UI)
# ===================================================================

class Screen(QWidget):
    """ Classe base para todas as 'telas' da aplicação. (Sem mudanças) """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent 

class InstructionsScreen(Screen):
    """ Tela de Instruções (Tela Inicial). """
    def __init__(self, parent):
        super().__init__(parent)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Bem-vindo ao Air Band 🤘</h2>"))
        layout.addWidget(QLabel("Instruções 📝"))
        
        instructions_text = """
        Este aplicativo permite emular uma Guitarra (com a luva) ou uma Bateria (com a câmera).
        
        <b>Guitarra (Luva):</b>
        <ol>
            <li><b>Conecte seu PC ao Wi-Fi da luva (SSID: ALuvaQueTePariu).</b></li>
            <li>No menu principal, clique em 'Conectar à Luva'.</li>
            <li>Vá para a tela de Calibração.</li>
            <li>Para cada Ação (ex: Dedo 1), selecione o Sensor Bruto (ex: adc_v32) no menu dropdown.</li>
            <li>Defina o "Limiar" (valor de ativação) e o Tipo (Acima/Abaixo).</li>
            <li>Clique em 'Salvar' para aquela ação.</li>
            <li>Retorne ao menu e toque!</li>
        </ol>
        
        <b>Bateria (Câmera):</b>
        <ol>
            <li>Posicione-se em frente à câmera.</li>
            <li>No menu principal, clique em 'Ver Retorno da Câmera'.</li>
        </ol>
        """
        layout.addWidget(QLabel(instructions_text))
        
        layout.addStretch() 
        
        self.continue_btn = QPushButton("Ir para o Menu Principal ➡️")
        self.continue_btn.clicked.connect(self.main_app.show_main_menu_screen)
        layout.addWidget(self.continue_btn)
        
        self.setLayout(layout)

class CalibrationScreen(Screen):
    """ Tela de Mapeamento e Calibração dos Sensores. """
    def __init__(self, parent):
        super().__init__(parent)
        
        # --- Layout Principal ---
        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("<h2>Mapeamento e Calibração 🎛️</h2>"))

        # --- Área de Mapeamento (com Scroll) ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        form_layout = QFormLayout(scroll_widget)
        
        # Ações lógicas que o usuário pode mapear
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Palhetada", "Mov. X", "Mov. Y", "Mov. Z"
        ]
        
        # Dicionário para guardar os widgets de UI de cada linha
        self.mapping_widgets = {}

        for action in self.logical_actions:
            hbox = QHBoxLayout()
            
            # 1. Dropdown para selecionar o sensor bruto
            combo_sensor = QComboBox()
            combo_sensor.setMinimumWidth(120)
            
            # 2. Dropdown para tipo de ativação (Maior/Menor)
            combo_type = QComboBox()
            combo_type.addItems(["< (Abaixo de)", "> (Acima de)"])
            # Assume que dedos flexionados diminuem o valor do ADC
            if "Dedo" in action:
                combo_type.setCurrentIndex(0) # "< (Abaixo de)"
            else:
                combo_type.setCurrentIndex(1) # "> (Acima de)"

            # 3. Slider para o Limiar (Threshold)
            slider_threshold = QSlider(Qt.Horizontal)
            slider_threshold.setRange(0, 4095) # Range padrão do ADC
            
            # 4. Label para mostrar o valor do slider
            label_threshold = QLabel("0")
            label_threshold.setMinimumWidth(40)
            slider_threshold.valueChanged.connect(lambda v, lbl=label_threshold: lbl.setText(str(v)))

            # 5. Botão Salvar
            btn_save = QPushButton("Salvar")
            # Conecta o botão usando lambda para passar o nome da ação
            btn_save.clicked.connect(lambda _, a=action: self.save_mapping(a))

            # Adiciona widgets ao HBox
            hbox.addWidget(QLabel("Sensor:"))
            hbox.addWidget(combo_sensor)
            hbox.addWidget(QLabel("Ativação:"))
            hbox.addWidget(combo_type)
            hbox.addWidget(QLabel("Limiar:"))
            hbox.addWidget(slider_threshold)
            hbox.addWidget(label_threshold)
            hbox.addWidget(btn_save)

            # Adiciona a linha (Label da Ação + HBox de widgets) ao FormLayout
            form_layout.addRow(QLabel(f"<b>{action}:</b>"), hbox)
            
            # Armazena os widgets para esta ação
            self.mapping_widgets[action] = {
                "combo_sensor": combo_sensor,
                "combo_type": combo_type,
                "slider": slider_threshold,
                "label": label_threshold
            }

        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # --- Área de Dados Brutos ---
        main_layout.addWidget(QLabel("<b>Dados Brutos (Tempo Real):</b>"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        self.sensor_output.setFixedHeight(150) # Altura fixa
        main_layout.addWidget(self.sensor_output)

        # --- Botão Voltar ---
        back_btn = QPushButton("⬅️ Voltar ao Menu")
        back_btn.clicked.connect(self.go_back)
        main_layout.addWidget(back_btn)

        self.setLayout(main_layout)

        # Timer para atualizar dados
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)
        self._raw_keys_populated = False

    def showEvent(self, event):
        """ Chamado quando o widget é exibido. """
        super().showEvent(event)
        self.timer.start(100) # Atualiza rápido (10x/seg)
        # Carrega os mapeamentos salvos na UI
        self.load_mappings_to_ui()

    def hideEvent(self, event):
        """ Chamado quando o widget é ocultado. """
        super().hideEvent(event)
        self.timer.stop()
        self._raw_keys_populated = False # Força repopular na próxima vez

    def update_sensor_data(self):
        """ Atualiza o terminal de dados brutos e popula os combos na primeira vez. """
        # Obtém os dados mais recentes da classe de comunicação
        raw_data = self.main_app.communication.get_latest_data()
        
        if not raw_data:
            self.sensor_output.setHtml("<span style='color:#FF4444;'>Sem dados... conecte a luva.</span>")
            return
            
        # --- Popula os combos de sensores na primeira vez que recebe dados ---
        if not self._raw_keys_populated:
            self.populate_sensor_combos(raw_data.keys())
            self.load_mappings_to_ui() # Recarrega para selecionar os itens corretos
            self._raw_keys_populated = True

        # --- Atualiza o terminal de dados brutos ---
        texto = ""
        for key, value in sorted(raw_data.items()):
            if isinstance(value, (float)):
                texto += f"<span style='color:#00FFFF;'>{key}:</span> {value:.2f}\n"
            else:
                texto += f"<span style='color:#00FFFF;'>{key}:</span> {value}\n"
        self.sensor_output.setHtml(texto)

    def populate_sensor_combos(self, raw_keys):
        """ Preenche todos os QComboBox com as chaves de sensores brutos. """
        sorted_keys = sorted(list(raw_keys))
        
        for action, widgets in self.mapping_widgets.items():
            combo = widgets["combo_sensor"]
            
            # Salva o texto que estava selecionado
            current_selection = combo.currentText()
            
            combo.clear()
            combo.addItem("-- Nenhum --")
            combo.addItems(sorted_keys)
            
            # Tenta restaurar a seleção anterior
            index = combo.findText(current_selection)
            if index != -1:
                combo.setCurrentIndex(index)

    def load_mappings_to_ui(self):
        """ Carrega os mapeamentos salvos da MainApp para a UI. """
        mappings = self.main_app.sensor_mappings
        
        for action, widgets in self.mapping_widgets.items():
            if action in mappings:
                mapping = mappings[action]
                
                # Seleciona o sensor bruto no combo
                index = widgets["combo_sensor"].findText(mapping["key"])
                if index != -1:
                    widgets["combo_sensor"].setCurrentIndex(index)
                
                # Seleciona o tipo de ativação
                type_str = "< (Abaixo de)" if mapping["type"] == "lt" else "> (Acima de)"
                index = widgets["combo_type"].findText(type_str)
                if index != -1:
                    widgets["combo_type"].setCurrentIndex(index)
                    
                # Define o valor do slider e do label
                widgets["slider"].setValue(int(mapping["threshold"]))
                widgets["label"].setText(str(int(mapping["threshold"])))
            else:
                # Reseta para o padrão se não houver mapeamento
                widgets["combo_sensor"].setCurrentIndex(0)
                widgets["slider"].setValue(0)
                widgets["label"].setText("0")

    def save_mapping(self, logical_action):
        """ Salva o mapeamento da UI para a MainApp. """
        widgets = self.mapping_widgets[logical_action]
        
        raw_key = widgets["combo_sensor"].currentText()
        type_str = widgets["combo_type"].currentText()
        threshold = widgets["slider"].value()
        
        if raw_key == "-- Nenhum --":
            # Remove o mapeamento se "Nenhum" for selecionado
            if logical_action in self.main_app.sensor_mappings:
                del self.main_app.sensor_mappings[logical_action]
            print(f"Mapeamento '{logical_action}' removido.")
        else:
            # Adiciona ou atualiza o mapeamento
            activation_type = "lt" if type_str == "< (Abaixo de)" else "gt"
            self.main_app.sensor_mappings[logical_action] = {
                "key": raw_key,
                "threshold": threshold,
                "type": activation_type
            }
            print(f"Mapeamento salvo: '{logical_action}' -> {raw_key} {activation_type} {threshold}")
            
        # (Opcional) Confirmação visual (pisca o botão, etc)
        # Por enquanto, apenas o print no console.

    def go_back(self):
        self.main_app.show_main_menu_screen()


class MainMenuScreen(Screen):
    """ Tela Principal de Emulação e Configuração. """
    def __init__(self, parent):
        super().__init__(parent)
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<h2>Menu Principal ⚙️</h2>"))
        layout.addWidget(QLabel("<b>1. Selecione o Instrumento:</b>"))
        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(["Guitarra (Luva)", "Bateria (Camera)"])
        layout.addWidget(self.instrument_combo)

        layout.addWidget(QLabel("<b>2. Selecione a Saída:</b>"))
        self.output_combo = QComboBox()
        self.output_combo.addItems(["Teclado", "Joystick"])
        layout.addWidget(self.output_combo)
        
        layout.addWidget(QLabel("<h3>Controles da Guitarra 🎸</h3>"))
        self.connect_glove_btn = QPushButton("Conectar à Luva")
        self.connect_glove_btn.clicked.connect(self.main_app.toggle_glove_connection)
        layout.addWidget(self.connect_glove_btn)

        self.calibrate_btn = QPushButton("Mapear Sensores (Luva)")
        self.calibrate_btn.clicked.connect(self.main_app.show_calibration_screen)
        layout.addWidget(self.calibrate_btn)
        
        self.status_label = QLabel("Status Luva: Desconectado")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("<h3>Controles da Bateria 🥁</h3>"))
        self.camera_feedback_btn = QPushButton("Ver Retorno da Câmera (Bateria)")
        self.camera_feedback_btn.clicked.connect(self.main_app.run_drum_simulation)
        layout.addWidget(self.camera_feedback_btn)

        layout.addWidget(QLabel("<h3>Geral</h3>"))
        self.instructions_btn = QPushButton("Ver Instruções 📝")
        self.instructions_btn.clicked.connect(self.main_app.show_instructions_screen)
        layout.addWidget(self.instructions_btn)

        self.debug_check = QCheckBox("Habilitar Terminal de Debug (Luva)")
        self.debug_check.setChecked(False) 
        layout.addWidget(self.debug_check)

        self.debug_label = QLabel("Dados Brutos dos Sensores (Luva):")
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        
        layout.addWidget(self.debug_label)
        layout.addWidget(self.sensor_output)
        
        self.debug_check.toggled.connect(self.debug_label.setVisible)
        self.debug_check.toggled.connect(self.sensor_output.setVisible)
        
        self.debug_label.setVisible(False)
        self.sensor_output.setVisible(False)
        
        self.setLayout(layout)

    def update_sensor_data(self, raw_data):
        """ Atualiza o QTextEdit com dados brutos da luva. """
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
        """ Atualiza os botões e labels de status da luva. """
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

class MainApplication(QMainWindow):
    """
    Classe principal da Interface (QMainWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 600, 700)
        
        # Estado e Lógica
        # Dicionário de mapeamento (ex: "Dedo 1" -> {"key": "adc_v32", "threshold": 800, "type": "lt"})
        self.sensor_mappings = {} 
        
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # --- Configuração do QStackedWidget ---
        self.stack = QStackedWidget(self)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self)
        self.stack.addWidget(self.instructions_screen)
        self.stack.addWidget(self.main_menu_screen)
        self.stack.addWidget(self.calibration_screen)
        self.setCentralWidget(self.stack)
        
        # --- Timers ---
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) # Roda 2x/seg
        
        # Configuração inicial
        self.stack.setCurrentWidget(self.instructions_screen) 
        self._check_network_status() 
        self.apply_stylesheet()

    # ============ Funções de Controle ============

    def toggle_glove_connection(self):
        self.communication.toggle_connection()
        
    def _check_network_status(self):
        status = self.communication.get_status_message()
        is_connected = self.communication.connected
        self.main_menu_screen.update_connection_status(is_connected, status)

    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ 
        Chamado pelo timer rápido (glove_timer).
        Pega dados brutos, traduz para lógicos e envia para emulação.
        """
        # 1. Pega os dados brutos mais recentes (ex: {"adc_v32": 1023, ...})
        raw_data = self.communication.get_latest_data()
        
        # 2. Atualiza o terminal de debug (se estiver visível)
        self.main_menu_screen.update_sensor_data(raw_data)
        
        # 3. Traduz dados brutos para lógicos usando os mapeamentos
        logical_data = {}
        if self.communication.connected:
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")
                if raw_key in raw_data:
                    # Cria o dicionário (ex: {"Dedo 1": 1023, "Palhetada": 1.5})
                    logical_data[action] = raw_data[raw_key]
        
        # 4. Envia os dados lógicos e os mapeamentos para a classe Guitar
        if logical_data:
            self.guitar.process_data(
                logical_data, 
                self.sensor_mappings, 
                self.emulator
            )

    # ============ Troca de Telas (agora usando o Stack) ============

    def show_main_menu_screen(self):
        self.stack.setCurrentWidget(self.main_menu_screen)

    def show_calibration_screen(self):
        self.stack.setCurrentWidget(self.calibration_screen)
        
    def show_instructions_screen(self):
        self.stack.setCurrentWidget(self.instructions_screen)

    # ============ Estilo ============
    
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #111; color: white; }
            QWidget { color: white; } 
            QScrollArea { border: none; }
            QPushButton {
                background-color: #222;
                color: #FF00FF;
                font-size: 14px;
                padding: 8px;
                border-radius: 6px;
                border: 1px solid #FF00FF;
            }
            QPushButton:hover {
                background-color: #FF00FF;
                color: black;
            }
            QCheckBox {
                color: #00FFFF;
                font-size: 14px;
                margin-top: 10px;
            }
            QComboBox {
                background-color: #333;
                color: #00FFFF;
                padding: 4px;
            }
            QLabel { color: #FFFFFF; font-weight: bold; }
            QLabel[text^="Status"] { color: #FFA500; font-style: italic; }
            h2 { color: #00FFFF; }
            h3 { color: #FFA500; margin-top: 10px;}
            QTextEdit {
                background-color: #000;
                color: white;
                font-family: monospace;
                border: 1px solid #333;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 8px;
                background: #333;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #FF00FF;
                border: 1px solid #FF00FF;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
        """)

    def closeEvent(self, event):
        """ Garante que a câmera e o socket sejam liberados ao fechar. """
        self.communication.connected = False 
        self.drum.camera.release()
        event.accept()

# ===================================================================
# 3. EXECUÇÃO DA APLICAÇÃO
# ===================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApplication()
    window.show()
    sys.exit(app.exec_())