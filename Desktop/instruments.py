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
        Lógica de Batida baseada puramente em Eixo de Rotação (Giroscópio).
        Ignora acelerômetro.
        """
        import time
        current_time = time.time()
        
        # Tempo entre batidas
        STRUM_COOLDOWN = 0.12 

        strum_actions = ["Batida (Mestra)", "Batida (Escrava)"]

        for action_name in strum_actions:
            if action_name not in mappings: continue
            
            calib = mappings[action_name]
            
            # Se a calibração não tiver o campo 'axis', é do tipo antigo (ignora ou recalibra)
            target_axis = calib.get("axis") 
            if not target_axis: continue

            prefix = calib.get("key_prefix", "gyro_") # gyro_ ou slave_
            full_key_name = f"{prefix}{target_axis}"  # Ex: "gyro_gz" ou "slave_gx"
            
            # 1. Pega o valor AO VIVO apenas do eixo dominante
            # No InstrumentWorker, certifique-se de passar esses dados em logical_data!
            if full_key_name not in logical_data:
                continue
                
            current_val = logical_data[full_key_name]
            
            # 2. Verifica Limiar (Threshold)
            threshold = calib.get("threshold", 4000)
            
            if abs(current_val) > threshold:
                
                # 3. Verifica Debounce
                cooldown_key = f"{action_name}_strum"
                last_time = self.last_strum_time.get(cooldown_key, 0)

                if (current_time - last_time) > STRUM_COOLDOWN:
                    
                    # 4. Determina Direção pelo Sinal
                    # Se o sinal atual for igual ao sinal gravado para "Down" -> É Baixo
                    # Caso contrário -> É Cima
                    calib_sign = calib.get("down_sign", 1)
                    
                    # Lógica de sinal:
                    # Se (val > 0 e sign > 0) ou (val < 0 e sign < 0) -> Sinais iguais
                    is_down = (current_val * calib_sign) > 0
                    
                    direction = "DOWN" if is_down else "UP"
                    
                    print(f"🎸 {action_name} -> {direction} (Eixo: {target_axis}, Val: {current_val})")

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