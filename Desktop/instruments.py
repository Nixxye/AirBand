import math
import time

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
        print("🥁 Processando dados da bateria...")

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
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", 
            "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)"
        ]
        
        # --- Configuração de Debug ---
        self.use_strumming = False
        
        # --- Configuração de Sensibilidade ---
        self.TRIGGER_THRESHOLD = 0.50
        self.FILTER_ALPHA = 0.4
        # --- AJUSTE DA MÁSCARA (CROSSTALK) ---
        # 1.0 = Matemático exato (Padrão)
        # 0.8 = Mais permissivo (Melhor para Acordes, risco de fantasmas)
        # 1.2 = Mais agressivo (Isola bem o dedo, risco de matar acordes)
        self.CROSSTALK_GAIN = 1.0
        
        # --- Configuração de Batida (Strum) ---
        self.STRUM_COOLDOWN = 0.10
        self.last_strum_time = 0
        
        # --- Estado Interno ---
        self.smoothed_values = {}
        self.fingers_armed = [0, 0, 0, 0]
        self.lanes_vector = [0, 0, 0, 0]

    def set_strumming_mode(self, enabled: bool):
        """Método auxiliar para mudar o modo em tempo real via UI"""
        self.use_strumming = enabled

    def process_data(self, logical_data, mappings, emulator):
        # Variável para acumular texto de debug deste frame
        debug_lines = []
        has_activity = False

        # =====================================================================
        # PASSO 1: CÁLCULO DA ATIVAÇÃO BRUTA (RAW)
        # =====================================================================
        raw_activations = {}
        for action in self.finger_actions:
            if action in mappings:
                calib = mappings[action]
                sensor_key = calib.get("key")
                if sensor_key and sensor_key in logical_data:
                    raw_val = float(logical_data[sensor_key])
                    
                    # Filtro
                    prev_val = self.smoothed_values.get(action, raw_val)
                    val = (raw_val * self.FILTER_ALPHA) + (prev_val * (1.0 - self.FILTER_ALPHA))
                    self.smoothed_values[action] = val
                    
                    # Normalização
                    try:
                        rest = float(calib.get("rest", 0))
                        full = float(calib.get("full", 1))
                        total_range = full - rest
                        
                        if abs(total_range) > 0.1:
                            norm = (val - rest) / total_range
                            norm = max(0.0, min(1.0, norm))
                            raw_activations[action] = norm
                            # DEBUG RAW: Mostra se o input está chegando
                            if norm > 0.05:
                                has_activity = True
                                debug_lines.append(f"[RAW] {action[-10:]}: {norm:.2f} (Val:{val:.0f}/R:{rest:.0f}/F:{full:.0f})")
                        else:
                            raw_activations[action] = 0.0
                    except (ValueError, TypeError):
                        raw_activations[action] = 0.0
                else:
                    raw_activations[action] = 0.0

        # =====================================================================
        # PASSO 2: MATRIZ DE DESACOPLAMENTO (CROSSTALK)
        # =====================================================================
        final_activations = {}
        
        for target_action in self.finger_actions:
            if target_action not in raw_activations:
                final_activations[target_action] = 0.0
                continue
            
            my_raw_activation = raw_activations[target_action]
            target_calib = mappings.get(target_action, {})
            target_sensor_key = target_calib.get("key")
            target_rest = float(target_calib.get("rest", 0))
            target_full = float(target_calib.get("full", 1))
            target_range = target_full - target_rest

            total_interference = 0.0
            debug_interference_details = []

            for other_action in self.finger_actions:
                if other_action == target_action: continue
                
                other_raw_activation = raw_activations.get(other_action, 0.0)
                
                # Só calcula interferência se o outro dedo estiver ativo
                if other_raw_activation > 0.05 and target_sensor_key:
                    other_calib = mappings.get(other_action, {})
                    crosstalk_ref = other_calib.get("crosstalk_ref", {})
                    
                    val_on_my_sensor_caused_by_other = crosstalk_ref.get(target_sensor_key)
                    
                    if val_on_my_sensor_caused_by_other is not None and abs(target_range) > 10:
                        # Fator de Acoplamento
                        coupling_factor = (val_on_my_sensor_caused_by_other - target_rest) / target_range
                        current_interference = (other_raw_activation * coupling_factor) * self.CROSSTALK_GAIN
                        
                        if current_interference > 0:
                            total_interference += current_interference
                            debug_interference_details.append(f"{other_action[-8:]}({coupling_factor:.2f})")

            clean_activation = my_raw_activation - total_interference
            final_activations[target_action] = max(0.0, clean_activation)

            # DEBUG CROSSTALK: Mostra se a interferência matou o sinal
            if my_raw_activation > 0.05:
                status = "VIVO" if clean_activation > self.TRIGGER_THRESHOLD else "MORTO"
                debug_lines.append(
                    f"  -> {target_action[-10:]}: Raw={my_raw_activation:.2f} - Interf={total_interference:.2f} = Final={clean_activation:.2f} [{status}]"
                )
                if debug_interference_details:
                    debug_lines.append(f"     (Culpa de: {', '.join(debug_interference_details)})")

        # Atualiza vetor de dedos armados
        current_fingers_armed = [0, 0, 0, 0]
        for i, action in enumerate(self.finger_actions):
            if final_activations.get(action, 0) > self.TRIGGER_THRESHOLD:
                current_fingers_armed[i] = 1

        self.fingers_armed = current_fingers_armed

        # =====================================================================
        # PASSO 3: LÓGICA DE JOGO E ENVIO
        # =====================================================================
        
        if not self.use_strumming:
            self.lanes_vector = self.fingers_armed[:]
        else:
            # (Mantive sua lógica de strumming resumida aqui para focar no debug dos dedos)
            is_strumming = False 
            # ... (Lógica de strumming original) ...
            if is_strumming: self.lanes_vector = self.fingers_armed[:]
            for i in range(4):
                if self.fingers_armed[i] == 0: self.lanes_vector[i] = 0

        emulator.atualizar_estado(self.lanes_vector)

        # PRINT FINAL (Apenas se houver atividade para não poluir)
        # if has_activity:
        #     print("\n".join(debug_lines))
        #     print(f"OUT: {self.lanes_vector} | Mode: {'Strum' if self.use_strumming else 'Tap'}")
        #     print("-" * 40)
