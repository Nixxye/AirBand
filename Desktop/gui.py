import math
import json
import cv2
import mediapipe as mp
import numpy as np
import sys
from collections import deque

from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPolygon, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QSlider,
    QCheckBox, QStackedWidget, QFormLayout,
    QScrollArea, QLineEdit, QMessageBox,
    QGroupBox, QFrame, QTabWidget, QMainWindow, QApplication,
    QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt, pyqtSlot, pyqtSignal, QPoint

# --- Imports dos Módulos ---
# Certifique-se que os arquivos communication.py, emulator.py, etc, estão na mesma pasta
from communication import Communication
from emulator import Emulator
from instruments import Guitar, Drum
from worker import InstrumentWorker

# =============================================================================
# WIDGETS DE VISUALIZAÇÃO PERSONALIZADOS (GRÁFICOS E VETORES)
# =============================================================================

class RealTimeGraph(QWidget):
    """
    Widget que desenha um gráfico de linhas em tempo real para 4 canais (ADCs).
    Usa QPainter para desenhar polígonos baseados em um buffer circular (deque).
    """
    def __init__(self, channels=4, max_points=100, parent=None):
        super().__init__(parent)
        self.channels = channels
        self.max_points = max_points
        # Buffer para armazenar histórico: Lista de deques
        self.data = [deque([0]*max_points, maxlen=max_points) for _ in range(channels)]
        
        # Cores para cada dedo: Vermelho, Verde, Azul, Amarelo
        self.colors = [QColor(255, 50, 50), QColor(50, 255, 50), QColor(50, 100, 255), QColor(255, 255, 50)]
        self.labels = ["Dedo 1", "Dedo 2", "Dedo 3", "Dedo 4"]
        
        self.setMinimumHeight(200) # Altura mínima para ficar visível
        self.setStyleSheet("background-color: #111; border: 1px solid #444;")

    def update_values(self, values_list):
        """ Recebe uma lista de valores [v1, v2, v3, v4] e adiciona ao histórico """
        for i, val in enumerate(values_list):
            if i < self.channels:
                self.data[i].append(val)
        self.update() # Força o repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Desenha Grid
        painter.setPen(QPen(QColor(50, 50, 50), 1, Qt.DotLine))
        painter.drawLine(0, h//2, w, h//2)
        painter.drawLine(0, h//4, w, h//4)
        painter.drawLine(0, h*3//4, w, h*3//4)

        # Configuração de Escala (ADC 0 a 4095)
        max_val = 4095
        step_x = w / (self.max_points - 1)

        # Desenha as linhas
        for i in range(self.channels):
            painter.setPen(QPen(self.colors[i], 2))
            polyline = []
            
            # Converte o deque para pontos X,Y na tela
            for j, val in enumerate(self.data[i]):
                x = j * step_x
                # Inverte Y (0 embaixo, 4095 em cima)
                normalized_h = (val / max_val) * h
                y = h - normalized_h
                polyline.append(QPoint(int(x), int(y)))
            
            if len(polyline) > 1:
                painter.drawPolyline(QPolygon(polyline))

            # Legenda simples no topo
            painter.drawText(10 + (i * 70), 20, self.labels[i])


class VectorScope(QWidget):
    """
    Visualiza vetores 3D.
    - Círculo central: Eixos X e Y.
    - Barra lateral: Eixo Z.
    """
    def __init__(self, title="Vector", parent=None):
        super().__init__(parent)
        self.title = title
        self.vx = 0
        self.vy = 0
        self.vz = 0
        self.setMinimumSize(150, 150) # Tamanho quadrado
        self.setStyleSheet("background-color: #222; border-radius: 8px; border: 1px solid #444;")

    def update_vector(self, x, y, z):
        self.vx = x
        self.vy = y
        self.vz = z
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        cx, cy = w // 2, h // 2
        
        # Raio do radar (deixa espaço para a barra Z na direita)
        radius = min(w, h) // 2 - 10
        radar_radius = radius - 15 

        # 1. Título
        painter.setPen(Qt.white)
        painter.drawText(5, 15, self.title)

        # 2. Desenha Círculo do Radar (X/Y)
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(cx - radar_radius - 10, cy - radar_radius, radar_radius * 2, radar_radius * 2)
        
        # Cruz central
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawLine(cx - radar_radius - 10, cy, cx + radar_radius - 10, cy)
        painter.drawLine(cx - 10, cy - radar_radius, cx - 10, cy + radar_radius)

        # 3. Desenha Vetor X/Y
        # Normalização empírica: Assume que o acelerômetro vai de -16000 a 16000 aprox (MPU6050 raw)
        # Se seus valores forem floats pequenos (ex: g-force), ajuste o divisor.
        scale = radar_radius / 16000.0 if abs(self.vx) > 100 else radar_radius / 2.0 
        
        end_x = (cx - 10) + int(self.vx * scale)
        end_y = cy - int(self.vy * scale) # Y invertido na tela

        painter.setPen(QPen(Qt.cyan, 3))
        painter.drawLine(cx - 10, cy, end_x, end_y)
        painter.setBrush(QBrush(Qt.cyan))
        painter.drawEllipse(end_x - 3, end_y - 3, 6, 6)

        # 4. Desenha Barra Z (Direita)
        bar_x = w - 15
        bar_w = 10
        bar_center_y = h // 2
        
        # Fundo da barra
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(40, 40, 40))
        painter.drawRect(bar_x, 10, bar_w, h - 20)

        # Valor Z
        z_px = int(self.vz * scale)
        # Limita visualmente para não sair do widget
        z_px = max(-(h//2)+15, min((h//2)-15, z_px))

        color_z = Qt.yellow if z_px > 0 else Qt.magenta
        painter.setBrush(color_z)
        # Desenha retângulo a partir do centro
        painter.drawRect(bar_x, bar_center_y, bar_w, -z_px)

        painter.setPen(Qt.white)
        painter.drawText(bar_x - 5, h - 5, "Z")


# =============================================================================
# CLASSES PRINCIPAIS
# =============================================================================

class MainApplication(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Air Band 🤘 (Gráficos Reais)")
        self.setGeometry(100, 100, 1000, 800) # Aumentei um pouco a altura

        self.sensor_mappings = {}
        self.load_mappings_from_file()

        # --- Lógica ---
        self.communication = Communication()
        self.emulator = Emulator()
        self.guitar = Guitar()
        self.drum = Drum()

        self.worker = InstrumentWorker(
            self.communication, self.guitar, self.drum, self.emulator
        )
        self.worker.update_mappings(self.sensor_mappings)
        self.worker.start()

        # --- UI ---
        self.tabs = QTabWidget(self)
        self.instructions_tab = InstructionsScreen(self)
        self.main_menu_tab = MainMenuScreen(self)
        self.calibration_tab = CalibrationScreen(self)

        self.tabs.addTab(self.instructions_tab, "🏠 Início")
        self.tabs.addTab(self.main_menu_tab, "⚙️ Controle")
        self.tabs.addTab(self.calibration_tab, "🎛️ Calibração")

        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- Timers ---
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_ui_visuals)
        self.ui_timer.start(30) # 30ms para fluidez do gráfico

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._check_network_status)
        self.status_timer.start(500)

        self._check_network_status()

    def on_tab_changed(self, index):
        if self.tabs.widget(index) == self.calibration_tab:
            self.calibration_tab.start_timer()
        else:
            self.calibration_tab.stop_timer()

    def load_mappings_from_file(self):
        try:
            with open('sensor_mappings.json', 'r') as f:
                self.sensor_mappings = json.load(f)
        except: self.sensor_mappings = {}

    def save_mappings_to_file(self):
        try:
            with open('sensor_mappings.json', 'w') as f:
                json.dump(self.sensor_mappings, f, indent=4)
            if hasattr(self, 'worker'):
                self.worker.update_mappings(self.sensor_mappings)
        except Exception as e: print(e)

    def toggle_glove_connection(self):
        self.communication.toggle_connection()

    def _check_network_status(self):
        self.main_menu_tab.update_connection_status(
            self.communication.connected, 
            self.communication.get_status_message()
        )

    def update_ui_visuals(self):
        # Pega dados e manda para a aba principal atualizar gráficos e texto
        raw_data = self.communication.get_latest_data()
        self.main_menu_tab.update_sensor_data(raw_data)

    def closeEvent(self, event):
        if hasattr(self, 'worker'): self.worker.stop()
        self.communication.connected = False
        self.emulator.fechar()
        event.accept()

# --- Classes Auxiliares de Tela ---

class Screen(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent

class InstructionsScreen(Screen):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Instruções</h2>"))
        layout.addWidget(QLabel("Conecte a luva na aba Controle e siga para Calibração."))
        layout.addStretch()
        btn = QPushButton("Ir para Controle")
        btn.clicked.connect(lambda: self.main_app.tabs.setCurrentIndex(1))
        layout.addWidget(btn)
        self.setLayout(layout)

class CalibrationScreen(Screen):
    # Mantida a lógica original, simplificada para focar na resposta do gráfico
    def __init__(self, parent):
        super().__init__(parent)
        # ... (Mantendo estrutura básica para não quebrar) ...
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        
        l = QVBoxLayout(self)
        self.stack = QStackedWidget()
        l.addWidget(self.stack)
        
        # Menu simples para exemplo
        menu = QWidget()
        lm = QVBoxLayout(menu)
        lm.addWidget(QLabel("<h3>Menu de Calibração (Funcionalidade Completa no Código Original)</h3>"))
        self.txt = QTextEdit()
        lm.addWidget(self.txt)
        self.stack.addWidget(menu)
        self.setLayout(l)

    def start_timer(self): self.timer.start(50)
    def stop_timer(self): self.timer.stop()
    def update_data(self):
        d = self.main_app.communication.get_latest_data()
        self.txt.setText(str(d))
    # Adicione aqui os métodos de Wizard originais se precisar calibrar novamente

class MainMenuScreen(Screen):
    """ Tela Principal com GRÁFICOS e VETORES """
    def __init__(self, parent):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- COLUNA DA ESQUERDA (Controles) ---
        left_column = QVBoxLayout()
        
        # Config
        config_group = QGroupBox("Configuração")
        cl = QFormLayout(config_group)
        self.cb_inst = QComboBox(); self.cb_inst.addItems(["Guitarra", "Bateria"])
        self.cb_out = QComboBox(); self.cb_out.addItems(["Joystick", "Teclado"])
        self.cb_out.currentTextChanged.connect(self.change_emul)
        cl.addRow("Instrumento:", self.cb_inst)
        cl.addRow("Saída:", self.cb_out)
        left_column.addWidget(config_group)

        # Guitarra
        guitar_group = QGroupBox("Conexão Luva")
        gl = QVBoxLayout(guitar_group)
        self.btn_conn = QPushButton("Conectar Luva")
        self.btn_conn.clicked.connect(self.main_app.toggle_glove_connection)
        self.lbl_status = QLabel("Desconectado")
        gl.addWidget(self.btn_conn); gl.addWidget(self.lbl_status)
        left_column.addWidget(guitar_group)

        # Bateria
        drum_group = QGroupBox("Bateria")
        dl = QVBoxLayout(drum_group)
        self.btn_cam = QPushButton("Alternar Câmera")
        self.btn_cam.clicked.connect(self.toggle_cam)
        dl.addWidget(self.btn_cam)
        left_column.addWidget(drum_group)

        left_column.addStretch()
        main_layout.addLayout(left_column, 1)

        # --- COLUNA DA DIREITA (Scroll Area para Gráficos) ---
        # Usamos ScrollArea pois os gráficos ocupam bastante espaço vertical
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        right_layout = QVBoxLayout(scroll_content)
        right_layout.setSpacing(20)

        # 1. Terminal de Texto (Mantido conforme pedido)
        term_group = QGroupBox("Terminal de Dados (Valores)")
        term_group.setCheckable(True); term_group.setChecked(True)
        t_layout = QVBoxLayout(term_group)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFixedHeight(120)
        self.terminal.setStyleSheet("font-family: Consolas; font-size: 11px; color: #0f0; background: #000;")
        t_layout.addWidget(self.terminal)
        right_layout.addWidget(term_group)

        # 2. Gráfico Real dos Dedos (ADC)
        graph_group = QGroupBox("Gráfico: Tensão dos Dedos (ADC)")
        g_layout = QVBoxLayout(graph_group)
        self.adc_graph = RealTimeGraph(channels=4, max_points=150)
        g_layout.addWidget(self.adc_graph)
        right_layout.addWidget(graph_group)

        # 3. Vetores (Aceleração Mestra e Escrava)
        vector_group = QGroupBox("Visualização Vetorial (Acelerômetros)")
        v_layout = QHBoxLayout(vector_group)
        
        # Mestra
        v1_layout = QVBoxLayout()
        v1_layout.addWidget(QLabel("Mestra (Glove)"))
        self.vec_mestra = VectorScope("Mestra")
        v1_layout.addWidget(self.vec_mestra)
        
        # Escrava
        v2_layout = QVBoxLayout()
        v2_layout.addWidget(QLabel("Escrava (Aux)"))
        self.vec_slave = VectorScope("Slave")
        v2_layout.addWidget(self.vec_slave)

        v_layout.addLayout(v1_layout)
        v_layout.addLayout(v2_layout)
        right_layout.addWidget(vector_group)

        # 4. Câmera
        self.cam_widget = CameraWidget()
        right_layout.addWidget(self.cam_widget)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 2) # Coluna direita ocupa 2/3 da largura

        self.setLayout(main_layout)

    def change_emul(self, t):
        self.main_app.emulator.set_tipo_emulacao(
            Emulator.TIPO_CONTROLE if t == "Joystick" else Emulator.TIPO_TECLADO
        )

    def update_connection_status(self, connected, msg):
        self.lbl_status.setText(msg)
        self.btn_conn.setText("Desconectar" if connected else "Conectar")

    def toggle_cam(self):
        if self.cam_widget.cap: self.cam_widget.stop_cam()
        else: self.cam_widget.start_cam()

    def update_sensor_data(self, data):
        if not data: return

        # 1. Atualizar Terminal (Texto)
        # Formata bonito em linhas
        lines = []
        for k, v in sorted(data.items()):
            val_str = f"{v:.1f}" if isinstance(v, float) else f"{v}"
            lines.append(f"{k}: {val_str}")
        self.terminal.setText(" | ".join(lines))

        # 2. Atualizar Gráfico dos Dedos
        # Assume chaves: adc_1, adc_2, adc_3, adc_4
        # Se não houver dados, envia 0
        adcs = [
            data.get('adc_1', 0),
            data.get('adc_2', 0),
            data.get('adc_3', 0),
            data.get('adc_4', 0)
        ]
        self.adc_graph.update_values(adcs)

        # 3. Atualizar Vetores
        # Mestra
        self.vec_mestra.update_vector(
            data.get('ax', 0), data.get('ay', 0), data.get('az', 0)
        )
        # Slave (pode vir como slave_ax ou slave_gx dependendo do firmware)
        sax = data.get('slave_ax', data.get('slave_gx', 0))
        say = data.get('slave_ay', data.get('slave_gy', 0))
        saz = data.get('slave_az', data.get('slave_gz', 0))
        self.vec_slave.update_vector(sax, say, saz)


class CameraWidget(QWidget):
    camera_data_signal = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lbl = QLabel("Câmera Desligada")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setStyleSheet("background: #000; color: #555; border: 1px dashed #555;")
        self.lbl.setMinimumHeight(240)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.addWidget(self.lbl)
        self.cap = None
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_frame)

    def start_cam(self):
        self.cap = cv2.VideoCapture(0)
        self.timer.start(30)
    def stop_cam(self):
        self.timer.stop()
        if self.cap: self.cap.release(); self.cap = None
        self.lbl.setText("Câmera Desligada"); self.lbl.setPixmap(QPixmap())

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            # Lógica MediaPipe simplificada aqui para visualização
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, c = frame.shape
            qimg = QImage(rgb.data, w, h, c*w, QImage.Format_RGB888)
            self.lbl.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl.size(), Qt.KeepAspectRatio))
