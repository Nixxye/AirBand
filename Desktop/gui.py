import math
import json
import cv2
import mediapipe as mp
import numpy as np
import sys

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QSlider,
    QCheckBox, QStackedWidget, QFormLayout,
    QScrollArea, QLineEdit, QMessageBox,
    QGroupBox, QFrame, QTabWidget, QMainWindow, QApplication, QGridLayout
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot, pyqtSignal

# --- Imports dos Módulos ---
from communication import Communication
from emulator import Emulator
from instruments import Guitar, Drum
from worker import InstrumentWorker  # <--- Import do Worker

import pyqtgraph as pg
from collections import deque
import pyqtgraph.opengl as gl
import numpy as np
from collections import deque


class SensorVisualizer3D(QWidget):
    # --- CONSTANTES DE CALIBRAÇÃO ---
    CONST_X = 0.5  # Linha Verde 2D
    CONST_Y = 0.8  # Linha Vermelha 2D

    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent
        
        main_layout = QVBoxLayout(self)

        # 1. ÁREA 3D (VETORES)
        self.view_3d = gl.GLViewWidget()
        self.view_3d.opts['distance'] = 20
        self.view_3d.setWindowTitle('Vetores de Aceleração')
        self.view_3d.setFixedHeight(400)

        gz = gl.GLGridItem()
        gz.translate(0, 0, -1)
        self.view_3d.addItem(gz)
        self.view_3d.addItem(gl.GLAxisItem())

        # --- VETORES VIVOS (Linhas Sólidas) ---
        self.master_line = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,0]]), color=(0, 1, 1, 1), width=3, antialias=True)
        self.view_3d.addItem(self.master_line)
        
        self.slave_line = gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,0]]), color=(1, 0, 1, 1), width=3, antialias=True)
        self.view_3d.addItem(self.slave_line)

        # --- VETORES DE CALIBRAÇÃO (Pontilhados/Scatter) ---
        # Tamanho aumentado para 8 e pxMode=True para garantir visibilidade
        self.master_ref_up = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), color=(0, 1, 0, 0.6), size=8, pxMode=True)
        self.master_ref_down = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), color=(1, 0, 0, 0.6), size=8, pxMode=True)
        self.view_3d.addItem(self.master_ref_up)
        self.view_3d.addItem(self.master_ref_down)

        self.slave_ref_up = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), color=(0, 1, 0, 0.6), size=8, pxMode=True)
        self.slave_ref_down = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), color=(1, 0, 0, 0.6), size=8, pxMode=True)
        self.view_3d.addItem(self.slave_ref_up)
        self.view_3d.addItem(self.slave_ref_down)

        main_layout.addWidget(self.view_3d)

        # 2. ÁREA 2D (GRÁFICOS INDIVIDUAIS DOS DEDOS)
        adc_grid = QGridLayout()
        main_layout.addLayout(adc_grid)

        self.finger_configs = [
            {"name": "Dedo 1 (Indicador)", "label": "D1: Indicador"},
            {"name": "Dedo 2 (Médio)",     "label": "D2: Médio"},
            {"name": "Dedo 3 (Anelar)",    "label": "D3: Anelar"},
            {"name": "Dedo 4 (Mindinho)",  "label": "D4: Mindinho"},
        ]

        self.adc_plots = []
        self.adc_curves = []
        self.threshold_lines = []
        
        self.buffer_size = 100
        self.adc_data = [deque([0]*self.buffer_size, maxlen=self.buffer_size) for _ in range(4)]

        for i, config in enumerate(self.finger_configs):
            plot = pg.PlotWidget(title=config["label"])
            plot.showGrid(x=True, y=True, alpha=0.3)
            
            # Zoom fixo 0 - 3.3V
            plot.setYRange(0, 3.3)      
            plot.setXRange(0, self.buffer_size)
            plot.setMouseEnabled(x=False, y=False)
            
            curve = plot.plot(pen=pg.mkPen('y', width=2))
            
            line_x = pg.InfiniteLine(angle=0, pen=pg.mkPen('g', style=pg.QtCore.Qt.DashLine, width=1))
            line_y = pg.InfiniteLine(angle=0, pen=pg.mkPen('r', style=pg.QtCore.Qt.DashLine, width=1))
            
            plot.addItem(line_x)
            plot.addItem(line_y)

            row = i // 2
            col = i % 2
            adc_grid.addWidget(plot, row, col)

            self.adc_plots.append(plot)
            self.adc_curves.append(curve)
            self.threshold_lines.append((line_x, line_y))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_visuals)

    def start_timer(self):
        self.timer.start(30)

    def stop_timer(self):
        self.timer.stop()

    def _make_dotted_line(self, x, y, z, steps=20):
        """ Cria pontos interpolados float32 para OpenGL """
        # Se o vetor for nulo (ou quase nulo), retorna vazio para esconder
        if abs(x) < 0.1 and abs(y) < 0.1 and abs(z) < 0.1:
            return np.empty((0, 3), dtype=np.float32)

        xs = np.linspace(0, x, steps)
        ys = np.linspace(0, y, steps)
        zs = np.linspace(0, z, steps)
        
        # Empilha e converte para float32 (Essencial para pyqtgraph opengl)
        return np.column_stack((xs, ys, zs)).astype(np.float32)

    def update_visuals(self):
        raw = self.main_app.communication.get_latest_data()
        if not raw: return
        mappings = self.main_app.sensor_mappings

        scale = 0.5 
        
        # --- MESTRA (Live) ---
        mx, my, mz = raw.get('gyro_ax', 0), raw.get('gyro_ay', 0), raw.get('gyro_az', 0)
        self.master_line.setData(pos=np.array([[0, 0, 0], [mx*scale, my*scale, mz*scale]]))

        # --- ESCRAVA (Live) ---
        sx = raw.get('slave_ax', 0) 
        sy = raw.get('slave_ay', 0)
        sz = raw.get('slave_az', 0)
        self.slave_line.setData(pos=np.array([[0, 0, 0], [sx*scale, sy*scale, sz*scale]]))

        # --- CALIBRAÇÃO (Pontilhada) ---
        
        # 1. Mestra
        if "Batida (Mestra)" in mappings:
            m_calib = mappings["Batida (Mestra)"]
            
            up = m_calib.get("up", {})
            ux, uy, uz = up.get("ax", 0), up.get("ay", 0), up.get("az", 0)
            self.master_ref_up.setData(pos=self._make_dotted_line(ux*scale, uy*scale, uz*scale))
            
            down = m_calib.get("down", {})
            dx, dy, dz = down.get("ax", 0), down.get("ay", 0), down.get("az", 0)
            self.master_ref_down.setData(pos=self._make_dotted_line(dx*scale, dy*scale, dz*scale))
        else:
            # Limpa se não calibrado
            self.master_ref_up.setData(pos=np.empty((0, 3)))
            self.master_ref_down.setData(pos=np.empty((0, 3)))
        
        # 2. Escrava
        if "Batida (Escrava)" in mappings:
            s_calib = mappings["Batida (Escrava)"]
            
            up = s_calib.get("up", {})
            ux, uy, uz = up.get("ax", 0), up.get("ay", 0), up.get("az", 0)
            self.slave_ref_up.setData(pos=self._make_dotted_line(ux*scale, uy*scale, uz*scale))
            
            down = s_calib.get("down", {})
            dx, dy, dz = down.get("ax", 0), down.get("ay", 0), down.get("az", 0)
            self.slave_ref_down.setData(pos=self._make_dotted_line(dx*scale, dy*scale, dz*scale))
        else:
            self.slave_ref_up.setData(pos=np.empty((0, 3)))
            self.slave_ref_down.setData(pos=np.empty((0, 3)))

        # --- GRÁFICOS 2D ---
        for i, curve in enumerate(self.adc_curves):
            val = raw.get(f'adc_v{i+32}', 0) 
            self.adc_data[i].append(val)
            curve.setData(self.adc_data[i])

            finger_name = self.finger_configs[i]["name"]
            if finger_name in mappings:
                max_val = mappings[finger_name].get("full", 0)
                self.threshold_lines[i][0].setPos(max_val * self.CONST_X)
                self.threshold_lines[i][1].setPos(max_val * self.CONST_Y)
            else:
                self.threshold_lines[i][0].setPos(0)
                self.threshold_lines[i][1].setPos(0)

# =============================================================================
# CLASSES PRINCIPAIS
# =============================================================================

class MainApplication(QMainWindow):
    """
    Classe principal da Interface (QMainWindow).
    Gerencia UI e Thread de Processamento (Worker).
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘 (Multi-Thread + Slave)")
        self.setGeometry(300, 200, 800, 700)

        self.sensor_mappings = {}
        self.load_mappings_from_file()

        # --- 1. Instancia a Lógica (Shared Resources) ---
        self.communication = Communication() # Thread de rede inicia internamente
        self.emulator = Emulator()           # Singleton
        self.guitar = Guitar()
        self.drum = Drum()

        # --- 2. Instancia e Inicia o WORKER (Thread de Processamento) ---
        # O worker assume o loop pesado de verificar sensores e acionar emulador
        self.worker = InstrumentWorker(
            self.communication, 
            self.guitar, 
            self.drum, 
            self.emulator
        )
        self.worker.update_mappings(self.sensor_mappings) # Passa config inicial
        self.worker.start() # Inicia loop de alta frequência

        # --- 3. Configuração da UI ---
        self.tabs = QTabWidget(self)
        self.tabs.setMovable(True)

        # Instancia as telas
        self.graphs_tab = SensorVisualizer3D(self)
        self.instructions_tab = InstructionsScreen(self)
        self.main_menu_tab = MainMenuScreen(self)
        self.calibration_tab = CalibrationScreen(self)

        self.tabs.addTab(self.instructions_tab, "🏠 Início")
        self.tabs.addTab(self.main_menu_tab, "⚙️ Controle")
        self.tabs.addTab(self.calibration_tab, "🎛️ Calibração")
        self.tabs.addTab(self.graphs_tab, "📈 Gráficos")

        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- 4. Timers da Interface (Apenas Visualização) ---
        
        # Timer Visual: Atualiza apenas os textos de debug na tela.
        # 30ms (~33FPS) é suficiente para o olho humano.
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_ui_visuals)
        self.ui_timer.start(30) 

        # Timer de Conexão: Verifica status a cada 500ms
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

        if current_widget == self.graphs_tab:
            self.graphs_tab.start_timer()
        else:
            self.graphs_tab.stop_timer()

    # ============ Funções de Controle ============
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
            
            # CRÍTICO: Atualiza a thread worker imediatamente com os novos mapeamentos
            if hasattr(self, 'worker'):
                self.worker.update_mappings(self.sensor_mappings)
                
        except Exception as e:
            print(f"Erro ao salvar mapeamentos: {e}")

    def toggle_glove_connection(self):
        # A comunicação roda em thread própria, só chamamos o método
        self.communication.toggle_connection()

    def _check_network_status(self):
        status = self.communication.get_status_message()
        is_connected = self.communication.connected
        self.main_menu_tab.update_connection_status(is_connected, status)

    def update_ui_visuals(self):
        """ 
        Substitui o antigo 'update_glove_data'.
        Apenas atualiza a interface visual. O processamento lógico
        agora ocorre dentro de 'self.worker'.
        """
        # Obtém cópia thread-safe dos dados apenas para mostrar na tela
        raw_data = self.communication.get_latest_data()

        # Passa dados para o terminal na aba "Controle"
        self.main_menu_tab.update_sensor_data(raw_data)
        
        # A lógica da guitarra (self.guitar.process_data) foi removida daqui 
        # pois agora roda no worker.py

    def closeEvent(self, event):
        """ Garante encerramento limpo de todas as threads. """
        if hasattr(self, 'worker'):
            self.worker.stop() # Para a thread de lógica
        self.communication.connected = False # Para a thread de rede
        self.emulator.fechar() # Reseta controle virtual
        event.accept()


class Screen(QWidget):
    """ 
    Classe base para todas as 'telas' da aplicação. 
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
            <li>Clique em "Calibrar Dedo 1" e siga as instruções.</li>
            <li>Para "Batidas", clique em "Batida (Giroscópio)". Você gravará: Repouso, Batida p/ Cima e Batida p/ Baixo.</li>
            <li>O app irá <b>auto-detectar</b> qual eixo do giroscópio usar (Master ou Slave).</li>
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


class CalibrationScreen(QWidget):
    """
    Tela de Calibração com Wizard.
    - Dedos: 3 Etapas (Repouso, Meio, Cheio).
    - Batida: Focada em GIROSCÓPIO (Aceleração Angular).
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent

        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Batida (Mestra)", "Batida (Escrava)"
        ]

        self.is_recording_peak = False
        self.current_peak_val = 0.0
        self.current_peak_axis_data = {} # Guarda o snapshot exato do pico

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
        
        back_btn = QPushButton("⬅️ Voltar ao Controle")
        back_btn.clicked.connect(
            lambda: self.main_app.tabs.setCurrentWidget(self.main_app.main_menu_tab)
        )
        layout.addWidget(back_btn)
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

        # --- LÓGICA DE CAPTURA DE PICO (GIROSCÓPIO) ---
        if self.is_recording_peak and self.current_calibration_action:
            prefix = "slave_" if "Escrava" in self.current_calibration_action else "gyro_"
            
            # Pega valor absoluto dos 3 eixos de rotação
            gx = raw_data.get(f"{prefix}gx", 0)
            gy = raw_data.get(f"{prefix}gy", 0)
            gz = raw_data.get(f"{prefix}gz", 0)
            
            # Magnitude total da rotação (Aceleração Angular Total)
            magnitude = math.sqrt(gx**2 + gy**2 + gz**2)
            
            # Se for o movimento mais forte até agora, salva esse snapshot
            if magnitude > self.current_peak_val:
                self.current_peak_val = magnitude
                self.current_peak_axis_data = {
                    "gx": gx, "gy": gy, "gz": gz
                }

    def update_calibration_status_labels(self):
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                data = self.main_app.sensor_mappings[action]
                # Tenta mostrar info relevante (Eixo ou Tecla)
                info = data.get("key", data.get("axis", "OK"))
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

        # --- DEDOS ---
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

        # --- BATIDA (GIROSCÓPIO) ---
        elif "Batida" in action:
            if step == 1:
                self.wizard_instruction.setText("1/2: <b>REPOUSO</b>\n\nFique com a mão parada.\nIsso zera o ruído do sensor.")
                self.wizard_capture_btn.setText("Capturar Repouso")
            elif step == 2:
                self.wizard_instruction.setText("2/2: <b>BATIDA PARA BAIXO</b>\n\nClique INICIAR, faça uma batida forte PARA BAIXO, e pare.")
                self.wizard_capture_btn.setText("INICIAR Captura")
            elif step == 3:
                self.wizard_instruction.setText("<b>LENDO MOVIMENTO...</b>\n\nFaça o movimento para BAIXO agora!\nO sistema vai detectar o eixo de rotação.")
                self.wizard_capture_btn.setText("PARAR e Salvar")

    def process_wizard_step(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        snapshot = self.main_app.communication.get_latest_data()

        # --- DEDOS ---
        if "Dedo" in action:
            if step == 1: self.temp_snapshots["rest"] = snapshot
            if step == 2: self.temp_snapshots["half"] = snapshot
            if step == 3:
                self.temp_snapshots["full"] = snapshot
                self.finish_finger_calibration()
                return
            self.current_calibration_step += 1
            self.update_wizard_ui()

        # --- BATIDA ---
        elif "Batida" in action:
            if step == 1:
                # Captura repouso (opcional, mas bom pra offset)
                self.temp_snapshots["rest"] = snapshot
                self.current_calibration_step = 2
                self.update_wizard_ui()
            
            elif step == 2:
                # Inicia Gravação de Pico Gyro
                self.current_peak_val = 0
                self.current_peak_axis_data = {} 
                self.is_recording_peak = True
                self.current_calibration_step = 3
                self.update_wizard_ui()
            
            elif step == 3:
                # Para Gravação e Analisa
                self.is_recording_peak = False
                self.finish_strum_calibration()

    def finish_finger_calibration(self):
        action = self.current_calibration_action
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
        
        if best_key and max_delta > 100:
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
            QMessageBox.warning(self, "Falha", "Pouca variação detectada.")
        self.cancel_wizard()

    def finish_strum_calibration(self):
        """ 
        Salva o VETOR COMPLETO (3 eixos) do giroscópio no pico do movimento.
        """
        action = self.current_calibration_action
        prefix = "slave_" if "Escrava" in action else "gyro_"
        
        # Dados do pico capturado (dicionário com gx, gy, gz)
        peak_vector = self.current_peak_axis_data
        
        if not peak_vector:
             QMessageBox.warning(self, "Erro", "Nenhum movimento forte detectado.")
             self.cancel_wizard()
             return

        # 1. Calcula a Magnitude total desse vetor de pico
        gx = peak_vector.get("gx", 0)
        gy = peak_vector.get("gy", 0)
        gz = peak_vector.get("gz", 0)
        peak_magnitude = math.sqrt(gx**2 + gy**2 + gz**2)
        
        # 2. Define o Limiar (Threshold)
        # O gatilho será acionado se a projeção do movimento atual nesse vetor
        # for maior que X% da força original.
        threshold = peak_magnitude * 0.4 # 40% de sensibilidade

        mapping = {
            "key_prefix": prefix,
            "vector": peak_vector, # Salva {gx:..., gy:..., gz:...}
            "threshold": threshold 
        }
        
        self.main_app.sensor_mappings[action] = mapping
        self.main_app.save_mappings_to_file()
        
        QMessageBox.information(self, "Sucesso", 
            f"Batida Vetorial Calibrada!\n\n"
            f"Vetor: [{gx}, {gy}, {gz}]\n"
            f"Força Ref: {peak_magnitude:.0f}\n"
            f"Limiar: {threshold:.0f}")
        
        self.cancel_wizard()

    def cancel_wizard(self):
        self.stack.setCurrentWidget(self.main_menu_widget)
        self.is_recording_peak = False
        self.current_calibration_action = None
        self.temp_snapshots = {}
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
        self.output_combo.addItems(["Joystick", "Teclado"])
        self.output_combo.currentTextChanged.connect(self.change_emulator_type)
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

    def change_emulator_type(self, text):
        if text == "Joystick":
            self.main_app.emulator.set_tipo_emulacao(Emulator.TIPO_CONTROLE)
        else:
            self.main_app.emulator.set_tipo_emulacao(Emulator.TIPO_TECLADO)

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