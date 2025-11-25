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

    def process_data(self, logical_data, camera_data, mappings, emulator):
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

        # --- Configuração de Sensibilidade ---
        # Trigger: Ativa ao passar de 10% de flexão
        self.TRIGGER_THRESHOLD = 0.10
        # Release: Só desativa se voltar para menos de 40% (Histerese)
        self.RELEASE_THRESHOLD = 0.40

        # --- Configuração do Filtro ---
        # Alpha 0.3: 30% valor novo, 70% histórico (Suave e rápido)
        # Diminua para mais suavidade (ex: 0.1), aumente para mais rapidez (ex: 0.8)
        self.FILTER_ALPHA = 0.3 
        self.smoothed_values = {} # Armazena o estado anterior de cada dedo

    def process_data(self, logical_data, mappings, emulator):
        """
        Processa lógica de Dedos com Histerese e Filtro Anti-Ruído.
        """
        new_lanes = self.lanes_vector[:] # Copia o estado atual

        for i, action in enumerate(self.finger_actions):
            if action in mappings and action in logical_data:
                raw_val = float(logical_data[action])
                calib = mappings[action]

                # ---  Filtro EMA (Exponential Moving Average) ---
                # Pega o valor anterior (ou usa o atual se for a primeira vez)
                prev_val = self.smoothed_values.get(action, raw_val)

                # Fórmula do filtro: suaviza picos repentinos
                val = (raw_val * self.FILTER_ALPHA) + (prev_val * (1.0 - self.FILTER_ALPHA))

                # Atualiza histórico
                self.smoothed_values[action] = val

                try:
                    rest = float(calib.get("rest", 0))
                    full = float(calib.get("full", 0))

                    total_range = full - rest

                    # --- Calcula % de flexão (Normalização) ---
                    progress = (val - rest) / total_range

                    # --- Máquina de Estados (Histerese) ---
                    is_active = (self.lanes_vector[i] == 1)

                    if not is_active:
                        # Gatilho (Ataque)
                        if progress > self.TRIGGER_THRESHOLD:
                            new_lanes[i] = 1
                    else:
                        # Liberação (Relaxamento)
                        if progress < self.RELEASE_THRESHOLD:
                            new_lanes[i] = 0

                except (ValueError, TypeError):
                    pass

        # Atualiza emulador apenas se houver mudança
        if new_lanes != self.lanes_vector:
            self.lanes_vector = new_lanes
            emulator.atualizar_estado(self.lanes_vector)