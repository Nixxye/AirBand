import socket
import struct
import threading

class Communication:
    UDP_PORT = 8888
    LISTEN_IP = "0.0.0.0"
    
    # Struct Atualizada: 
    # Mestra: 6 shorts (acc/gyr) + 3 ints (mag) + 1 float (head) + 4 floats (adc)
    # Escrava: 3 shorts (slave_gyro)
    # Footer: 1 uint (time)
    STRUCT_FORMAT = "<hhhhhhiiifffffhhhI" 
    PACKET_SIZE = struct.calcsize(STRUCT_FORMAT)

    def __init__(self):
        self.connected = False
        self.sock = None
        self.receiver_thread = None
        self.data_lock = threading.Lock()
        self.new_data_event = threading.Event()
        self.network_status_message = "Parado"
        self.last_sensor_data = {}

    def toggle_connection(self):
        if self.connected:
            self.connected = False
            if self.sock: 
                try:
                    self.sock.close()
                except: 
                    pass
            self.new_data_event.set()
            if self.receiver_thread: 
                self.receiver_thread.join(timeout=1.0)
            self.network_status_message = "Parado"
        else:
            self.connected = True
            self.new_data_event.clear()
            self.network_status_message = "Ouvindo UDP..."
            self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receiver_thread.start()

    def _receive_loop(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.LISTEN_IP, self.UDP_PORT))
            self.network_status_message = f"Conectado: {self.UDP_PORT}"
            
            while self.connected:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    
                    if len(data) == self.PACKET_SIZE:
                        values = struct.unpack(self.STRUCT_FORMAT, data)
                        
                        new_data = {
                            # --- MESTRA ---
                            "gyro_ax": values[0], "gyro_ay": values[1], "gyro_az": values[2],
                            "gyro_gx": values[3], "gyro_gy": values[4], "gyro_gz": values[5],
                            "mag_mx": values[6], "mag_my": values[7], "mag_mz": values[8],
                            "mag_heading": values[9],
                            "adc_v32": values[10], "adc_v33": values[11],
                            "adc_v34": values[12], "adc_v35": values[13],
                            
                            # --- ESCRAVA (Novo) ---
                            "slave_gx": values[14], 
                            "slave_gy": values[15], 
                            "slave_gz": values[16],
                            
                            "timestamp": values[17]
                        }
                        
                        with self.data_lock:
                            self.last_sensor_data = new_data
                        
                        self.new_data_event.set()
                        
                except OSError:
                    break
        except Exception as e:
            self.network_status_message = f"Erro: {e}"
        finally:
            if self.sock: 
                try: self.sock.close()
                except: pass
            self.connected = False
            self.new_data_event.set()

    def wait_for_data(self, timeout=0.1):
        flag = self.new_data_event.wait(timeout)
        if flag:
            self.new_data_event.clear()
        return flag

    def get_latest_data(self):
        with self.data_lock:
            return self.last_sensor_data.copy()

    def get_status_message(self):
        return self.network_status_message