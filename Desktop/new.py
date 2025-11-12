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
    QScrollArea, QLineEdit, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot

# ===================================================================
# 1. CLASSES DE LÓGICA (NÃO-UI)
# ===================================================================

class Communication:
    """ 
    Gerencia a conexão REAL com a luva (ESP32) via Wi-Fi (TCP Socket).
    (Sem mudanças nesta classe)
    """
    
    ESP_HOST = '192.168.4.1' 
    ESP_PORT = 8888 

    def __init__(self):
        self.connected = False
        self.sock = None
        self.receiver_thread = None
        self.data_lock = threading.Lock()
        self.network_status_message = "Desconectado"
        self.last_sensor_data = {}

    def toggle_connection(self):
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
        line = line.strip()
        if not line:
            return
        try:
            json_data = json.loads(line)
            flattened_data = {}
            for main_key, value_dict in json_data.items():
                if isinstance(value_dict, dict):
                    for sub_key, sub_value in value_dict.items():
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
        with self.data_lock:
            return self.last_sensor_data.copy()

    def get_live_sensor_value(self, sensor_key):
        with self.data_lock:
            return self.last_sensor_data.get(sensor_key, 0.0) 

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
    def process_guitar_action(self, action): pass
    def process_drum_action(self, action): pass

class Camera:
    """ Gerencia a captura da câmera. (Sem mudanças) """
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)
    @staticmethod
    def calcular_angulo(a, b, c):
        angulo = math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0]))
        angulo = abs(angulo)
        if angulo > 180: angulo = 360 - angulo
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
        print("Simulação de bateria iniciada... (Pressione 'q' na janela OpenCV para sair)")
        pass

class Guitar(Instrument):
    """ Implementação da Guitarra. (Sem mudanças) """
    def __init__(self):
        pass

    def process_data(self, logical_data, mappings, emulator: Emulator):
        """
        Processa os dados lógicos da luva usando os mapeamentos de 3 pontos.
        """
        
        for action, current_value in logical_data.items():
            if action not in mappings:
                continue

            mapping = mappings[action]
            
            # Lógica para DEDOS (3 pontos)
            if "Dedo" in action:
                try:
                    rest_val = float(mapping.get("rest", 4095))
                    half_val = float(mapping.get("half", 2048))
                    full_val = float(mapping.get("full", 0))
                except ValueError:
                    continue 
                
                # Assume que valores MENORES significam "mais pressionado"
                if current_value < full_val:
                    # print(f"{action}: COMPLETO")
                    pass
                elif current_value < half_val:
                    # print(f"{action}: MEIO")
                    pass
                elif current_value < rest_val:
                    # print(f"{action}: REPOUSO (mas não totalmente solto)")
                    pass
                else:
                    # print(f"{action}: SOLTO")
                    pass

            # Lógica para BATIDAS (2 pontos)
            elif "Batida" in action:
                # current_value agora é um dicionário, ex: {"ax": 1.1, "ay": -0.5, "az": 0.2}
                if not isinstance(logical_data[action], dict):
                    continue # Mapeamento antigo ou erro

                try:
                    # Pega os dicionários de 'rest' e 'peak'
                    rest_map = mapping.get("rest", {})
                    peak_map = mapping.get("peak", {})

                    # --- MUDANÇA: Usa ax, ay, az ---
                    # Calcula a magnitude do vetor de repouso
                    rest_mag = math.sqrt(
                        float(rest_map.get("ax", 0))**2 +
                        float(rest_map.get("ay", 0))**2 +
                        float(rest_map.get("az", 0))**2
                    )
                    
                    # Calcula a magnitude do vetor de pico
                    peak_mag = math.sqrt(
                        float(peak_map.get("ax", 0))**2 +
                        float(peak_map.get("ay", 0))**2 +
                        float(peak_map.get("az", 0))**2
                    )

                    # Pega o valor atual (já é um dicionário)
                    current_val_map = logical_data[action]
                    current_mag = math.sqrt(
                        float(current_val_map.get("ax", 0))**2 +
                        float(current_val_map.get("ay", 0))**2 +
                        float(current_val_map.get("az", 0))**2
                    )
                    # --- FIM DA MUDANÇA ---

                except (ValueError, TypeError):
                    continue
                
                # Calcula um limiar simples (ex: 75% do caminho entre repouso e pico)
                # Adiciona uma pequena margem (ex: 0.1) para evitar ativação com ruído
                threshold = rest_mag + (peak_mag - rest_mag) * 0.75
                
                # Compara a magnitude atual com o limiar
                if current_mag > threshold and current_mag > rest_mag + 0.1:
                    # print(f"{action} ATIVADA! (Mag: {current_mag:.2f})")
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
    """ Tela de Instruções (Tela Inicial). (Sem mudanças) """
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
        layout.addWidget(QLabel(instructions_text))
        
        layout.addStretch() 
        
        self.continue_btn = QPushButton("Ir para o Menu Principal ➡️")
        self.continue_btn.clicked.connect(self.main_app.show_main_menu_screen)
        layout.addWidget(self.continue_btn)
        
        self.setLayout(layout)

class CalibrationScreen(Screen):
    """ 
    Tela de Calibração estilo Wizard. 
    Contém um QStackedWidget para alternar entre o menu e o wizard.
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
        
        # --- NOVOS ESTADOS PARA GRAVAÇÃO DE PICO ---
        self.is_recording_peak = False
        self.current_peak_snapshot = {} # Armazena o snapshot que contém o pico
        self.current_peak_magnitude = -1.0 # Armazena a magnitude do pico
        # -------------------------------------------

        # --- Layout Principal ---
        main_layout = QVBoxLayout()
        self.stack = QStackedWidget()
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
        """ Cria o widget com a lista de botões de calibração. (Sem mudanças) """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<h2>Mapeamento e Calibração 🎛️</h2>"))
        layout.addWidget(QLabel("Selecione a Ação para Calibrar:"))

        self.action_labels = {} 

        for action in self.logical_actions:
            hbox = QHBoxLayout()
            label = QLabel(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")
            self.action_labels[action] = label
            
            btn = QPushButton(f"Calibrar {action}")
            btn.clicked.connect(lambda _, a=action: self.start_calibration_wizard(a))
            
            hbox.addWidget(label)
            hbox.addStretch()
            hbox.addWidget(btn)
            layout.addLayout(hbox)

        layout.addStretch()
        back_btn = QPushButton("⬅️ Voltar ao Menu")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)
        return widget

    def _create_wizard_widget(self):
        """ Cria o widget para o wizard de captura passo-a-passo. (Sem mudanças) """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
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
        
    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start(100)
        self.update_calibration_status_labels()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()

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

            # Filtra para 'gyro_' e 'mag_'. O C++ coloca 'ax,ay,az' dentro de 'gyro'
            sensor_prefixes = ["gyro_", "mag_"]
            
            # Calcula a magnitude atual para cada grupo de sensor
            for prefix in sensor_prefixes:
                # O C++ agrupa 'ax,ay,az' e 'gx,gy,gz' sob 'gyro_'.
                # Vamos focar apenas no acelerômetro ('ax','ay','az') como pedido.
                if prefix != "gyro_": # Ignora 'mag_' por enquanto
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
                    
                    # Compara com a maior desviação de magnitude salva
                    if current_deviation > self.current_peak_magnitude:
                        self.current_peak_magnitude = current_deviation
                        # Salva o *snapshot completo* que gerou esse pico
                        self.current_peak_snapshot = raw_data.copy()

                except (ValueError, TypeError):
                    continue # Ignora dados não numéricos
    
    def update_calibration_status_labels(self):
        """ Atualiza os labels do menu principal (ex: [OK: adc_v32]). (Sem mudanças) """
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                # Atualizado para checar 'key' (dedo) ou 'key_prefix' (batida)
                key = self.main_app.sensor_mappings[action].get("key", 
                          self.main_app.sensor_mappings[action].get("key_prefix", "N/A"))
                label.setText(f"<b>{action}:</b> <span style='color:#00FF00;'>[OK: {key}]</span>")
            else:
                 label.setText(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")

    # --- Lógica do Wizard (ATUALIZADA) ---

    def start_calibration_wizard(self, action_name):
        """ (Sem mudanças) """
        if not self.main_app.communication.connected:
            QMessageBox.warning(self, "Erro", "Conecte a luva antes de calibrar.")
            return
            
        self.current_calibration_action = action_name
        self.current_calibration_step = 1
        self.temp_snapshots = {} # Limpa snapshots anteriores
        self.update_wizard_ui()
        self.stack.setCurrentWidget(self.wizard_widget)

    def update_wizard_ui(self):
        """ ATUALIZADO: Altera o texto para a gravação de batidas. (Sem mudanças) """
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
            # --- LÓGICA DE UI ATUALIZADA ---
            if step == 1: 
                self.wizard_instruction.setText("1/2: Mantenha a mão em <b>REPOUSO</b> e clique em 'Capturar Repouso'.")
                self.wizard_capture_btn.setText("Capturar Repouso")
            if step == 2: 
                self.wizard_instruction.setText("2/2: Prepare-se para a batida.\n\nClique em 'INICIAR' para começar a gravar.")
                self.wizard_capture_btn.setText("INICIAR GRAVAÇÃO")
            if step == 3:
                self.wizard_instruction.setText("<b>GRAVANDO...</b>\n\nFaça o movimento de batida (ex: palhetada) uma ou mais vezes.\n\nClique 'PARAR' quando terminar.")
                self.wizard_capture_btn.setText("PARAR GRAVAÇÃO")
            # --- FIM DA ATUALIZAÇÃO ---

    def process_wizard_step(self):
        """ ATUALIZADO: Salva o snapshot e avança, ou inicia/para a gravação. (Sem mudanças) """
        action = self.current_calibration_action
        step = self.current_calibration_step
        
        snapshot = self.main_app.communication.get_latest_data()
        if not snapshot and step == 1: # Só precisa checar no passo 1
            QMessageBox.warning(self, "Erro", "Luva desconectada no meio da calibração.")
            self.cancel_wizard()
            return

        if "Dedo" in action:
            # Lógica dos dedos permanece a mesma
            if step == 1: self.temp_snapshots["rest"] = snapshot
            if step == 2: self.temp_snapshots["half"] = snapshot
            if step == 3: 
                self.temp_snapshots["full"] = snapshot
                self.finish_finger_calibration() 
                return 
        
        elif "Batida" in action:
            # --- LÓGICA DE PASSOS ATUALIZADA ---
            if step == 1:
                # Capturou o repouso
                self.temp_snapshots["rest"] = snapshot
                # Inicializa o 'peak_snapshot' com os valores de repouso
                self.current_peak_snapshot = snapshot.copy() 
                self.current_calibration_step = 2
            elif step == 2:
                # Botão "INICIAR GRAVAÇÃO" foi clicado
                # Reseta o estado de gravação de pico
                self.current_peak_snapshot = self.temp_snapshots["rest"].copy()
                self.current_peak_magnitude = -1.0
                self.is_recording_peak = True
                self.current_calibration_step = 3
            elif step == 3:
                # Botão "PARAR GRAVAÇÃO" foi clicado
                self.is_recording_peak = False
                self.temp_snapshots["peak"] = self.current_peak_snapshot # Salva o pico gravado
                self.finish_strum_calibration() # Finaliza
                return 
            # --- FIM DA ATUALIZAÇÃO ---
        
        # Avança para o próximo passo (se não retornou)
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
        """ 
        ATUALIZADO: Compara snapshots e encontra o *prefixo* do sensor (ex: "gyro_")
        baseado na maior mudança na *magnitude do vetor de ACELERAÇÃO*.
        """
        max_delta_mag = -1
        detected_prefix = None
        
        for prefix in sensor_prefix_filter:
            try:
                # --- MUDANÇA: Usa ax, ay, az ---
                # Calcula magnitude do vetor no snapshot A (repouso)
                mag_a = math.sqrt(
                    float(snap_a.get(f"{prefix}ax", 0))**2 +
                    float(snap_a.get(f"{prefix}ay", 0))**2 +
                    float(snap_a.get(f"{prefix}az", 0))**2
                )
                # Calcula magnitude do vetor no snapshot B (pico)
                mag_b = math.sqrt(
                    float(snap_b.get(f"{prefix}ax", 0))**2 +
                    float(snap_b.get(f"{prefix}ay", 0))**2 +
                    float(snap_b.get(f"{prefix}az", 0))**2
                )
                # --- FIM DA MUDANÇA ---
                delta_mag = abs(mag_b - mag_a)
                
                if delta_mag > max_delta_mag:
                    max_delta_mag = delta_mag
                    detected_prefix = prefix
                    
            except (ValueError, TypeError):
                continue
                
        return detected_prefix

    def finish_finger_calibration(self):
        """ (Sem mudanças) """
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
        """ 
        ATUALIZADO: Salva o mapeamento com os eixos 'ax, ay, az'.
        """
        action = self.current_calibration_action
        
        # Procura o *grupo* de sensor (gyro_ ou mag_) com maior mudança de magnitude
        detected_prefix = self._find_best_sensor_group(
            self.temp_snapshots["rest"], 
            self.temp_snapshots["peak"],
            sensor_prefix_filter=["gyro_"] # Foca apenas no grupo 'gyro'
        )
        
        if detected_prefix:
            # --- MUDANÇA: Salva ax, ay, az ---
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
            # --- FIM DA MUDANÇA ---
            
            self.main_app.sensor_mappings[action] = mapping
            self.main_app.save_mappings_to_file()
            QMessageBox.information(self, "Sucesso", f"Calibração para '{action}' salva!\nSensor detectado: {detected_prefix} (Aceleração)")
        else:
            QMessageBox.warning(self, "Erro", "Nenhuma variação de sensor de Aceleração detectada. Tente novamente.")
        self.cancel_wizard()

    def cancel_wizard(self):
        """ ATUALIZADO: Garante que a gravação de pico pare. (Sem mudanças) """
        self.stack.setCurrentWidget(self.main_menu_widget)
        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        
        # --- Adicionado ---
        self.is_recording_peak = False # Garante que a gravação pare
        self.current_peak_snapshot = {}
        self.current_peak_magnitude = -1.0
        # --- Fim ---
            
        self.update_calibration_status_labels()

    def go_back(self):
        self.main_app.show_main_menu_screen()


class MainMenuScreen(Screen):
    """ Tela Principal de Emulação e Configuração. (Sem mudanças) """
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
        self.calibrate_btn = QPushButton("Calibrar Sensores (Luva)") 
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

class MainApplication(QMainWindow):
    """
    Classe principal da Interface (QMainWindow).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 600, 700)
        
        self.sensor_mappings = {} 
        self.load_mappings_from_file()
        
        self.communication = Communication() 
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        self.stack = QStackedWidget(self)
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self) 
        self.stack.addWidget(self.instructions_screen)
        self.stack.addWidget(self.main_menu_screen)
        self.stack.addWidget(self.calibration_screen)
        self.setCentralWidget(self.stack)
        
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda 10x/seg


        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) 
        
        self.stack.setCurrentWidget(self.instructions_screen) 
        self._check_network_status() 
        self.apply_stylesheet()

    # ============ Funções de Controle (ATUALIZADA) ============
    
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

    def run_drum_simulation(self):
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ 
        ATUALIZADO: Passa os dados de aceleração corretos para a classe Guitar.
        """
        raw_data = self.communication.get_latest_data()
        self.main_menu_screen.update_sensor_data(raw_data)
        
        logical_data = {}
        if self.communication.connected:
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")
                key_prefix = mapping.get("key_prefix")
                
                if raw_key in raw_data:
                    # Mapeamento de DEDO (chave única)
                    logical_data[action] = raw_data[raw_key]
                elif key_prefix and raw_data.get(f"{key_prefix}ax") is not None:
                    # Mapeamento de BATIDA (prefixo)
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

    # ============ Troca de Telas (Sem Mudanças) ============

    def show_main_menu_screen(self):
        self.stack.setCurrentWidget(self.main_menu_screen)

    def show_calibration_screen(self):
        self.stack.setCurrentWidget(self.calibration_screen)
        
    def show_instructions_screen(self):
        self.stack.setCurrentWidget(self.instructions_screen)

    # ============ Estilo (Sem Mudanças) ============
    
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
            /* Botão de Calibrar no menu */
            QPushButton[text^="Calibrar"] {
                background-color: #333;
                color: #00FFFF;
                border: 1px solid #00FFFF;
            }
            QPushButton[text^="Calibrar"]:hover {
                background-color: #00FFFF;
                color: black;
            }
            /* Botão de Capturar no wizard */
            QPushButton[text^="Capturar"], QPushButton[text^="INICIAR"], QPushButton[text^="PARAR"] {
                background-color: #008000;
                color: white;
                border: 1px solid #00FF00;
                font-weight: bold;
                padding: 12px;
            }
            QPushButton[text^="Capturar"]:hover, QPushButton[text^="INICIAR"]:hover, QPushButton[text^="PARAR"]:hover {
                background-color: #00FF00;
                color: black;
            }
            /* Botão Cancelar no wizard */
            QPushButton[text^="Cancelar"] {
                background-color: #8B0000;
                color: white;
                border: 1px solid #FF4444;
            }
            QPushButton[text^="Cancelar"]:hover {
                background-color: #FF4444;
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
            QLineEdit {
                background-color: #111;
                color: #FFFFFF;
                border: 1px solid #444;
                padding: 4px;
                font-size: 14px;
                min-width: 60px;
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