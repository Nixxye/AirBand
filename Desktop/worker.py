from PyQt5.QtCore import QThread, QMutex
import time

class InstrumentWorker(QThread):
    def __init__(self, communication, guitar, drum, emulator):
        super().__init__()
        self.comm = communication
        self.guitar = guitar
        self.drum = drum
        self.emulator = emulator
        self.running = True
        self.sensor_mappings = {} 
        
        # --- NOVO: Estado e Dados da Câmera ---
        self.current_instrument = "Guitarra (Luva)" # Default
        self.camera_data = {"Drum_Vector": [0,0,0,0]} # Buffer seguro
        self.data_mutex = QMutex() # Para evitar leitura/escrita simultânea

    def update_mappings(self, new_mappings):
        self.sensor_mappings = new_mappings

    def set_instrument(self, instrument_name):
        """ Chamado pela UI quando o usuário troca o combobox. """
        self.current_instrument = instrument_name

    def update_camera_data(self, data):
        """ Chamado pela UI (CameraWidget) sempre que chega um frame novo. """
        self.data_mutex.lock()
        self.camera_data = data
        self.data_mutex.unlock()

    def stop(self):
        self.running = False
        self.comm.new_data_event.set()
        self.wait()

    def run(self):
        while self.running:
            has_data = self.comm.wait_for_data(timeout=0.1)
            
            # Mesmo sem dados da luva, a bateria precisa rodar (câmera)
            # Mas vamos manter sincronizado com a luva por enquanto para simplificar o loop
            if not has_data:
                continue

            raw_data = self.comm.get_latest_data()
            logical_data = {}
            
            # 1. Copia dados brutos (Accel + Gyro)
            essential_keys = [
                'gyro_ax', 'gyro_ay', 'gyro_az', 'gyro_gx', 'gyro_gy', 'gyro_gz',
                'slave_ax', 'slave_ay', 'slave_az', 'slave_gx', 'slave_gy', 'slave_gz'
            ]
            for k in essential_keys:
                if k in raw_data: logical_data[k] = raw_data[k]

            # 2. Copia Mapeamentos (Dedos)
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")
                if raw_key and raw_key in raw_data:
                    logical_data[raw_key] = raw_data[raw_key]

            # 3. Pega dados mais recentes da câmera (Thread-Safe)
            self.data_mutex.lock()
            current_camera_data = self.camera_data.copy()
            self.data_mutex.unlock()
            
            # Pega o vetor de bateria [0, 1, 0, 0]
            active_drums = current_camera_data.get("Drum_Vector", [0,0,0,0])

            # 4. Lógica Condicional (Seleção de Instrumento)
            if self.current_instrument == "Guitarra (Luva)":
                self.guitar.process_data(
                    logical_data, 
                    self.sensor_mappings, 
                    self.emulator
                )
            
            elif self.current_instrument == "Bateria (Camera)":
                # A bateria precisa tanto da câmera (active_drums) quanto da luva (logical_data para o bumbo/pedal)
                self.drum.process_data(
                    logical_data, 
                    active_drums, # Passa o vetor da câmera
                    self.sensor_mappings, 
                    self.emulator
                )