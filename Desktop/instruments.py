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
        self.last_strum_time = {} 
        self.STRUM_COOLDOWN = 0.2
        super().__init__()

    def process_data(self, logical_data, camera_data, mappings, emulator):
        """
        Processamento Vetorial de Giroscópio (3 Eixos).
        Usa Projeção Escalar para detectar similaridade de direção e intensidade.
        """
        import math
        import time
        current_time = time.time()

        STRUM_COOLDOWN = 0.12 

        strum_actions = ["Batida (Mestra)", "Batida (Escrava)"]

        for action_name in strum_actions:
            if action_name not in mappings: continue
            
            calib = mappings[action_name]
            
            # Recupera o vetor calibrado (Down)
            cal_vec = calib.get("vector") # {gx, gy, gz}
            if not cal_vec: continue

            prefix = calib.get("key_prefix", "gyro_")
            
            # 1. Monta o Vetor Calibrado (Referência)
            rx = cal_vec.get("gx", 0)
            ry = cal_vec.get("gy", 0)
            rz = cal_vec.get("gz", 0)
            
            # Magnitude do vetor de referência
            ref_mag = math.sqrt(rx**2 + ry**2 + rz**2)
            if ref_mag == 0: continue

            # 2. Monta o Vetor Atual (Live)
            # Verifica se os dados existem no pacote
            if f"{prefix}gx" not in logical_data: continue
            
            cx = logical_data[f"{prefix}gx"]
            cy = logical_data[f"{prefix}gy"]
            cz = logical_data[f"{prefix}gz"]

            # 3. CÁLCULO DA PROJEÇÃO (Dot Product)
            # Projetamos o vetor Atual sobre o vetor de Referência Normalizado.
            # Isso nos diz "Quanto de força existe na direção da batida calibrada?"
            
            # Dot Product (A . B)
            dot_product = (cx * rx) + (cy * ry) + (cz * rz)
            
            # Projeção Escalar = (A . B) / |B|
            # Isso retorna um valor na mesma escala dos dados brutos (ex: 5000, 10000)
            projection_value = dot_product / ref_mag
            
            # 4. Verifica Limiar
            threshold = 26000
            
            # Se projeção for muito positiva -> Movimento igual ao calibrado (DOWN)
            # Se projeção for muito negativa -> Movimento oposto ao calibrado (UP)
            
            if abs(projection_value) > threshold:
                
                cooldown_key = f"{action_name}_strum"
                last_time = self.last_strum_time.get(cooldown_key, 0)

                if (current_time - last_time) > STRUM_COOLDOWN:
                    
                    direction = "DOWN" if projection_value > 0 else "UP"
                    
                    print(f"🎸 {action_name} -> {direction} (Força Projetada: {abs(projection_value):.0f})")

                    # if direction == "DOWN":
                    #     emulator.strum_down()
                    # else:
                    #     emulator.strum_up()
                    
                    self.last_strum_time[cooldown_key] = current_time
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