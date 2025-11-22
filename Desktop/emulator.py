import cv2
import mediapipe as mp
import math
import numpy as np

try:
    import vgamepad as vg
    _VGAMEPAD_DISPONIVEL = True
except ImportError:
    HAS_VGAMEPAD = False

from communication import Communication


class Emulator:
    """ Gerencia a saída de emulação. """
    def __init__(self):
        self.gamepad = vg.VX360Gamepad() if HAS_VGAMEPAD else None
        if HAS_VGAMEPAD:
            print("Controlador Virtual (vgamepad) conectado.")
        else:
            print("vgamepad não encontrado. Emulação de joystick desabilitada.")

    def process_guitar_action(self, action): pass

    def process_drum_action(self, action): pass



class InputData:
    """ Classe base que agrupa as fontes de entrada. """
    def __init__(self):
        self.communication = Communication()
