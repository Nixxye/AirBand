import sys
import random
import cv2
import mediapipe as mp
import math

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
# 1. CLASSES DE LÓGICA (Não-UI)
# (Estas classes permanecem inalteradas)
# ===================================================================

class Communication:
    """ Gerencia a conexão e simulação de dados da luva (sensores). """
    def __init__(self):
        self.connected = False

    def toggle_connection(self):
        """ Alterna o estado de conexão. """
        self.connected = not self.connected
        return self.connected

    def generate_sensor_data(self):
        """ Simula a leitura de todos os sensores da luva. """
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
        """ Simula a leitura de um único sensor para calibração. """
        if "flex" in sensor_name:
            return random.randint(0, 1023)
        else:
            return random.uniform(-50, 50)

class Emulator:
    """ Gerencia a saída de emulação (Teclado/Joystick). """
    def __init__(self):
        self.gamepad = vg.VX360Gamepad() if HAS_VGAMEPAD else None
        if HAS_VGAMEPAD:
            print("Controlador Virtual (vgamepad) conectado.")
        else:
            print("vgamepad não encontrado. Emulação de joystick desabilitada.")

    def process_guitar_action(self, action):
        """ (LÓGICA FUTURA) Recebe uma ação 'guitarra' e a traduz para o gamepad/teclado. """
        pass

    def process_drum_action(self, action):
        """ (LÓGICA FUTURA) Recebe uma ação 'bateria' e a traduz para o gamepad/teclado. """
        pass

class Camera:
    """ Gerencia a captura da câmera e o processamento do MediaPipe. """
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

    @staticmethod
    def calcular_angulo(a, b, c):
        """ Função estática para calcular o ângulo entre três pontos. """
        angulo = math.degrees(
            math.atan2(c[1] - b[1], c[0] - b[0]) -
            math.atan2(a[1] - b[1], a[0] - b[0])
        )
        angulo = abs(angulo)
        if angulo > 180:
            angulo = 360 - angulo
        return angulo

    def release(self):
        """ Libera a câmera. """
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()


class InputData:
    """ Classe base que agrupa as fontes de entrada. """
    def __init__(self):
        self.camera = Camera()
        self.communication = Communication() # Usado pela Guitarra

class Instrument(InputData):
    """ Classe base para um instrumento. """
    def __init__(self):
        super().__init__()

class Drum(Instrument):
    """
    Implementação da Bateria.
    Usa a Câmera para detectar os movimentos.
    """
    def __init__(self):
        super().__init__()

    def run_simulation(self):
        """ Executa o loop principal da simulação de bateria com OpenCV. """
        
        # Define os círculos (coordenadas normalizadas e raio em pixels)
        circulos = [
            {'center': (0.1, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
            {'center': (0.3, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
            {'center': (0.7, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
            {'center': (0.9, 0.8), 'raio': 40, 'cor': (255, 0, 0)}   # Azul
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

                    # Pontos dos braços
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

                    # (Opcional) Desenha informações de debug
                    cv2.putText(image, f"Angulo Esq: {ang_esq:.1f}", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(image, f"Angulo Dir: {ang_dir:.1f}", (10, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                # Desenha os círculos e checa colisão com pulsos
                for c in circulos:
                    cx = int(c['center'][0] * w)
                    cy = int(c['center'][1] * h)
                    cor = c['cor']
                    
                    for pulso in [pulso_esq, pulso_dir]:
                        dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                        if dist <= c['raio']:
                            cor = (0, 0, 255)  # vermelho
                            # (LÓGICA FUTURA) Aqui você enviaria a ação para o Emulator
                            # self.parent.emulator.process_drum_action("HIT_LEFT_SNARE")
                    
                    cv2.circle(image, (cx, cy), c['raio'], cor, 2)

                cv2.imshow('Air Band - Bateria (Pressione Q para sair)', image)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break
        
        self.camera.release()


class Guitar(Instrument):
    """
    Implementação da Guitarra.
    Usa a Comunicação da luva para detectar os movimentos.
    """
    def __init__(self):
        # A Guitarra não usa a câmera, então não chamamos super().__init__()
        # Ela usará a instância de 'Communication' da classe principal.
        pass

    def process_data(self, sensor_data, calibrated_data, emulator: Emulator):
        """
        (LÓGICA FUTURA) Processa os dados dos sensores da luva
        e envia comandos para o emulador.
        """
        pass


# ===================================================================
# 2. CLASSES DE INTERFACE (PyQt5 UI)
# ===================================================================

class Screen(QWidget):
    """ Classe base para todas as 'telas' da aplicação. """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent # Referência à MainApplication

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
            <li>No menu principal, conecte a Luva.</li>
            <li>Vá para a tela de Calibração.</li>
            <li>Calibre cada sensor para definir os limites de ativação.</li>
            <li>Retorne ao menu e toque!</li>
        </ol>
        
        <b>Bateria (Câmera):</b>
        <ol>
            <li>Posicione-se em frente à câmera.</li>
            <li>No menu principal, clique em 'Ver Retorno da Câmera'.</li>
            <li>Movimente seus pulsos para 'acertar' os alvos.</li>
        </ol>
        
        Use o menu principal para configurar seu instrumento e saída.
        """
        layout.addWidget(QLabel(instructions_text))
        
        layout.addStretch() # Empurra o botão para baixo
        
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
        """ Chamado quando o widget é exibido. """
        super().showEvent(event)
        self.timer.start(1000) # Inicia o timer da tela de calibração

    def hideEvent(self, event):
        """ Chamado quando o widget é ocultado. """
        super().hideEvent(event)
        self.timer.stop() # Para o timer da tela de calibração

    def update_error_label(self):
        self.error_label.setText(f"Margem: {self.error_slider.value()}%")

    def calibrate(self, sensor_name):
        # Acessa 'communication' e 'calibrated_values' da aplicação principal
        if not self.main_app.communication.connected:
            self.sensor_output.append(
                "<span style='color:#FF4444;'>⚠️ Não é possível calibrar — luva desconectada.</span>"
            )
            return

        taxa = self.error_slider.value() / 100.0
        val = self.main_app.communication.get_random_sensor_value(sensor_name)
        limite = val * (1 - taxa)
        
        # Salva o valor calibrado na aplicação principal
        self.main_app.calibrated_values[sensor_name] = limite
        
        self.sensor_output.append(
            f"<span style='color:#00FFFF;'>"
            f"{sensor_name.replace('_', ' ').title()} calibrado com valor {val:.2f} "
            f"(limite {limite:.2f}, erro {self.error_slider.value()}%)</span><br>"
        )

    def update_sensor_data(self):
        if not self.main_app.communication.connected:
            self.sensor_output.setHtml(
                "<span style='color:#FF4444; font-weight:bold;'>⚠️ Luva desconectada — conecte para visualizar os sensores.</span>"
            )
            return

        data = self.main_app.communication.generate_sensor_data()
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
        self.main_app.show_main_menu_screen()


class MainMenuScreen(Screen):
    """ Tela Principal de Emulação e Configuração. """
    def __init__(self, parent):
        super().__init__(parent)
        
        layout = QVBoxLayout()
        
        # --- Seção de Configuração ---
        layout.addWidget(QLabel("<h2>Menu Principal ⚙️</h2>"))
        layout.addWidget(QLabel("<b>1. Selecione o Instrumento:</b>"))
        self.instrument_combo = QComboBox()
        self.instrument_combo.addItems(["Guitarra (Luva)", "Bateria (Camera)"])
        layout.addWidget(self.instrument_combo)

        layout.addWidget(QLabel("<b>2. Selecione a Saída:</b>"))
        self.output_combo = QComboBox()
        self.output_combo.addItems(["Teclado", "Joystick"])
        layout.addWidget(self.output_combo)
        
        # --- Seção da Guitarra (Luva) ---
        layout.addWidget(QLabel("<h3>Controles da Guitarra 🎸</h3>"))
        self.connect_glove_btn = QPushButton("Conectar à Luva")
        self.connect_glove_btn.clicked.connect(self.main_app.toggle_glove_connection)
        layout.addWidget(self.connect_glove_btn)

        self.calibrate_btn = QPushButton("Calibrar Sensores (Luva)")
        self.calibrate_btn.clicked.connect(self.main_app.show_calibration_screen)
        layout.addWidget(self.calibrate_btn)
        
        self.status_label = QLabel("Status Luva: Desconectado")
        layout.addWidget(self.status_label)

        # --- Seção da Bateria (Câmera) ---
        layout.addWidget(QLabel("<h3>Controles da Bateria 🥁</h3>"))
        self.camera_feedback_btn = QPushButton("Ver Retorno da Câmera (Bateria)")
        self.camera_feedback_btn.clicked.connect(self.main_app.run_drum_simulation)
        layout.addWidget(self.camera_feedback_btn)

        # --- Seção Geral / Debug ---
        layout.addWidget(QLabel("<h3>Geral</h3>"))
        self.instructions_btn = QPushButton("Ver Instruções 📝")
        self.instructions_btn.clicked.connect(self.main_app.show_instructions_screen)
        layout.addWidget(self.instructions_btn)

        # Checkbox para o terminal de debug
        self.debug_check = QCheckBox("Habilitar Terminal de Debug (Luva)")
        self.debug_check.setChecked(False) # Começa desligado
        layout.addWidget(self.debug_check)

        # Terminal de Debug (controlado pelo checkbox)
        self.debug_label = QLabel("Dados dos Sensores (Luva):")
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        
        layout.addWidget(self.debug_label)
        layout.addWidget(self.sensor_output)
        
        # Conecta o checkbox aos slots setVisible
        self.debug_check.toggled.connect(self.debug_label.setVisible)
        self.debug_check.toggled.connect(self.sensor_output.setVisible)
        
        # Esconde o terminal e o label inicialmente
        self.debug_label.setVisible(False)
        self.sensor_output.setVisible(False)
        
        self.setLayout(layout)

    def update_sensor_data(self, data):
        """ Atualiza o QTextEdit com novos dados da luva. """
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

    def update_connection_status(self, is_connected):
        """ Atualiza os botões e labels de status da luva. """
        if is_connected:
            self.status_label.setText("Status Luva: Conectado")
            self.connect_glove_btn.setText("Desconectar Luva")
            self.sensor_output.clear()
        else:
            self.status_label.setText("Status Luva: Desconectado")
            self.connect_glove_btn.setText("Conectar à Luva")
            if not self.sensor_output.isVisible(): # Só atualiza se o terminal estiver visível
                self.sensor_output.setHtml(
                    "<span style='color:#FF4444; font-weight:bold;'>⚠️ Luva desconectada.</span>"
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
        self.communication = Communication()
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        # --- Configuração do QStackedWidget ---
        # 1. Crie o "baralho" de telas
        self.stack = QStackedWidget(self)

        # 2. Crie as telas (passando 'self' como a referência 'main_app')
        self.instructions_screen = InstructionsScreen(self)
        self.main_menu_screen = MainMenuScreen(self)
        self.calibration_screen = CalibrationScreen(self)

        # 3. Adicione as telas ao "baralho"
        self.stack.addWidget(self.instructions_screen)
        self.stack.addWidget(self.main_menu_screen)
        self.stack.addWidget(self.calibration_screen)
        
        # 4. Defina o "baralho" (stack) como o ÚNICO widget central
        self.setCentralWidget(self.stack)
        # --- Fim da Configuração do Stack ---
        
        # Timer principal para a luva
        self.glove_timer = QTimer(self)
        self.glove_timer.timeout.connect(self.update_glove_data)
        
        # Configuração inicial
        # *** MUDANÇA: Começa na tela de instruções ***
        self.stack.setCurrentWidget(self.instructions_screen) 
        
        self.main_menu_screen.update_connection_status(False)
        self.apply_stylesheet()

    # ============ Funções de Controle ============

    def toggle_glove_connection(self):
        """ Conecta/Desconecta da luva e inicia/para o timer. """
        is_connected = self.communication.toggle_connection()
        self.main_menu_screen.update_connection_status(is_connected)
        
        if is_connected:
            self.glove_timer.start(100) # Atualiza dados da luva 10x/seg
        else:
            self.glove_timer.stop()

    def run_drum_simulation(self):
        """ Inicia a simulação de bateria (bloqueia a UI principal). """
        self.hide()
        self.drum.run_simulation()
        self.show()

    def update_glove_data(self):
        """ Chamado pelo timer para atualizar dados da luva. """
        if not self.communication.connected:
            return
            
        sensor_data = self.communication.generate_sensor_data()
        self.main_menu_screen.update_sensor_data(sensor_data)
        
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
        # (O seu CSS está ótimo, sem mudanças)
        self.setStyleSheet("""
            QMainWindow { background-color: #111; color: white; }
            QWidget { color: white; } /* Cor padrão para todos os widgets */
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
        """ Garante que a câmera seja liberada ao fechar a janela. """
        self.drum.camera.release()
        event.accept()

# ===================================================================
# 3. EXECUÇÃO DA APLICAÇÃO
# (Sem mudanças)
# ===================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApplication()
    window.show()
    sys.exit(app.exec_())