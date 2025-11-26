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
        Processa APENAS batidas para BAIXO (Down strum).
        """
        import math
        import time

        # --- CONSTANTES ---
        ANGLE_THRESHOLD = 30.0      # Ângulo máximo (Cone de detecção)
        MAGNITUDE_THRESHOLD = 0.8   # 50% da força calibrada mínima

        current_time = time.time()
        strum_actions = ["Batida (Mestra)", "Batida (Escrava)"]
        for action_name in strum_actions:
            # print(action_name)
            if action_name not in mappings: 
                # print(list(mappings.keys()))
                continue
            # print("AAA")
            calib = mappings[action_name]

            # 1. Extrai Vetor Atual
            curr_vec = None
            if "Mestra" in action_name:
                if all(k in logical_data for k in ['gyro_ax', 'gyro_ay', 'gyro_az']):
                    curr_vec = (logical_data['gyro_ax'], logical_data['gyro_ay'], logical_data['gyro_az'])
            elif "Escrava" in action_name:
                # print("Escrava no action name")
                # print(logical_data)
                if all(k in logical_data for k in ['slave_ax', 'slave_ay', 'slave_az']):
                    curr_vec = (logical_data['slave_ax'], logical_data['slave_ay'], logical_data['slave_az'])

            if curr_vec is None: continue

            # 2. Magnitude Atual
            curr_mag = math.sqrt(curr_vec[0]**2 + curr_vec[1]**2 + curr_vec[2]**2)
            # print(f'Magnitude: {curr_mag}')
            if curr_mag < 100: continue # Ignora ruído

            # 3. Verifica APENAS "down"
            target_data = calib.get("down", {})
            
            cal_vec = (target_data.get("ax", 0), target_data.get("ay", 0), target_data.get("az", 0))
            cal_mag = math.sqrt(cal_vec[0]**2 + cal_vec[1]**2 + cal_vec[2]**2)
            
            if cal_mag == 0: continue
            # A. Checa Intensidade
            if curr_mag < (cal_mag * MAGNITUDE_THRESHOLD):
                continue

            # B. Checa Ângulo
            dot_product = (curr_vec[0]*cal_vec[0]) + (curr_vec[1]*cal_vec[1]) + (curr_vec[2]*cal_vec[2])
            denominator = curr_mag * cal_mag
            
            if denominator == 0: continue
            
            cos_theta = max(-1.0, min(1.0, dot_product / denominator))
            angle = math.degrees(math.acos(cos_theta))

            # C. Dispara se estiver dentro do ângulo
            # print(f'Ângulo: {angle}')
            
            if angle <= ANGLE_THRESHOLD:
                
                # Debounce (Cooldown)
                cooldown_key = f"{action_name}_strum"
                last_time = self.last_strum_time.get(cooldown_key, 0)

                if (current_time - last_time) > self.STRUM_COOLDOWN:
                    print(f"🎸 {action_name} -> DOWN (Ângulo: {angle:.1f}°)")
                    
                    emulator.atualizar_estado([1,1,1,1])
                    print(f'Ângulo: {angle}')
                    print(f'Magnitude: {curr_mag}')
                    print(curr_vec)
                    
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