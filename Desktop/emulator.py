import cv2
import mediapipe as mp
import math
import numpy as np

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
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


class Camera:
    """ Gerencia a captura da câmera. """
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

    @staticmethod
    def calcular_angulo(a, b, c):
        angulo = math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0]))
        angulo = abs(angulo)
        if angulo > 180: angulo = 360 - angulo
        return angulo

    def release(self):
        if self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()


class InputData:
    """ Classe base que agrupa as fontes de entrada. """
    def __init__(self):
        self.camera = Camera()
        self.communication = Communication()
