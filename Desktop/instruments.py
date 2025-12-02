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
        Processamento exclusivo da CÂMERA para Bateria.
        Ignora o giroscópio.
        """
        print("🥁 Processando dados da bateria (CÂMERA)...")
        
        # ✅ NOVO: Enviar o vetor da câmera diretamente para o emulador
        if camera_data:
            # camera_data é o Drum_Vector [0, 1, 0, 0] da câmera
            print(f"🥁 [DRUM] Recebeu camera_data: {camera_data}")
            print(f"🥁 [DRUM] Enviando para emulador: {camera_data}")
            emulator.atualizar_estado(camera_data)
        else:
            print(f"🥁 [DRUM] camera_data é None ou vazio!")
            emulator.atualizar_estado([0, 0, 0, 0])  # Desativa tudo se não houver câmera
class Guitar(Instrument):
    def __init__(self):
        super().__init__()
        self.finger_actions = [
            "Dedo 1 (Indicador)", "Dedo 2 (Médio)", 
            "Dedo 3 (Anelar)", "Dedo 4 (Mindinho)"
        ]
        
        # --- Configuração de Sensibilidade Dedos ---
        self.TRIGGER_THRESHOLD = 0.50 # Flexão necessária para considerar dedo "armado"
        self.FILTER_ALPHA = 0.3
        self.smoothed_values = {}
        
        # --- Configuração de Batida (Strum) ---
        self.last_strum_time = 0
        self.STRUM_COOLDOWN = 0.12
        
        # Estado Lógico dos Dedos (Armados)
        # 1 = Dedo dobrado, pronto para tocar. 0 = Dedo esticado.
        self.fingers_armed = [0, 0, 0, 0]

    def process_data(self, logical_data, mappings, emulator):
        """
        Lógica Guitar Hero:
        1. Atualiza estado dos dedos ("Armado" ou "Solto") o tempo todo.
        2. Detecta batida (Strum) na mão escrava.
        3. SE bater: Envia o estado atual dos dedos para o emulador.
        4. SE soltar o dedo depois: Desliga a tecla correspondente.
        """
        import time
        import math
        
        # =====================================================================
        # PASSO 1: ATUALIZAR ESTADO DOS DEDOS (ARMADO/DESARMADO)
        # =====================================================================
        current_fingers_state = [0, 0, 0, 0]
        
        for i, action in enumerate(self.finger_actions):
            if action in mappings and action in logical_data:
                raw_val = float(logical_data[action])
                calib = mappings[action]

                # Filtro EMA
                prev_val = self.smoothed_values.get(action, raw_val)
                val = (raw_val * self.FILTER_ALPHA) + (prev_val * (1.0 - self.FILTER_ALPHA))
                self.smoothed_values[action] = val

                try:
                    rest = float(calib.get("rest", 0))
                    full = float(calib.get("full", 0))
                    total_range = full - rest
                    
                    if total_range == 0: continue

                    # Normaliza (0.0 a 1.0)
                    progress = (val - rest) / total_range
                    
                    # Verifica se o dedo está "armado" (pressionado)
                    if progress > self.TRIGGER_THRESHOLD:
                        current_fingers_state[i] = 1
                    else:
                        current_fingers_state[i] = 0
                        
                except (ValueError, TypeError):
                    pass
        
        # Atualiza vetor interno de dedos
        self.fingers_armed = current_fingers_state

        # =====================================================================
        # PASSO 2: DETECTAR BATIDA (STRUM) - APENAS ESCRAVA
        # =====================================================================
        is_strumming = False
        strum_direction = None
        
        # Verifica APENAS a "Batida (Escrava)" para a palhetada
        action_name = "Batida (Escrava)"
        
        if action_name in mappings:
            calib = mappings[action_name]
            cal_vec = calib.get("vector")
            
            if cal_vec:
                prefix = calib.get("key_prefix", "slave_")
                
                # Dados Live
                cx = logical_data.get(f"{prefix}gx", 0)
                cy = logical_data.get(f"{prefix}gy", 0)
                cz = logical_data.get(f"{prefix}gz", 0)
                
                # Dados Calibração
                rx = cal_vec.get("gx", 0)
                ry = cal_vec.get("gy", 0)
                rz = cal_vec.get("gz", 0)
                ref_mag = math.sqrt(rx**2 + ry**2 + rz**2)

                if ref_mag > 0:
                    dot_product = (cx * rx) + (cy * ry) + (cz * rz)
                    projection = dot_product / ref_mag
                    threshold = calib.get("threshold", 26000)

                    if abs(projection) > threshold:
                        now = time.time()
                        if (now - self.last_strum_time) > self.STRUM_COOLDOWN:
                            is_strumming = True
                            strum_direction = "DOWN" if projection > 0 else "UP"
                            self.last_strum_time = now
                            print(f"🎸 PALHETADA: {strum_direction} (Força: {abs(projection):.0f})")

        # =====================================================================
        # PASSO 3: LÓGICA DE ATIVAÇÃO DO EMULADOR
        # =====================================================================
        
        # Regra 1: Se bater, ativa as teclas dos dedos que estão armados
        if is_strumming:
            # Copia o estado dos dedos armados para as "Lanes" ativas
            self.lanes_vector = self.fingers_armed[:] 

        # Regra 2: Se o dedo soltar (desarmar), a tecla tem que desligar IMEDIATAMENTE
        # mesmo que não tenha batida nova.
        for i in range(4):
            if self.fingers_armed[i] == 0:
                self.lanes_vector[i] = 0

        # Atualiza o emulador com o estado final calculado
        emulator.atualizar_estado(self.lanes_vector)
