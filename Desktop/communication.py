import threading
import socket
import struct
import time


class Communication:
    """
    Gerencia a recepção de dados via UDP (Alta Performance).
    Decodifica structs binárias C++ diretamente.
    """

    # Porta deve ser a mesma definida no WifiServer.hpp
    UDP_PORT = 8888
    # Escuta em todos os IPs da máquina (0.0.0.0)
    LISTEN_IP = "0.0.0.0"

    # Formato da Struct (Deve bater EXATAMENTE com o C++)
    # < = Little Endian
    # h = int16 (2 bytes) | i = int32 (4 bytes) | f = float (4 bytes) | I = uint32 (4 bytes)
    # Estrutura: 6 shorts (acc/gyro) + 3 ints (mag) + 1 float (head) + 4 floats (adc) + 1 uint (time)
    STRUCT_FORMAT = "<hhhhhhiiifffffI"
    PACKET_SIZE = struct.calcsize(STRUCT_FORMAT)

    def __init__(self):
        self.connected = False
        self.sock = None
        self.receiver_thread = None
        self.data_lock = threading.Lock()
        self.network_status_message = "Parado"
        self.last_sensor_data = {}

    def toggle_connection(self):
        """Liga ou desliga a escuta UDP."""
        if self.connected:
            self.connected = False
            # Fecha o socket para forçar a thread a sair do bloqueio recvfrom
            if self.sock:
                self.sock.close()
            if self.receiver_thread:
                self.receiver_thread.join()
            self.network_status_message = "Parado"
        else:
            self.connected = True
            self.network_status_message = "Iniciando UDP..."
            self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receiver_thread.start()

    def _receive_loop(self):
        try:
            # Configura Socket UDP
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Permite reutilizar a porta caso reinicie o app rápido
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Abre a porta e espera dados
            self.sock.bind((self.LISTEN_IP, self.UDP_PORT))

            self.network_status_message = f"Ouvindo na porta {self.UDP_PORT}"
            print(f"UDP Server iniciado em {self.LISTEN_IP}:{self.UDP_PORT}")

            while self.connected:
                try:
                    # Recebe dados
                    data, addr = self.sock.recvfrom(1024)

                    if len(data) == self.PACKET_SIZE:
                        # Desempacota os bytes
                        values = struct.unpack(self.STRUCT_FORMAT, data)

                        # Reconstrói o dicionário para compatibilidade com sua UI
                        new_data = {
                            "gyro_ax": values[0], "gyro_ay": values[1], "gyro_az": values[2],
                            "gyro_gx": values[3], "gyro_gy": values[4], "gyro_gz": values[5],
                            "mag_mx":  values[6], "mag_my":  values[7], "mag_mz":  values[8],
                            "mag_heading": values[9],
                            "adc_v32": values[10], "adc_v33": values[11],
                            "adc_v34": values[12], "adc_v35": values[13],
                            "timestamp": values[14]
                        }

                        with self.data_lock:
                            self.last_sensor_data = new_data
                            # Atualiza status com IP da ESP
                            self.network_status_message = f"Recebendo de {addr[0]}"
                    else:
                        print(f"Pacote tamanho incorreto: {len(data)} vs {self.PACKET_SIZE}")

                except OSError:
                    break
                except Exception as e:
                    print(f"Erro no loop UDP: {e}")

        except Exception as e:
            self.network_status_message = f"Erro Bind: {e}"
            print(f"Falha ao iniciar servidor UDP: {e}")
        finally:
            if self.sock:
                self.sock.close()
            self.connected = False
            print("Thread UDP finalizada.")

    def get_latest_data(self):
        with self.data_lock:
            return self.last_sensor_data.copy()

    def get_live_sensor_value(self, sensor_key):
        with self.data_lock:
            return self.last_sensor_data.get(sensor_key, 0.0)

    def get_status_message(self):
        return self.network_status_message
