import cv2
import mediapipe as mp
import math
import numpy as np

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

# Função para desenhar uma linha tracejada
def linha_tracejada(img, p1, p2, cor, espessura=1, tamanho_tracejado=10):
    p1 = np.array(p1)
    p2 = np.array(p2)
    dist = np.linalg.norm(p1 - p2)
    direcao = (p2 - p1) / dist
    for i in range(0, int(dist), tamanho_tracejado * 2):
        inicio = tuple(np.int32(p1 + direcao * i))
        fim = tuple(np.int32(p1 + direcao * (i + tamanho_tracejado)))
        cv2.line(img, inicio, fim, cor, espessura)

# Inicializa o MediaPipe Pose
mp_pose = mp.solutions.pose
cap = cv2.VideoCapture(0)

# Círculos de interação
circulos = [
    {'center': [0.1, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
    {'center': [0.3, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
    {'center': [0.7, 0.8], 'raio': 40, 'cor': (255, 0, 0)},
    {'center': [0.9, 0.8], 'raio': 40, 'cor': (255, 0, 0)}
]

# Teclas de controle
teclas = [
    {'up': ord('1'), 'down': ord('q'), 'raio_up': ord('a'), 'raio_down': ord('z')},
    {'up': ord('2'), 'down': ord('w'), 'raio_up': ord('s'), 'raio_down': ord('x')},
    {'up': ord('3'), 'down': ord('e'), 'raio_up': ord('d'), 'raio_down': ord('c')},
    {'up': ord('4'), 'down': ord('r'), 'raio_up': ord('f'), 'raio_down': ord('v')}
]

velocidade = 0.02
delta_raio = 5
limite_angulo_vert = 130.0
limite_angulo_cotovelo = 150.0
delta_limite = 2.0

with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
    while cap.isOpened():
        success, frame = cap.read()
        frame = cv2.flip(frame, 1)  # espelha a imagem
        if not success:
            print("Erro ao acessar a câmera.")
            break

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = pose.process(image)
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        h, w, _ = image.shape

        def to_pixel(p): return int(p.x * w), int(p.y * h)

        pulso_esq = pulso_dir = (-100, -100)

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            # Pega os pontos principais
            left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
            left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value]
            right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value]

            # Converte para coordenadas de pixel
            l_sh, l_el, l_wr = to_pixel(left_shoulder), to_pixel(left_elbow), to_pixel(left_wrist)
            r_sh, r_el, r_wr = to_pixel(right_shoulder), to_pixel(right_elbow), to_pixel(right_wrist)

            pulso_esq, pulso_dir = l_wr, r_wr

            # Ângulos do cotovelo
            ang_esq = calcular_angulo(l_sh, l_el, l_wr)
            ang_dir = calcular_angulo(r_sh, r_el, r_wr)

            # Ângulo entre o braço e a vertical
            l_vert = (l_sh[0], l_sh[1] - 150)
            r_vert = (r_sh[0], r_sh[1] - 150)
            ang_esq_vert = calcular_angulo(l_el, l_sh, l_vert)
            ang_dir_vert = calcular_angulo(r_el, r_sh, r_vert)

            # --- Cores baseadas nos limites ---
            # Vertical (ombro)
            cor_esq_vert = (0, 255, 128)
            cor_dir_vert = (255, 128, 0)
            if ang_esq_vert < limite_angulo_vert:
                cor_esq_vert = (0, 0, 255)
            if ang_dir_vert < limite_angulo_vert:
                cor_dir_vert = (0, 0, 255)

            # Cotovelo
            cor_esq_cot = (0, 255, 0)
            cor_dir_cot = (0, 255, 255)
            if ang_esq > limite_angulo_cotovelo:
                cor_esq_cot = (255, 0, 255)  # Rosa
            if ang_dir > limite_angulo_cotovelo:
                cor_dir_cot = (255, 0, 255)  # Rosa

            # --- DESENHA OS BRAÇOS ---
            cv2.line(image, l_sh, l_el, (0, 255, 0), 3)
            cv2.line(image, l_el, l_wr, (0, 255, 0), 3)
            cv2.line(image, r_sh, r_el, (0, 255, 255), 3)
            cv2.line(image, r_el, r_wr, (0, 255, 255), 3)

            # Linhas verticais tracejadas
            linha_tracejada(image, l_sh, l_vert, (200, 200, 200), espessura=1)
            linha_tracejada(image, r_sh, r_vert, (200, 200, 200), espessura=1)

            # Pontos
            cv2.circle(image, l_sh, 8, cor_esq_vert, -1)
            cv2.circle(image, l_el, 8, cor_esq_cot, -1)
            cv2.circle(image, l_wr, 8, (0, 200, 200), -1)
            cv2.circle(image, r_sh, 8, cor_dir_vert, -1)
            cv2.circle(image, r_el, 8, cor_dir_cot, -1)
            cv2.circle(image, r_wr, 8, (0, 200, 255), -1)

            # --- TEXTOS NOS PONTOS ---
            cv2.putText(image, f"{ang_esq:.1f}°", (l_el[0]+10, l_el[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_cot, 2)
            cv2.putText(image, f"{ang_esq_vert:.1f}°", (l_sh[0]+10, l_sh[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_vert, 2)
            cv2.putText(image, f"{ang_dir:.1f}°", (r_el[0]+10, r_el[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_cot, 2)
            cv2.putText(image, f"{ang_dir_vert:.1f}°", (r_sh[0]+10, r_sh[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_vert, 2)

            # --- LEGENDAS COMPLETAS ---
            cv2.putText(image, f"Ang Esq (cotovelo): {ang_esq:.1f}", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_cot, 2)
            cv2.putText(image, f"Ang Dir (cotovelo): {ang_dir:.1f}", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_cot, 2)
            cv2.putText(image, f"Vert Esq (ombro): {ang_esq_vert:.1f}", (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_esq_vert, 2)
            cv2.putText(image, f"Vert Dir (ombro): {ang_dir_vert:.1f}", (10, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_dir_vert, 2)
            cv2.putText(image, f"Limite vertical: {limite_angulo_vert:.1f} graus (+/-)", (10, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
            cv2.putText(image, f"Limite cotovelo: {limite_angulo_cotovelo:.1f} graus (*/)", (10, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Desenha círculos e verifica colisão
        for c in circulos:
            cx = int(c['center'][0] * w)
            cy = int(c['center'][1] * h)
            cor = c['cor']
            for pulso in [pulso_esq, pulso_dir]:
                dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                if dist <= c['raio']:
                    cor = (0, 0, 255)
            cv2.circle(image, (cx, cy), c['raio'], cor, 2)

        cv2.imshow('MediaPipe Pose', image)

        # --- CAPTURA DE TECLAS ---
        key = cv2.waitKey(5) & 0xFF
        if key == ord('p'):
            break
        # Limite do ângulo vertical (ombro)
        elif key in [ord('='), ord('+')]:
            limite_angulo_vert = min(180, limite_angulo_vert + delta_limite)
        elif key in [ord('-'), ord('_')]:
            limite_angulo_vert = max(0, limite_angulo_vert - delta_limite)
        # Limite do cotovelo
        elif key == ord('*'):
            limite_angulo_cotovelo = min(180, limite_angulo_cotovelo + delta_limite)
        elif key == ord('/'):
            limite_angulo_cotovelo = max(0, limite_angulo_cotovelo - delta_limite)

        # Movimentação e tamanho dos círculos
        for i, c in enumerate(circulos):
            if key == teclas[i]['up']:
                c['center'][1] = max(0.0, c['center'][1] - velocidade)
            elif key == teclas[i]['down']:
                c['center'][1] = min(1.0, c['center'][1] + velocidade)
            elif key == teclas[i]['raio_up']:
                c['raio'] = min(200, c['raio'] + delta_raio)
            elif key == teclas[i]['raio_down']:
                c['raio'] = max(10, c['raio'] - delta_raio)

cap.release()
cv2.destroyAllWindows()
