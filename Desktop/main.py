import cv2
import mediapipe as mp
import math

# Função para calcular o ângulo entre três pontos
def calcular_angulo(a, b, c):
    angulo = math.degrees(
        math.atan2(c[1] - b[1], c[0] - b[0]) -
        math.atan2(a[1] - b[1], a[0] - b[0])
    )
    angulo = abs(angulo)
    if angulo > 180:
        angulo = 360 - angulo
    return angulo

# Inicializa os módulos do MediaPipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# Abre a webcam
cap = cv2.VideoCapture(0)

# Define os círculos (coordenadas normalizadas e raio em pixels)
circulos = [
    {'center': (0.1, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
    {'center': (0.3, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
    {'center': (0.7, 0.8), 'raio': 40, 'cor': (255, 0, 0)},  # Azul
    {'center': (0.9, 0.8), 'raio': 40, 'cor': (255, 0, 0)}   # Azul
]

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("Erro ao acessar a câmera.")
            break

        # Converte a imagem para RGB e processa
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        h, w, _ = image.shape

        # Converte coordenadas normalizadas para pixels
        def to_pixel(p): return int(p.x * w), int(p.y * h)

        # Inicializa posição do pulso
        pulso_esq = (-100, -100)
        pulso_dir = (-100, -100)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            landmarks = results.pose_landmarks.landmark

            # Pontos dos braços
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]

            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
            right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]

            # Converte para pixels
            l_sh, l_el, l_wr = to_pixel(left_shoulder), to_pixel(left_elbow), to_pixel(left_wrist)
            r_sh, r_el, r_wr = to_pixel(right_shoulder), to_pixel(right_elbow), to_pixel(right_wrist)

            pulso_esq = l_wr
            pulso_dir = r_wr

            # Calcula ângulos
            ang_esq = calcular_angulo(l_sh, l_el, l_wr)
            ang_dir = calcular_angulo(r_sh, r_el, r_wr)

            # Exibe coordenadas e ângulo na tela
            cv2.putText(image, f"E (O:{l_sh}, C:{l_el}, P:{l_wr})", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(image, f"Angulo Esq: {ang_esq:.1f}", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.putText(image, f"D (O:{r_sh}, C:{r_el}, P:{r_wr})", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(image, f"Angulo Dir: {ang_dir:.1f}", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Desenhar círculo no cotovelo
            cv2.circle(image, l_el, 6, (0, 255, 0), -1)
            cv2.putText(image, f"{ang_esq:.1f}", (l_el[0] + 10, l_el[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.circle(image, r_el, 6, (0, 255, 255), -1)
            cv2.putText(image, f"{ang_dir:.1f}", (r_el[0] + 10, r_el[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Desenha os círculos e checa colisão com pulsos
        for c in circulos:
            cx = int(c['center'][0] * w)
            cy = int(c['center'][1] * h)
            cor = c['cor']
            for pulso in [pulso_esq, pulso_dir]:
                dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                if dist <= c['raio']:
                    cor = (0, 0, 255)  # vermelho
            cv2.circle(image, (cx, cy), c['raio'], cor, 2)

        # Exibe a imagem
        cv2.imshow('MediaPipe Pose', image)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
