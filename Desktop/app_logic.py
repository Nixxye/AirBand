# app_logic.py
import sys
import random
import cv2
import mediapipe as mp
import math
import socket
import threading
import time
import json

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False

# ===================================================================
# 1. CLASSES DE LÓGICA (NÃO-UI)
# ===================================================================

class Communication:
    """ 
    Gerencia a conexão REAL com a luva (ESP32) via Wi-Fi (TCP Socket).
    (Sem mudanças)
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