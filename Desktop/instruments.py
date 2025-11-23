import math

class InputData:
    """ Interface base. """
    def process_data(self, data, mappings, emulator):
        pass

class Instrument(InputData):
    def __init__(self):
        self.lanes_vector = [0, 0, 0, 0]

class Drum(Instrument):
    def __init__(self):
        super().__init__()

    def process_data(self, camera_data, mappings, emulator):
        # Lógica futura da bateria
        pass

class Guitar(Instrument):
    def __init__(self):
        super().__init__()
        self.finger_actions = [
            "Dedo 1 (Indicador)", 
            "Dedo 2 (Médio)", 
            "Dedo 3 (Anelar)", 
            "Dedo 4 (Mindinho)"
        ]
        # Limiares de Histerese (0.0 a 1.0)
        # Trigger baixo (0.15) significa que basta dobrar 15% para ativar!
        self.TRIGGER_THRESHOLD = 0.15 
        self.RELEASE_THRESHOLD = 0.30 

    def process_data(self, logical_data, mappings, emulator):
        """
        Processa lógica de Dedos com Histerese para latência zero.
        """
        
        new_lanes = self.lanes_vector[:] # Copia o estado atual
        
        for i, action in enumerate(self.finger_actions):
            if action in mappings and action in logical_data:
                val = float(logical_data[action])
                calib = mappings[action]
                
                try:
                    # Usa apenas Rest e Full para definir o range total
                    rest = float(calib.get("rest", 0))
                    full = float(calib.get("full", 0))
                    
                    # Evita divisão por zero se calibração estiver ruim
                    total_range = full - rest
                    if abs(total_range) < 10: 
                        continue

                    # 1. Calcula % de flexão (0.0 a 1.0+)
                    # Funciona tanto para sensores diretos quanto inversos
                    progress = (val - rest) / total_range
                    
                    # 2. Máquina de Estados (Histerese)
                    is_active = (self.lanes_vector[i] == 1)
                    
                    if not is_active:
                        # Borda de Subida: Se passou de 15%, ATIVA
                        if progress > self.TRIGGER_THRESHOLD:
                            new_lanes[i] = 1
                    else:
                        # Borda de Descida: Só desativa se voltar para < 10%
                        # Isso permite manter a nota pressionada mesmo relaxando um pouco
                        if progress < self.RELEASE_THRESHOLD:
                            new_lanes[i] = 0
                        
                except (ValueError, TypeError):
                    pass

        # Atualiza emulador apenas se houver mudança
        if new_lanes != self.lanes_vector:
            self.lanes_vector = new_lanes
            emulator.atualizar_estado(self.lanes_vector)