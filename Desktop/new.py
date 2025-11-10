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
    QCheckBox, QStackedWidget
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot

# ===================================================================
# 1. CLASSES DE LÓGICA (NÃO-UI)
# ===================================================================

class Communication:
    """ 
    Gerencia a conexão REAL com a luva (ESP32) via Wi-Fi (TCP Socket).
    Substitui a simulação.
    """
    
    # IP Padrão da ESP32 em modo AP
    ESP_HOST = '192.168.4.1' 
    
    # Porta (ADIVINHADA) - Altere se o seu WifiServer.cpp usar outra!
    ESP_PORT = 8888 

    def __init__(self):
        self.connected = False
        self.sock = None
        self.receiver_thread = None
        self.data_lock = threading.Lock()
        self.network_status_message = "Desconectado"
        
        # Estrutura de dados padrão (usada para preencher o que não vem da ESP)
        self.last_sensor_data = self._get_default_sensor_data()

    def _get_default_sensor_data(self):
        """ Retorna a estrutura completa de dados zerada. """
        return {
            "flex_dedo1": 0,
            "flex_dedo2": 0,
            "flex_dedo3": 0,
            "flex_dedo4": 0,
            "magnetometro_esq": (0, 0, 0),
            "acelerometro_esq": (0, 0, 0),
            "giroscopio_esq": (0, 0, 0),
            "magnetometro_dir": (0, 0, 0),
            "acelerometro_dir": (0, 0, 0),
            "giroscopio_dir": (0, 0, 0),
        }

    def toggle_connection(self):
        """ Inicia ou para a thread de conexão. """
        if self.connected:
            # Usuário quer desconectar
            self.connected = False
            if self.receiver_thread:
                self.receiver_thread.join() # Espera a thread terminar
            if self.sock:
                self.sock.close()
            self.network_status_message = "Desconectado"
        else:
            # Usuário quer conectar
            self.connected = True
            self.network_status_message = "Conectando..."
            # Inicia a thread para não travar a UI
            self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receiver_thread.start()

    def _receive_loop(self):
        """ Loop principal da thread de rede. """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0) # 5 segundos para conectar
            print(f"Tentando conectar a {self.ESP_HOST}:{self.ESP_PORT}...")
            self.sock.connect((self.ESP_HOST, self.ESP_PORT))
            self.sock.settimeout(1.0) # 1 segundo para ler
            
            self.network_status_message = "Conectado"
            print("Conectado à ESP32!")
            
            buffer = ""
            while self.connected:
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        # Conexão fechada pelo servidor
                        print("Servidor (ESP32) fechou a conexão.")
                        break
                    
                    buffer += data.decode('utf-8')
                    
                    # Processa linhas completas (espera JSON terminado por \n)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        self._parse_data(line)

                except socket.timeout:
                    # Nenhuma mensagem recebida, apenas continua o loop
                    continue
                except Exception as e:
                    print(f"Erro no loop de recebimento: {e}")
                    time.sleep(0.5)

        except socket.error as e:
            print(f"Falha na conexão com a ESP32: {e}")
            print("Verifique se o PC está no Wi-Fi 'ALuvaQueTePariu' e se o IP/Porta estão corretos.")
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
        Decodifica uma linha de dados (JSON) vinda da ESP32
        e atualiza a estrutura 'last_sensor_data'.
        """
        line = line.strip()
        if not line:
            return
            
        try:
            # Espera um JSON, ex: {"flex_dedo1": 1023, "giroscopio_esq": [1.1, 2.2, 3.3]}
            json_data = json.loads(line)
            
            # Começa com a estrutura padrão zerada
            new_data_struct = self._get_default_sensor_data()
            
            # Atualiza a estrutura com os dados que vieram no JSON
            new_data_struct.update(json_data)
            
            # Atualiza o dicionário principal de forma segura
            with self.data_lock:
                self.last_sensor_data = new_data_struct
                
        except json.JSONDecodeError:
            print(f"Dado recebido mal formatado (não é JSON): '{line}'")
        except Exception as e:
            print(f"Erro ao decodificar dados: {e}")

    def get_latest_data(self):
        """ Chamado pelo Timer da UI para obter os dados mais recentes. """
        with self.data_lock:
            return self.last_sensor_data.copy()

    def get_live_sensor_value(self, sensor_name):
        """ 
        Obtém o valor ATUAL de um sensor específico para a calibração.
        (Substitui 'get_random_sensor_value')
        """
        with self.data_lock:
            if sensor_name in self.last_sensor_data:
                val = self.last_sensor_data[sensor_name]
                # Se for um valor 3D (tupla/lista), usa o primeiro (e.g., X) para calibrar
                if isinstance(val, (list, tuple)) and len(val) > 0:
                    return val[0] 
                elif isinstance(val, (int, float)):
                    return val
            return 0 # Valor padrão se não encontrado

    def get_status_message(self):
        """ Retorna a mensagem de status da rede para a UI. """
        return self.network_status_message

class Emulator:
    """ Gerencia a saída de emulação (Teclado/Joystick). (Sem mudanças) """
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
    """ Gerencia a captura da câmera e o processamento do MediaPipe. (Sem mudanças) """
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
        self.communication = Communication() # Usado pela Guitarra

class Instrument(InputData):
    """ Classe base para um instrumento. (Sem mudanças) """
    def __init__(self):
        super().__init__()

class Drum(Instrument):
    """ Implementação da Bateria. (Sem mudanças) """
    def __init__(self):
        super().__init__()

    def run_simulation(self):
        circulos = [
            {'center': (0.1, 0.8), 'raio': 40, 'cor': (255, 0, 0)}, 
            {'center': (0.3, 0.8), 'raio': 40, 'cor': (255, 0, 0)}, 
            {'center': (0.7, 0.8), 'raio': 40, 'cor': (255, 0, 0)}, 
            {'center': (0.9, 0.8), 'raio': 40, 'cor': (255, 0, 0)}  
        ]

        with self.camera.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while self.camera.cap.isOpened():
                success, frame = self.camera.cap.read()
                if not success:
                    print("Erro ao acessar a câmera.")
                    break

                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                results = pose.process(image)
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                h, w, _ = image.shape

                def to_pixel(p): return int(p.x * w), int(p.y * h)

                pulso_esq = (-100, -100)
                pulso_dir = (-100, -100)

                if results.pose_landmarks:
                    self.camera.mp_drawing.draw_landmarks(
                        image, results.pose_landmarks, self.camera.mp_pose.POSE_CONNECTIONS)

                    landmarks = results.pose_landmarks.landmark

                    left_shoulder = landmarks[self.camera.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                    left_elbow = landmarks[self.camera.mp_pose.PoseLandmark.LEFT_ELBOW.value]
                    left_wrist = landmarks[self.camera.mp_pose.PoseLandmark.LEFT_WRIST.value]
                    right_shoulder = landmarks[self.camera.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                    right_elbow = landmarks[self.camera.mp_pose.PoseLandmark.RIGHT_ELBOW.value]
                    right_wrist = landmarks[self.camera.mp_pose.PoseLandmark.RIGHT_WRIST.value]

                    l_sh, l_el, l_wr = to_pixel(left_shoulder), to_pixel(left_elbow), to_pixel(left_wrist)
                    r_sh, r_el, r_wr = to_pixel(right_shoulder), to_pixel(right_elbow), to_pixel(right_wrist)

                    pulso_esq = l_wr
                    pulso_dir = r_wr

                    ang_esq = Camera.calcular_angulo(l_sh, l_el, l_wr)
                    ang_dir = Camera.calcular_angulo(r_sh, r_el, r_wr)

                    cv2.putText(image, f"Angulo Esq: {ang_esq:.1f}", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(image, f"Angulo Dir: {ang_dir:.1f}", (10, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                for c in circulos:
                    cx = int(c['center'][0] * w)
                    cy = int(c['center'][1] * h)
                    cor = c['cor']
                    
                    for pulso in [pulso_esq, pulso_dir]:
                        dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                        if dist <= c['raio']:
                            cor = (0, 0, 255) 
                    
                    cv2.circle(image, (cx, cy), c['raio'], cor, 2)

                cv2.imshow('Air Band - Bateria (Pressione Q para sair)', image)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        
        self.camera.release()


class Guitar(Instrument):
    """ Implementação da Guitarra. (Sem mudanças) """
    def __init__(self):
        pass

    def process_data(self, sensor_data, calibrated_data, emulator: Emulator):
        pass


# ===================================================================
# 2. CLASSES DE INTERFACE (PyQt5 UI)
# (Pequenas mudanças na Calibração e Menu Principal)
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
            <li>Vá para a tela de Calibração e calibre os sensores.</li>
            <li>Retorne ao menu e toque!</li>
        </ol>
        
        <b>Bateria (Câmera):</b>
        <ol>
            <li>Posicione-se em frente à câmera.</li>
            <li>No menu principal, clique em 'Ver Retorno da Câmera'.</li>
            <li>Movimente seus pulsos para 'acertar' os alvos.</li>
        </ol>
        """
        layout.addWidget(QLabel(instructions_text))
        
        layout.addStretch() 
        
        self.continue_btn = QPushButton("Ir para o Menu Principal ➡️")
        self.continue_btn.clicked.connect(self.main_app.show_main_menu_screen)
        layout.addWidget(self.continue_btn)
        
        self.setLayout(layout)

class CalibrationScreen(Screen):
    """ Tela de Calibração dos Sensores. """
    def __init__(self, parent):
        super().__init__(parent)

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

        layout.addWidget(QLabel("<b>MÃO ESQUERDA (DEDOS):</b>"))
        for i in range(1, 5):
            btn = QPushButton(f"Dedo {i}")
            btn.clicked.connect(lambda _, idx=i: self.calibrate(f"flex_dedo{idx}"))
            layout.addWidget(btn)

        layout.addWidget(QLabel("<b>MÃO ESQUERDA (MOVIMENTO):</b>"))
        for sensor in ["magnetometro_esq", "acelerometro_esq", "giroscopio_esq"]:
            btn = QPushButton(f"{sensor.replace('_', ' ').title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate(s))
            layout.addWidget(btn)

        layout.addWidget(QLabel("<b>MÃO DIREITA (MOVIMENTO):</b>"))
        for sensor in ["magnetometro_dir", "acelerometro_dir", "giroscopio_dir"]:
            btn = QPushButton(f"{sensor.replace('_', ' ').title()}")
            btn.clicked.connect(lambda _, s=sensor: self.calibrate(s))
            layout.addWidget(btn)

        layout.addWidget(QLabel("Dados dos Sensores (Tempo Real):"))
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        layout.addWidget(self.sensor_output)

        back_btn = QPushButton("⬅️ Voltar ao Menu")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)

        self.setLayout(layout)

        # Timer para atualizar dados
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)
        
    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start(100) # Atualiza mais rápido para calibração

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop() 

    def update_error_label(self):
        self.error_label.setText(f"Margem: {self.error_slider.value()}%")

    def calibrate(self, sensor_name):
        # Acessa 'communication' da aplicação principal
        if not self.main_app.communication.connected:
            self.sensor_output.append(
                "<span style='color:#FF4444;'>⚠️ Não é possível calibrar — luva desconectada.</span>"
            )
            return

        taxa = self.error_slider.value() / 100.0
        
        # *** MUDANÇA: Obtém valor real ao invés de aleatório ***
        val = self.main_app.communication.get_live_sensor_value(sensor_name)
        
        limite = val * (1 - taxa)
        
        # Salva o valor calibrado na aplicação principal
        self.main_app.calibrated_values[sensor_name] = limite
        
        self.sensor_output.append(
            f"<span style='color:#00FFFF;'>"
            f"{sensor_name.replace('_', ' ').title()} calibrado com valor {val:.2f} "
            f"(limite {limite:.2f}, erro {self.error_slider.value()}%)</span><br>"
        )

    def update_sensor_data(self):
        # Obtém os dados mais recentes da classe de comunicação
        data = self.main_app.communication.get_latest_data()
        
        if not self.main_app.communication.connected:
            self.sensor_output.setHtml(
                "<span style='color:#FF4444; font-weight:bold;'>⚠️ Luva desconectada — conecte para visualizar os sensores.</span>"
            )
        else:
            # Formata os dados (mesma lógica de antes)
            texto = (
                "<b><span style='color:#00FF00;'>MÃO ESQUERDA:</span></b><br>"
                + "".join([f"<span>Dedo {i+1}: {data.get(f'flex_dedo{i+1}', 0)}</span><br>" for i in range(4)])
                + f"Magnetômetro: {data.get('magnetometro_esq', (0,0,0))}<br>"
                + f"Acelerômetro: {data.get('acelerometro_esq', (0,0,0))}<br>"
                + f"Giroscópio: {data.get('giroscopio_esq', (0,0,0))}<br>"
                "<hr>"
                "<b><span style='color:#00FF00;'>MÃO DIREITA:</span></b><br>"
                + f"Magnetômetro: {data.get('magnetometro_dir', (0,0,0))}<br>"
                + f"Acelerômetro: {data.get('acelerometro_dir', (0,0,0))}<br>"
                + f"Giroscópio: {data.get('giroscopio_dir', (0,0,0))}<br>"
            )
            self.sensor_output.setHtml(texto)

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

        self.calibrate_btn = QPushButton("Calibrar Sensores (Luva)")
        self.calibrate_btn.clicked.connect(self.main_app.show_calibration_screen)
        layout.addWidget(self.calibrate_btn)
        
        # Label de status que será atualizado pelo Timer
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

        self.debug_label = QLabel("Dados dos Sensores (Luva):")
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        
        layout.addWidget(self.debug_label)
        layout.addWidget(self.sensor_output)
        
        self.debug_check.toggled.connect(self.debug_label.setVisible)
        self.debug_check.toggled.connect(self.sensor_output.setVisible)
        
        self.debug_label.setVisible(False)
        self.sensor_output.setVisible(False)
        
        self.setLayout(layout)

    def update_sensor_data(self, data):
        """ Atualiza o QTextEdit com novos dados da luva. """
        # Só atualiza o terminal se ele estiver visível
        if not self.sensor_output.isVisible():
            return
            
        texto = (
            "<b><span style='color:#00FF00;'>MÃO ESQUERDA:</span></b><br>"
            + "".join([f"<span>Dedo {i+1}: {data.get(f'flex_dedo{i+1}', 0)}</span><br>" for i in range(4)])
            + f"Magnetômetro: {data.get('magnetometro_esq', (0,0,0))}<br>"
            + f"Acelerômetro: {data.get('acelerometro_esq', (0,0,0))}<br>"
            + f"Giroscópio: {data.get('giroscopio_esq', (0,0,0))}<br>"
            "<hr>"
            "<b><span style='color:#00FF00;'>MÃO DIREITA:</span></b><br>"
            + f"Magnetômetro: {data.get('magnetometro_dir', (0,0,0))}<br>"
            + f"Acelerômetro: {data.get('acelerometro_dir', (0,0,0))}<br>"
            + f"Giroscópio: {data.get('giroscopio_dir', (0,0,0))}<br>"
        )
        self.sensor_output.setHtml(texto)

    def update_connection_status(self, is_connected, status_message):
        """ 
        Atualiza os botões e labels de status da luva.
        Recebe a 'status_message' da thread de rede.
        """
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
    Gerencia as telas e a lógica de comunicação usando QStackedWidget.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘")
        self.setGeometry(300, 200, 600, 700)
        
        # Estado e Lógica
        self.calibrated_values = {}
        self.communication = Communication() # <-- Usa a nova classe de Wi-Fi
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
        # Timer para processar dados (rápido)
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        self.glove_timer.start(100) # Roda constantemente (10x/seg)

        # Timer para atualizar status da UI (lento)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500) # Roda 2x/seg
        
        # Configuração inicial
        self.stack.setCurrentWidget(self.instructions_screen) 
        self._check_network_status() # Atualiza o status da UI imediatamente
        self.apply_stylesheet()

    # ============ Funções de Controle ============

    def toggle_glove_connection(self):
        """ Apenas 'avisa' a classe de comunicação para conectar/desconectar. """
        self.communication.toggle_connection()
        # O _check_network_status timer vai atualizar a UI
        
    def _check_network_status(self):
        """ Atualiza a UI com o status da conexão da thread. """
        status = self.communication.get_status_message()
        is_connected = self.communication.connected
        self.main_menu_screen.update_connection_status(is_connected, status)

    def run_drum_simulation(self):
        """ Inicia a simulação de bateria (bloqueia a UI principal). """
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ 
        Chamado pelo timer rápido (glove_timer).
        Processa os dados para emulação, se conectado.
        """
        # Sempre pega os dados mais recentes (ou 0s)
        sensor_data = self.communication.get_latest_data()
        
        # Atualiza o terminal de debug (se estiver visível)
        self.main_menu_screen.update_sensor_data(sensor_data)
        
        # Só processa a lógica da guitarra se estivermos conectados
        if self.communication.connected:
            self.guitar.process_data(
                sensor_data, 
                self.calibrated_values, 
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
        self.communication.connected = False # Para a thread de rede
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