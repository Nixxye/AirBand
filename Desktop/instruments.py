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
        Processa batidas (Strum) usando Vetor Diferença e Plano Normal da Gravidade.
        Não exige calibração de 'Up'/'Down', apenas 'Rest'.
        """
        import math
        import time

        # --- CONSTANTES ---
        # Limiar de variação de aceleração para considerar um movimento.
        # Ajuste este valor! Se os dados forem raw (0-16000), tente 4000. 
        # Se forem normalizados (0-1.0), tente 0.3.
        # Como no código anterior usávamos raw > 100 como filtro de ruído, 
        # vou assumir um valor conservador aqui.
        DELTA_THRESHOLD = 3000.0 
        
        # Tempo entre batidas (Cooldown)
        STRUM_COOLDOWN = 0.15 

        current_time = time.time()
        
        # Ações para verificar
        strum_actions = ["Batida (Mestra)", "Batida (Escrava)"]

        for action_name in strum_actions:
            if action_name not in mappings: continue

            calib = mappings[action_name]
            
            # 1. Obter Vetor de Repouso (Gravidade Calibrada)
            # Este vetor atua como o vetor Normal do plano que divide Cima/Baixo
            rest_data = calib.get("rest", {})
            
            # Tenta pegar calibração de accel (prioridade) ou gyro
            rx = rest_data.get("ax", rest_data.get("gx", 0))
            ry = rest_data.get("ay", rest_data.get("gy", 0))
            rz = rest_data.get("az", rest_data.get("gz", 0))
            
            # Se a calibração for inválida (0,0,0), pula
            if rx == 0 and ry == 0 and rz == 0: continue

            # 2. Obter Vetor Atual (Live)
            cx, cy, cz = 0, 0, 0
            
            if "Mestra" in action_name:
                if all(k in logical_data for k in ['gyro_ax', 'gyro_ay', 'gyro_az']):
                    cx, cy, cz = logical_data['gyro_ax'], logical_data['gyro_ay'], logical_data['gyro_az']
                else: continue
            
            elif "Escrava" in action_name:
                # Prioriza acelerômetro (ax), fallback para giroscópio (gx) se necessário
                if all(k in logical_data for k in ['slave_ax', 'slave_ay', 'slave_az']):
                    cx, cy, cz = logical_data['slave_ax'], logical_data['slave_ay'], logical_data['slave_az']
                elif all(k in logical_data for k in ['slave_gx', 'slave_gy', 'slave_gz']):
                     cx, cy, cz = logical_data['slave_gx'], logical_data['slave_gy'], logical_data['slave_gz']
                else: continue

            # 3. Calcular Vetor Diferença (Delta)
            # Delta = Atual - Repouso
            # Isso remove a gravidade estática e deixa apenas a aceleração do movimento da mão
            dx = cx - rx
            dy = cy - ry
            dz = cz - rz
            
            # 4. Verificar Magnitude do Delta (Força do movimento)
            delta_mag = math.sqrt(dx**2 + dy**2 + dz**2)
            
            if delta_mag < DELTA_THRESHOLD:
                continue # Movimento muito fraco, ignora

            # 5. Determinar Direção (Produto Escalar)
            # Projetamos o Delta no vetor de Repouso (Gravidade)
            # Dot Product: (Delta . Rest)
            dot_product = (dx * rx) + (dy * ry) + (dz * rz)

            # Debounce (Cooldown)
            cooldown_key = f"{action_name}_strum"
            last_time = self.last_strum_time.get(cooldown_key, 0)

            if (current_time - last_time) > STRUM_COOLDOWN:
                # Se o produto escalar for positivo: O movimento tem componente na direção da gravidade (BAIXO) 


                # Se negativo: O movimento é contra a gravidade (CIMA)
                
                direction = "DOWN" if dot_product > 0 else "UP"
                
                print(f"🎸 {action_name} -> {direction} (Força: {delta_mag:.0f})")

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