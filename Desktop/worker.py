from PyQt5.QtCore import QThread
import time

class InstrumentWorker(QThread):
    """
    Thread dedicada ao processamento de alta frequência dos instrumentos.
    Isola a lógica matemática da Interface Gráfica (GUI) para garantir 
    latência mínima e evitar travamentos visuais.
    """
    def __init__(self, communication, guitar, drum, emulator):
        super().__init__()
        self.comm = communication
        self.guitar = guitar
        self.drum = drum
        self.emulator = emulator
        self.running = True
        self.sensor_mappings = {} # Cópia local dos mapeamentos para acesso rápido

    def update_mappings(self, new_mappings):
        """ Atualiza os mapeamentos de forma segura (Thread-safe). """
        self.sensor_mappings = new_mappings

    def stop(self):
        """ Para o loop e acorda a thread se estiver dormindo. """
        self.running = False
        # Dispara o evento para desbloquear o wait_for_data imediatamente
        self.comm.new_data_event.set()
        self.wait()

    def run(self):
        """ Loop principal de processamento (Event-Driven). """
        while self.running:
            has_data = self.comm.wait_for_data(timeout=0.1)
            
            if not has_data:
                continue

            raw_data = self.comm.get_latest_data()
            logical_data = {}
            
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")       # Ex: "adc_v32" (Dedos)
                key_prefix = mapping.get("key_prefix") # Ex: "gyro_" ou "slave_" (Batida)

                if raw_key in raw_data:
                    logical_data[action] = raw_data[raw_key]
                
                elif key_prefix:
                    # Tenta pegar Acelerômetro (Padrão da Mestra: 'gyro_ax')
                    ax = raw_data.get(f"{key_prefix}ax")
                    ay = raw_data.get(f"{key_prefix}ay", 0)
                    az = raw_data.get(f"{key_prefix}az", 0)

                    if ax is None:
                        ax = raw_data.get(f"{key_prefix}gx")
                        ay = raw_data.get(f"{key_prefix}gy", 0)
                        az = raw_data.get(f"{key_prefix}gz", 0)

                    if ax is not None:
                        logical_data[action] = { "ax": ax, "ay": ay, "az": az }

            if logical_data:
                self.guitar.process_data(
                    logical_data, 
                    self.sensor_mappings, 
                    self.emulator
                )