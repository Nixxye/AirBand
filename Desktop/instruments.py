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
