import math

# Interface base conforme solicitado
class InputData:
    """ 
    Interface base. 
    Na nova arquitetura com Worker, ela não busca dados, 
    apenas define o contrato para os instrumentos processarem.
    """
    def process_data(self, data, mappings, emulator):
        pass

class Instrument(InputData):
    """ Classe base genérica para instrumentos com estado. """
    def __init__(self):
        self.lanes_vector = [0, 0, 0, 0]

class Drum(Instrument):
    def __init__(self):
        super().__init__()

    def process_data(self, camera_data, mappings, emulator):
        # Implementação futura da bateria via câmera
        # Poderia mapear hits para os botões do emulador se desejar
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
        # A lógica de Strum existe, mas não será enviada ao emulador atual
        self.strum_action = "Batida (Giroscópio)"

    def process_data(self, logical_data, mappings, emulator):
        """
        Processa lógica de Dedos (Lanes).
        Chamado automaticamente pelo Worker em alta frequência.
        """
        
        # --- 1. Lógica do Vetor de Lanes ---
        new_lanes = [0, 0, 0, 0]
        
        for i, action in enumerate(self.finger_actions):
            if action in mappings and action in logical_data:
                val = logical_data[action]
                calib = mappings[action]
                
                try:
                    half = float(calib.get("half", 0))
                    full = float(calib.get("full", 0))
                    
                    # Garante intervalo min/max (sensores flex podem inverter dependendo da montagem)
                    lim_inf = min(half, full)
                    lim_sup = max(half, full)
                    
                    # Ativa se estiver na zona de pressão (entre meio e completo)
                    if lim_inf <= val <= lim_sup:
                        new_lanes[i] = 1
                    # Se passou do máximo (apertou muito forte além da calibração), mantém ativo
                    elif abs(val - full) < abs(val - half):
                        new_lanes[i] = 1
                    else:
                        new_lanes[i] = 0
                        
                except (ValueError, TypeError):
                    new_lanes[i] = 0

        # Atualiza emulador apenas se houver mudança nos dedos
        # O emulador fornecido usa 'atualizar_estado' com vetor de 4 posições
        if new_lanes != self.lanes_vector:
            self.lanes_vector = new_lanes
            emulator.atualizar_estado(self.lanes_vector)

        # Nota: A lógica de Strum (Giroscópio) foi omitida aqui pois
        # o Emulator fornecido não possui o método 'realizar_palhetada'.