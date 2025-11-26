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
        Lógica Híbrida (Sensor Fusion):
        1. GATILHO: Usa a Aceleração Angular (Giroscópio) para detectar a força da batida.
        2. DIREÇÃO: Usa a Aceleração Linear (Acelerômetro) vs Gravidade para saber se foi Cima/Baixo.
        """
        import math
        import time

        # --- CONSTANTES ---
        
        # Limiar do GIROSCÓPIO para detectar que houve uma batida.
        # Valores raw do MPU6050 vão até 32768. Uma batida rápida é > 5000.
        GYRO_TRIGGER_THRESHOLD = 8000.0 
        
        # Tempo entre batidas
        STRUM_COOLDOWN = 0.15 

        current_time = time.time()
        
        strum_actions = ["Batida (Mestra)", "Batida (Escrava)"]

        for action_name in strum_actions:
            if action_name not in mappings: continue

            calib = mappings[action_name]
            
            # --- PASSO 1: DETECTAR O GATILHO (USANDO GIROSCÓPIO) ---
            gx, gy, gz = 0, 0, 0
            
            # Extrai dados do Giroscópio
            if "Mestra" in action_name:
                if all(k in logical_data for k in ['gyro_gx', 'gyro_gy', 'gyro_gz']):
                    gx, gy, gz = logical_data['gyro_gx'], logical_data['gyro_gy'], logical_data['gyro_gz']
                else: continue
            elif "Escrava" in action_name:
                if all(k in logical_data for k in ['slave_gx', 'slave_gy', 'slave_gz']):
                    gx, gy, gz = logical_data['slave_gx'], logical_data['slave_gy'], logical_data['slave_gz']
                else: continue

            # Calcula Magnitude da Rotação (Velocidade Angular Total)
            gyro_mag = math.sqrt(gx**2 + gy**2 + gz**2)

            # Se a rotação for fraca, ignora tudo. Não houve batida.
            if gyro_mag < GYRO_TRIGGER_THRESHOLD:
                continue

            # --- PASSO 2: DETERMINAR A DIREÇÃO (USANDO ACELERÔMETRO) ---
            # Se chegamos aqui, sabemos que houve uma batida forte. Agora: Cima ou Baixo?
            
            # Pega vetor de Repouso (Gravidade Calibrada)
            rest_data = calib.get("rest", {})
            rx = rest_data.get("ax", rest_data.get("gx", 0))
            ry = rest_data.get("ay", rest_data.get("gy", 0))
            rz = rest_data.get("az", rest_data.get("gz", 0))
            
            if rx == 0 and ry == 0 and rz == 0: continue

            # Pega vetor Acelerômetro Atual
            cx, cy, cz = 0, 0, 0
            if "Mestra" in action_name:
                cx, cy, cz = logical_data.get('gyro_ax', 0), logical_data.get('gyro_ay', 0), logical_data.get('gyro_az', 0)
            elif "Escrava" in action_name:
                cx, cy, cz = logical_data.get('slave_ax', 0), logical_data.get('slave_ay', 0), logical_data.get('slave_az', 0)

            # Calcula Delta (Movimento real da mão, removendo a gravidade estática)
            dx = cx - rx
            dy = cy - ry
            dz = cz - rz

            # Produto Escalar com a Gravidade (Rest)
            # Se > 0: Movimento a favor da gravidade (BAIXO)
            # Se < 0: Movimento contra a gravidade (CIMA)
            dot_product = (dx * rx) + (dy * ry) + (dz * rz)

            # --- PASSO 3: DISPARO COM DEBOUNCE ---
            cooldown_key = f"{action_name}_strum"
            last_time = self.last_strum_time.get(cooldown_key, 0)

            if (current_time - last_time) > STRUM_COOLDOWN:
                
                direction = "DOWN" if dot_product > 0 else "UP"
                
                print(f"🎸 {action_name} -> {direction} (Giro: {gyro_mag:.0f})")

                if direction == "DOWN":
                    emulator.strum_down()
                else:
                    emulator.strum_up()
                
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