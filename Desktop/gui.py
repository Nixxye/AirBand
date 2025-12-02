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
from worker import InstrumentWorker
from camera import CameraProcessor

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

        # 1. Se o instrumento selecionado é Guitarra (Luva)
        # if self.main_menu_tab.get_selected_instrument() == "Guitarra (Luva)":
        #     # ... (código existente para processar dados da luva) ...

        #     logical_data = {}
        #     if self.communication.connected:
        #         # ... (lógica de mapeamento da luva) ...
                
        #         # Processamento da Guitarra
        #         if logical_data:
        #             self.guitar.process_data(
        #                 logical_data, 
        #                 self.sensor_mappings, 
        #                 self.emulator
        #             )

        # # 2. Se o instrumento selecionado é Bateria (Camera)
        # elif self.main_menu_tab.get_selected_instrument() == "Bateria (Camera)":
            
        #     # Pega a lista de hits ativos da MainMenuScreen
        #     active_drums = self.main_menu_tab.get_active_drum_keys()
            
        #     # Processa os hits na classe Drum
        #     self.drum.process_data(
        #         logical_data,
        #         active_drums, 
        #         self.emulator
        #     )

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


from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QTextEdit, QComboBox, QMessageBox,
    QSlider, QGroupBox
)
from PyQt5.QtCore import QTimer, Qt

class CalibrationScreen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent
        self.current_calibration_action = None
        self.current_calibration_step = 0
        self.temp_snapshots = {}
        
        self.logical_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", 
            "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)",
            "Batida (Mestra)", "Batida (Escrava)"
        ]

        # Layout Principal
        main_layout = QVBoxLayout(self)
        
        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        # Telas
        self.main_menu_widget = self._create_main_menu_widget()
        self.wizard_widget = self._create_wizard_widget()
        self.stack.addWidget(self.main_menu_widget)
        self.stack.addWidget(self.wizard_widget)

        # Debug
        self.sensor_output = QTextEdit()
        self.sensor_output.setReadOnly(True)
        self.sensor_output.setFixedHeight(80) # Reduzi um pouco para caber os sliders
        main_layout.addWidget(self.sensor_output)

        self.setLayout(main_layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sensor_data)

    def _create_main_menu_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # --- Título ---
        layout.addWidget(QLabel("<h2>Mapeamento & Ajustes Finos</h2>"))

        # --- Área de Calibração (Botões) ---
        calib_group = QGroupBox("Calibração de Sensores")
        calib_layout = QVBoxLayout()
        calib_group.setLayout(calib_layout)

        self.action_labels = {}
        for action in self.logical_actions:
            hbox = QHBoxLayout()
            label = QLabel(f"<b>{action}:</b> --")
            self.action_labels[action] = label
            btn = QPushButton(f"Calibrar")
            btn.clicked.connect(lambda _, a=action: self.start_calibration_wizard(a))
            hbox.addWidget(label)
            hbox.addWidget(btn)
            calib_layout.addLayout(hbox)
        
        layout.addWidget(calib_group)

        # --- NOVO: Área de Ajustes Globais (Sliders) ---
        settings_group = QGroupBox("Ajustes de Sensibilidade (Global)")
        settings_layout = QVBoxLayout()
        settings_group.setLayout(settings_layout)

        # 1. Trigger Threshold
        self.lbl_thresh = QLabel("Limiar de Disparo (0.50)")
        self.slider_thresh = QSlider(Qt.Horizontal)
        self.slider_thresh.setRange(5, 95) # 0.05 a 0.95
        self.slider_thresh.setValue(50)    # Default 0.50
        self.slider_thresh.valueChanged.connect(self.update_guitar_params)
        settings_layout.addWidget(self.lbl_thresh)
        settings_layout.addWidget(self.slider_thresh)

        # 2. Filter Alpha
        self.lbl_alpha = QLabel("Suavização/Velocidade (0.40)")
        self.slider_alpha = QSlider(Qt.Horizontal)
        self.slider_alpha.setRange(1, 100) # 0.01 a 1.00
        self.slider_alpha.setValue(40)     # Default 0.40
        self.slider_alpha.valueChanged.connect(self.update_guitar_params)
        settings_layout.addWidget(self.lbl_alpha)
        settings_layout.addWidget(self.slider_alpha)

        # 3. Crosstalk Gain
        self.lbl_cross = QLabel("Força da Máscara/Crosstalk (1.00)")
        self.slider_cross = QSlider(Qt.Horizontal)
        self.slider_cross.setRange(0, 200) # 0.00 a 2.00
        self.slider_cross.setValue(100)    # Default 1.00
        self.slider_cross.valueChanged.connect(self.update_guitar_params)
        settings_layout.addWidget(self.lbl_cross)
        settings_layout.addWidget(self.slider_cross)

        layout.addWidget(settings_group)

        layout.addStretch()
        back = QPushButton("Voltar ao Menu")
        back.clicked.connect(lambda: self.main_app.tabs.setCurrentWidget(self.main_app.main_menu_tab))
        layout.addWidget(back)
        return widget

    def update_guitar_params(self):
        """Chamado sempre que um slider é movido."""
        # Converte valores dos sliders (int) para float
        thresh_val = self.slider_thresh.value() / 100.0
        alpha_val = self.slider_alpha.value() / 100.0
        cross_val = self.slider_cross.value() / 100.0

        # Atualiza Labels
        self.lbl_thresh.setText(f"Limiar de Disparo: <b>{thresh_val:.2f}</b> (Baixo=Sensível, Alto=Duro)")
        self.lbl_alpha.setText(f"Suavização (Alpha): <b>{alpha_val:.2f}</b> (Baixo=Lento/Liso, Alto=Rápido/Tremido)")
        self.lbl_cross.setText(f"Força Crosstalk: <b>{cross_val:.2f}</b> (1.0=Padrão)")

        # Injeta diretamente na classe Guitar (via Worker)
        if hasattr(self.main_app, 'worker') and self.main_app.worker and self.main_app.worker.guitar:
            guitar = self.main_app.worker.guitar
            guitar.TRIGGER_THRESHOLD = thresh_val
            guitar.FILTER_ALPHA = alpha_val
            guitar.CROSSTALK_GAIN = cross_val
            # print(f"Params atualizados: T={thresh_val}, A={alpha_val}, C={cross_val}")

    def _create_wizard_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.wizard_title = QLabel("Calibrando...")
        self.wizard_instruction = QLabel("Instruções...")
        
        # --- SELETOR MANUAL DE SENSOR ---
        self.sensor_selector_label = QLabel("Selecione o Sensor Físico:")
        self.sensor_selector = QComboBox()
        
        self.wizard_capture_btn = QPushButton("Capturar")
        self.wizard_capture_btn.clicked.connect(self.process_wizard_step)
        
        self.wizard_cancel_btn = QPushButton("Cancelar")
        self.wizard_cancel_btn.clicked.connect(self.cancel_wizard)

        layout.addWidget(self.wizard_title)
        layout.addWidget(self.sensor_selector_label)
        layout.addWidget(self.sensor_selector) 
        layout.addWidget(self.wizard_instruction)
        layout.addStretch()
        layout.addWidget(self.wizard_capture_btn)
        layout.addWidget(self.wizard_cancel_btn)
        return widget

    def update_sensor_data(self):
        raw_data = self.main_app.communication.get_latest_data()
        if not raw_data: return
        
        if self.sensor_selector.count() == 0:
            sensors = sorted([k for k in raw_data.keys() if "adc" in k or "gy" in k])
            self.sensor_selector.addItems(sensors)

        texto = " | ".join([f"{k}:{v}" for k,v in raw_data.items() if "adc" in k])
        self.sensor_output.setText(texto)

    def start_calibration_wizard(self, action_name):
        self.current_calibration_action = action_name
        self.current_calibration_step = 0 
        self.temp_snapshots = {}
        
        current_map = self.main_app.sensor_mappings.get(action_name, {})
        saved_key = current_map.get("key", "")
        
        self.update_wizard_ui()
        
        if saved_key:
            idx = self.sensor_selector.findText(saved_key)
            if idx >= 0: self.sensor_selector.setCurrentIndex(idx)
            
        self.stack.setCurrentWidget(self.wizard_widget)

    def update_wizard_ui(self):
        action = self.current_calibration_action
        step = self.current_calibration_step
        self.wizard_title.setText(f"Calibrando: {action}")

        if step == 0:
            self.sensor_selector.setVisible(True)
            self.sensor_selector_label.setVisible(True)
            self.sensor_selector.setEnabled(True)
            self.wizard_instruction.setText("Escolha qual sensor físico corresponde a este dedo.")
            self.wizard_capture_btn.setText("Confirmar Sensor")
        
        elif step == 1:
            self.sensor_selector.setEnabled(False) 
            self.wizard_instruction.setText("Deixe a mão relaxada (REPOUSO) e capture.")
            self.wizard_capture_btn.setText("Capturar Repouso")
            
        elif step == 2:
            self.wizard_instruction.setText(
                "Dobre <b>APENAS ESTE DEDO</b> até o final.\n"
                "Tente não mexer os outros, mas deixe eles virem naturalmente se a pele puxar."
            )
            self.wizard_capture_btn.setText("Capturar Full e Finalizar")

    def process_wizard_step(self):
        step = self.current_calibration_step
        
        if step == 0:
            self.current_calibration_step = 1
            self.update_wizard_ui()
            return

        snapshot = self.main_app.communication.get_latest_data()
        
        if step == 1:
            self.temp_snapshots["rest"] = snapshot
            self.current_calibration_step = 2
            self.update_wizard_ui()
            
        elif step == 2:
            self.temp_snapshots["full"] = snapshot
            if "Dedo" in self.current_calibration_action:
                self.finish_finger_calibration_manual()
            else:
                self.finish_generic_calibration()

    def finish_finger_calibration_manual(self):
        action = self.current_calibration_action
        chosen_key = self.sensor_selector.currentText() 
        
        rest_snapshot = self.temp_snapshots["rest"]
        full_snapshot = self.temp_snapshots["full"]
        
        val_rest = rest_snapshot.get(chosen_key, 0)
        val_full = full_snapshot.get(chosen_key, 0)
        
        interference_profile = {}
        for k, v in full_snapshot.items():
            if "adc" in k and k != chosen_key:
                interference_profile[k] = v

        mapping = {
            "key": chosen_key,
            "rest": val_rest,
            "full": val_full,
            "crosstalk_ref": interference_profile 
        }
        
        self.main_app.sensor_mappings[action] = mapping
        self.main_app.save_mappings_to_file()
        
        QMessageBox.information(self, "Sucesso", f"Calibrado!\nSensor: {chosen_key}\nPerfil de interferência salvo.")
        self.cancel_wizard()

    def finish_generic_calibration(self):
        self.cancel_wizard()

    def cancel_wizard(self):
        self.stack.setCurrentWidget(self.main_menu_widget)

    def start_timer(self):
        self.timer.start(30)
        self.update_calibration_status_labels()
        # Sincroniza sliders com valores atuais da Guitarra ao abrir a tela
        if hasattr(self.main_app, 'worker') and self.main_app.worker and self.main_app.worker.guitar:
             g = self.main_app.worker.guitar
             self.slider_thresh.setValue(int(g.TRIGGER_THRESHOLD * 100))
             self.slider_alpha.setValue(int(g.FILTER_ALPHA * 100))
             self.slider_cross.setValue(int(g.CROSSTALK_GAIN * 100))

    def stop_timer(self):
        self.timer.stop()

    def update_calibration_status_labels(self):
        for action, label in self.action_labels.items():
            if action in self.main_app.sensor_mappings:
                data = self.main_app.sensor_mappings[action]
                info = data.get("key", "OK")
                label.setText(f"<b>{action}:</b> <span style='color:#00FF00;'>[OK: {info}]</span>")
            else:
                label.setText(f"<b>{action}:</b> <span style='color:#FFA500;'>(Não calibrado)</span>")
class MainMenuScreen(Screen):
    """ Tela Principal (Aba 'Controle'). """
    def __init__(self, parent):
        super().__init__(parent)
        self.active_drums_list = []
        # Inicializa com vetor vazio de 4 posições
        self.current_drum_vector = [0, 0, 0, 0] 

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
        # ✅ NOVO: Conecta a mudança do combobox ao worker
        self.instrument_combo.currentTextChanged.connect(self.on_instrument_changed)
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

        # Botão para alternar transparência da janela principal (50% / 100%)
        self.transparent_btn = QPushButton("Alternar Transparência (50%)")
        self.transparent_btn.setCheckable(True)
        self.transparent_btn.clicked.connect(self.toggle_transparency)
        general_layout.addWidget(self.transparent_btn)

        # Botão para manter a janela sempre acima das outras
        self.always_on_top_btn = QPushButton("Manter Sempre Acima (OFF)")
        self.always_on_top_btn.setCheckable(True)
        self.always_on_top_btn.clicked.connect(self.toggle_always_on_top)
        general_layout.addWidget(self.always_on_top_btn)

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

        # --- CÂMERA WIDGET ---
        self.camera_widget = CameraWidget(self) 
        # Conecta sinal para atualizar dados locais e debug
        self.camera_widget.camera_data_signal.connect(self.update_camera_data)
        # ✅ NOVO: Conecta também ao worker
        self.camera_widget.camera_data_signal.connect(self.main_app.worker.update_camera_data)
        
        # Inicia Câmera IMEDIATAMENTE (para detecção em background)
        self.camera_widget.start_camera()

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
        """ Alterna entre mostrar o vídeo ou deixar rodando escondido. """
        
        # 1. Se a câmera caiu por algum motivo (erro de USB), tenta reiniciar
        if not self.camera_widget.processor.is_active():
             self.camera_widget.start_camera()

        # 2. Verifica se estamos MOSTRANDO o vídeo atualmente
        is_showing = self.camera_widget.show_video_feed

        if is_showing:
            # ESCONDER (Modo Performance)
            self.camera_widget.set_feedback_visible(False)
            self.camera_feedback_btn.setText("Ver Retorno da Câmera (Bateria)")
            self.camera_widget.video_label.setStyleSheet("") 
        else:
            # MOSTRAR (Modo Feedback)
            self.camera_widget.set_feedback_visible(True)
            self.camera_feedback_btn.setText("Parar Retorno da Câmera (Bateria)")

    def update_camera_data(self, data):
        """ Recebe os dados da câmera, atualiza vetor e debug. """
        
        # 1. Salva o vetor bruto que veio da câmera
        self.current_drum_vector = data.get("Drum_Vector", [0, 0, 0, 0])

        # 2. Atualiza UI (Debug) se habilitado
        if not self.debug_group.isChecked():
            return

        texto = "<span style='color:#00FFFF;'>--- DADOS DA BATERIA (CÂMERA) ---</span>\n"
        texto += f"<span style='color:#FFFF00;'>Vert. Esq:</span> {data['Angulo_Esq_Vert']:.1f}°\n"
        texto += f"<span style='color:#FFFF00;'>Vert. Dir:</span> {data['Angulo_Dir_Vert']:.1f}°\n"
        
        # Display do Vetor
        vec_str = str(self.current_drum_vector)
        hit_color = "#FF4444" if 1 in self.current_drum_vector else "#AAAAAA"
        texto += f"<span style='color:{hit_color}; font-weight:bold;'>VETOR:</span> {vec_str}\n"

        self.sensor_output.setHtml(texto)

    def get_active_drum_keys(self):
        """ Retorna o vetor de ativação dos tambores diretamente. """
        return self.current_drum_vector
    
    def get_selected_instrument(self):
        """ Retorna o texto do item selecionado no ComboBox de Instrumento. """
        return self.instrument_combo.currentText()
    def on_instrument_changed(self, instrument_name):
        """ Chamado quando o usuário muda o combobox de instrumento. """
        print(f"✅ [UI] Instrumento alterado para: {instrument_name}")
        self.main_app.worker.set_instrument(instrument_name)

    def toggle_transparency(self, checked: bool):
        """ Alterna opacidade da janela principal entre 1.0 e 0.5. """
        if checked:
            self.main_app.setWindowOpacity(0.2)
            self.transparent_btn.setText("Restaurar Opacidade (100%)")
        else:
            self.main_app.setWindowOpacity(1.0)
            self.transparent_btn.setText("Alternar Transparência (70%)")

    def toggle_always_on_top(self, checked: bool):
        """ Alterna a flag 'sempre acima' da janela principal. """
        # Define/limpa a flag e reaplica exibindo a janela para forçar atualização
        self.main_app.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.main_app.show()
        if checked:
            self.always_on_top_btn.setText("Manter Sempre Acima (ON)")
        else:
            self.always_on_top_btn.setText("Manter Sempre Acima (OFF)")
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
    Widget PyQt que gerencia a exibição da imagem.
    Delega todo o processamento pesado para a classe CameraProcessor.
    """
    camera_data_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Instancia a lógica separada
        self.processor = CameraProcessor()
        
        self.w, self.h = 640, 480
        self.setFixedSize(self.w, self.h)
        self.show_video_feed = False 

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.video_label = QLabel("Câmera Desligada")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #111; color: #555;")
        layout.addWidget(self.video_label)
        
        # Timer de Atualização (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def start_camera(self):
        """ Liga a câmera e o timer. """
        if self.processor.start():
            self.timer.start(30)
            self.set_feedback_visible(False) 
        else:
            self.video_label.setText("Erro ao abrir câmera!")

    def stop_camera(self):
        """ Para tudo e libera recursos. """
        self.timer.stop()
        self.processor.stop()
        self.video_label.setText("Câmera Desligada")
        self.video_label.clear()

    def set_feedback_visible(self, visible):
        """ Liga/Desliga apenas a renderização visual na tela. """
        self.show_video_feed = visible
        if visible:
            self.video_label.setText("Carregando feed...")
        else:
            self.video_label.clear()
            self.video_label.setText("Câmera rodando em background...")

    @pyqtSlot()
    def update_frame(self):
        """ Loop principal chamado pelo Timer. """
        # 1. Pede para o processador fazer a mágica
        frame_rgb, data = self.processor.process_frame()
        
        if frame_rgb is None: 
            # Se retornou None, a câmera caiu ou foi fechada
            # self.stop_camera() # Opcional: parar se cair
            return

        # 2. Emite os dados lógicos (vetor de bateria, ângulos)
        self.camera_data_signal.emit(data)

        # 3. Atualiza a tela APENAS se o usuário quiser ver (Feedback)
        if self.show_video_feed:
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
