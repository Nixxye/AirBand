from PyQt5.QtCore import QThread
import time

class InstrumentWorker(QThread):
    """
    Thread dedicada ao processamento de alta frequência dos instrumentos.
    Isola a lógica da GUI para garantir latência mínima.
    """
    def __init__(self, communication, guitar, drum, emulator):
        super().__init__()
        self.comm = communication
        self.guitar = guitar
        self.drum = drum
        self.emulator = emulator
        self.running = True
        self.sensor_mappings = {} # Cópia local dos mapeamentos

    def update_mappings(self, new_mappings):
        """ Atualiza os mapeamentos de forma segura. """
        self.sensor_mappings = new_mappings

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        """ Loop principal de processamento (Alta Frequência). """
        while self.running:
            # 1. Obter dados brutos (Thread-safe)
            raw_data = self.comm.get_latest_data()
            
            if not raw_data:
                time.sleep(0.005) # 5ms sleep se não houver dados para evitar 100% CPU
                continue

            # 2. Pré-processar dados lógicos para a Guitarra
            # Isso evita refazer logica complexa dentro da classe Guitar se não precisar
            logical_data = {}
            
            # Mapeia apenas o necessário baseado na calibração atual
            for action, mapping in self.sensor_mappings.items():
                raw_key = mapping.get("key")
                key_prefix = mapping.get("key_prefix")

                if raw_key in raw_data:
                    logical_data[action] = raw_data[raw_key]
                
                elif key_prefix:
                    # Constrói vetor se as chaves existirem
                    ax = raw_data.get(f"{key_prefix}ax")
                    if ax is not None:
                        logical_data[action] = {
                            "ax": ax,
                            "ay": raw_data.get(f"{key_prefix}ay", 0),
                            "az": raw_data.get(f"{key_prefix}az", 0)
                        }

            # 3. Processar Instrumentos
            # A Guitarra decide se chama o emulador
            if logical_data:
                self.guitar.process_data(
                    logical_data, 
                    self.sensor_mappings, 
                    self.emulator
                )

            # 4. Controle de Frequência
            # Um sleep minúsculo cede tempo para outras threads sem criar latência perceptível
            # 0.001s = 1ms (Teórico 1000Hz)
            time.sleep(0.001)
