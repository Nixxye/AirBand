import sys

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False

class Emulator:
    """ 
    Gerencia a saída de emulação (Virtual Controller). 
    Recebe estados abstratos dos instrumentos e converte em botões.
    """
    def __init__(self):
        self.gamepad = vg.VX360Gamepad() if HAS_VGAMEPAD else None
        self.active_lanes = [0, 0, 0, 0] # Vetor de 4 posições
        self.last_strum = "Neutro"
        
        if HAS_VGAMEPAD:
            print("[EMULATOR] Controlador Virtual (ViGEm) conectado.")
        else:
            print("[EMULATOR] AVISO: 'vgamepad' não instalado. Apenas simulação de console.")

    def update_guitar_state(self, lanes, strum_action):
        """
        Atualiza o estado da guitarra e envia para o joystick.
        lanes: Lista [bool, bool, bool, bool] (Ex: [1, 0, 0, 1])
        strum_action: "Up", "Down" ou "Neutro"
        """
        self.active_lanes = lanes
        self.last_strum = strum_action

        # --- Feedback Visual no Console ---
        # Cria uma string visual, ex: [X] [ ] [X] [ ] | STRUM: Down
        lanes_visual = "".join(["[X]" if l else "[ ]" for l in lanes])
        strum_visual = f"STRUM: {strum_action:^6}"
        sys.stdout.write(f"\r🎸 STATUS: {lanes_visual} | {strum_visual}   ")
        sys.stdout.flush()


class InputData:
    """ Classe base (pode ser expandida para logging global). """
    pass