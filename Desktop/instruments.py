import math
import numpy as np
from emulator import InputData, Emulator


class Instrument(InputData):
    """ Classe base genérica para instrumentos com estado. """
    def __init__(self):
        self.lanes_vector = [0, 0, 0, 0]

class Drum(Instrument):
    def __init__(self):
        super().__init__()

    def process_data(self, camera_data, mappings, emulator: Emulator):
        # Implementação futura da bateria via câmera
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
        self.strum_action = "Batida (Giroscópio)"

    def _get_magnitude(self, data):
        return math.sqrt(data.get("ax",0)**2 + data.get("ay",0)**2 + data.get("az",0)**2)

    def _get_dist(self, v1, v2):
        return math.sqrt(
            (v1.get("ax",0) - v2.get("ax",0))**2 +
            (v1.get("ay",0) - v2.get("ay",0))**2 +
            (v1.get("az",0) - v2.get("az",0))**2
        )

    def process_data(self, logical_data, mappings, emulator: Emulator):
        """
        Processa lógica de Dedos (Lanes) e Palhetada (Strum).
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
                    
                    # Garante intervalo min/max (sensores flex podem inverter)
                    lim_inf = min(half, full)
                    lim_sup = max(half, full)
                    
                    # Ativa se estiver na zona de pressão (entre meio e completo)
                    if lim_inf <= val <= lim_sup:
                        new_lanes[i] = 1
                    # Se passou do máximo (apertou muito forte), mantém ativo
                    elif abs(val - full) < abs(val - half):
                        new_lanes[i] = 1
                    else:
                        new_lanes[i] = 0
                        
                except (ValueError, TypeError):
                    new_lanes[i] = 0

        # Atualiza emulador apenas se houver mudança nos dedos
        if new_lanes != self.lanes_vector:
            self.lanes_vector = new_lanes
            emulator.atualizar_estado(self.lanes_vector)

        # --- 2. Lógica da Palhetada (Strum) ---
        # O Emulador fornecido não possui método de Strum, 
        # mas a lógica de detecção fica pronta aqui para expansão futura.
        if self.strum_action in mappings and self.strum_action in logical_data:
            current_vec = logical_data[self.strum_action]
            calib = mappings[self.strum_action]
            
            try:
                rest = calib.get("rest", {})
                up = calib.get("up", {})
                
                mag_curr = self._get_magnitude(current_vec)
                mag_rest = self._get_magnitude(rest)
                mag_up = self._get_magnitude(up)
                
                # Limiar de 40% da força calibrada
                threshold = mag_rest + (mag_up - mag_rest) * 0.4
                
                if mag_curr > threshold:
                    # Detectou batida (pode adicionar lógica de direção Up/Down aqui)
                    pass
            except:
                pass
    def __init__(self):
        super().__init__()
        # Mapeamento de indices para nomes das ações
        self.finger_actions = [
            "Dedo 1 (Indicador)", 
            "Dedo 2 (Médio)", 
            "Dedo 3 (Anelar)", 
            "Dedo 4 (Mindinho)"
        ]
        self.strum_action_name = "Batida (Giroscópio)"
        self.last_strum_time = 0

    def _calculate_magnitude(self, data_dict):
        """ Auxiliar para calcular magnitude vetorial de um dict {ax, ay, az}. """
        return math.sqrt(data_dict.get("ax",0)**2 + data_dict.get("ay",0)**2 + data_dict.get("az",0)**2)

    def _calculate_distance(self, vec_a, vec_b):
        """ Distância Euclidiana entre dois vetores 3D. """
        return math.sqrt(
            (vec_a.get("ax",0) - vec_b.get("ax",0))**2 +
            (vec_a.get("ay",0) - vec_b.get("ay",0))**2 +
            (vec_a.get("az",0) - vec_b.get("az",0))**2
        )

    def process_data(self, logical_data, mappings, emulator: Emulator):
        """
        Lógica principal da Guitarra.
        1. Verifica flexão dos dedos (Lanes).
        2. Verifica movimento do giroscópio (Strum).
        3. Notifica emulador.
        """
        
        current_lanes = [0, 0, 0, 0]
        strum_state = "Neutro"

        for i, action_name in enumerate(self.finger_actions):
            if action_name not in mappings or action_name not in logical_data:
                continue

            val = logical_data[action_name]
            calib = mappings[action_name]
            
            try:
                rest = float(calib.get("rest", 0))
                half = float(calib.get("half", 0))
                full = float(calib.get("full", 0))
            except (ValueError, TypeError):
                continue

            # Lógica: Ativar se estiver ENTRE 'half' e 'full'.
            # Flex sensors podem aumentar ou diminuir resistência, então usamos min/max.
            limite_inferior = min(half, full)
            limite_superior = max(half, full)
            
            # Se o valor do sensor "passou" do meio em direção ao full
            if limite_inferior <= val <= limite_superior:
                current_lanes[i] = 1
            # Fallback: Se passou do full (dobrou demais), mantém ativo
            elif abs(val - full) < abs(val - rest): 
                current_lanes[i] = 1
            else:
                current_lanes[i] = 0

        if self.strum_action_name in mappings and self.strum_action_name in logical_data:
            raw_gyro = logical_data[self.strum_action_name] # Vetor atual {ax, ay, az}
            calib = mappings[self.strum_action_name]
            
            # Pega vetores de calibração
            rest_vec = calib.get("rest", {})
            up_vec = calib.get("up", {})
            down_vec = calib.get("down", {})

            # Calcula magnitudes
            curr_mag = self._calculate_magnitude(raw_gyro)
            rest_mag = self._calculate_magnitude(rest_vec)
            up_mag_ref = self._calculate_magnitude(up_vec)
            
            # Limiar dinâmico: precisa ser pelo menos 40% da força do movimento calibrado
            threshold = rest_mag + (up_mag_ref - rest_mag) * 0.4

            if curr_mag > threshold:
                # Movimento detectado! Agora descobrimos a direção (Cima ou Baixo)
                # Comparando qual vetor de pico calibrado está mais próximo do vetor atual
                dist_to_up = self._calculate_distance(raw_gyro, up_vec)
                dist_to_down = self._calculate_distance(raw_gyro, down_vec)

                if dist_to_up < dist_to_down:
                    strum_state = "Up"
                else:
                    strum_state = "Down"

        # Atualiza o vetor interno
        state_changed = (current_lanes != self.lanes_vector) or (strum_state != "Neutro")
        self.lanes_vector = current_lanes

        # Sempre notifica o emulador se houver mudança ou se estiver tocando (para debug continuo)
        if state_changed:
            emulator.update_guitar_state(self.lanes_vector, strum_state)