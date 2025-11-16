import threading
import socket
import time
import json


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
