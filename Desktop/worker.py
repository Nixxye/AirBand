from PyQt5.QtCore import QThread
import time

class InstrumentWorker(QThread):
    """
    Thread dedicada ao processamento de alta frequência dos instrumentos.
    Isola a lógica matemática da Interface Gráfica (GUI).
    """
    def __init__(self, communication, guitar, drum, emulator):
        super().__init__()
        self.comm = communication
        self.guitar = guitar
        self.drum = drum
        self.emulator = emulator
        self.running = True
        self.sensor_mappings = {} 

    def update_mappings(self, new_mappings):
        self.sensor_mappings = new_mappings

    def stop(self):
        self.running = False
        self.comm.new_data_event.set()
        self.wait()

    def run(self):
        """ Loop principal de processamento (Event-Driven). """
        while self.running:
            # Espera até chegar um pacote novo (bloqueante com timeout para não travar ao fechar)
            has_data = self.comm.wait_for_data(timeout=0.1)
            
            if not has_data:
                continue

            raw_data = self.comm.get_latest_data()
            logical_data = {}
            
            # --- 1. PASSO CRÍTICO: Copiar Vetores Brutos ---
            # A lógica vetorial precisa acessar tanto Accel (Direção) quanto Gyro (Gatilho)
            
            essential_keys = [
                # --- Mestra ---
                'gyro_ax', 'gyro_ay', 'gyro_az',  # Acelerômetro
                'gyro_gx', 'gyro_gy', 'gyro_gz',  # Giroscópio <--- ADICIONADO
                
                # --- Escrava ---
                'slave_ax', 'slave_ay', 'slave_az', # Acelerômetro
                'slave_gx', 'slave_gy', 'slave_gz'  # Giroscópio <--- ADICIONADO
            ]
            
            for k in essential_keys:
                if k in raw_data:
                    logical_data[k] = raw_data[k]

            # --- 2. Copiar Mapeamentos Lógicos (ADC / Dedos) ---
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")       # Ex: "adc_v32"

                if raw_key and raw_key in raw_data:
                    logical_data[action] = raw_data[raw_key]

            # --- 3. Processamento ---
            if logical_data:
                # Aqui você escolhe qual lógica rodar (Guitarra ou Bateria)
                # Como estamos focando na batida (strum), usaremos a Drum.process_data
                # que contém a lógica nova de Giroscópio + Acelerômetro
                
                self.drum.process_data(
                    logical_data, 
                    None,
                    self.sensor_mappings, 
                    self.emulator
                )
                
                # Se precisar processar os dedos da guitarra também:
                # self.guitar.process_data(...)