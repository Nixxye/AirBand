from emulator import InputData, Emulator
import math


class Instrument(InputData):
    """ Classe base para um instrumento. """
    def __init__(self):
        super().__init__()


class Drum(Instrument):
    """ Implementação da Bateria. """
    def __init__(self):
        super().__init__()

    def run_simulation(self):
        print("Simulação de bateria iniciada... (Pressione 'q' na janela OpenCV para sair)")
        pass


class Guitar(Instrument):
    """ Implementação da Guitarra. """
    def __init__(self):
        pass

    def process_data(self, logical_data, mappings, emulator: Emulator):
        """
        Processa os dados lógicos da luva usando os mapeamentos de 3 pontos.
        """

        for action, current_value in logical_data.items():
            if action not in mappings:
                continue

            mapping = mappings[action]

            # Lógica para DEDOS (3 pontos)
            if "Dedo" in action:
                try:
                    rest_val = float(mapping.get("rest", 4095))
                    half_val = float(mapping.get("half", 2048))
                    full_val = float(mapping.get("full", 0))
                except ValueError:
                    continue 

                if current_value < full_val: pass
                elif current_value < half_val: pass
                elif current_value < rest_val: pass
                else: pass

            # Lógica para BATIDAS (2 pontos)
            elif "Batida" in action:
                if not isinstance(logical_data[action], dict):
                    continue

                try:
                    rest_map = mapping.get("rest", {})
                    peak_map = mapping.get("peak", {})
                    rest_mag = math.sqrt(
                        float(rest_map.get("ax", 0))**2 +
                        float(rest_map.get("ay", 0))**2 +
                        float(rest_map.get("az", 0))**2
                    )
                    peak_mag = math.sqrt(
                        float(peak_map.get("ax", 0))**2 +
                        float(peak_map.get("ay", 0))**2 +
                        float(peak_map.get("az", 0))**2
                    )
                    current_val_map = logical_data[action]
                    current_mag = math.sqrt(
                        float(current_val_map.get("ax", 0))**2 +
                        float(current_val_map.get("ay", 0))**2 +
                        float(current_val_map.get("az", 0))**2
                    )
                except (ValueError, TypeError):
                    continue

                threshold = rest_mag + (peak_mag - rest_mag) * 0.75

                if current_mag > threshold and current_mag > rest_mag + 0.1:
                    pass
