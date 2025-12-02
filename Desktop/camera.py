import cv2
import mediapipe as mp
import math
import numpy as np

class CameraProcessor:
    """
    Classe responsável pela lógica de Visão Computacional (OpenCV + MediaPipe).
    Processa o frame, desenha o esqueleto/tambores e retorna os dados lógicos.
    """
    def __init__(self):
        self.cap = None
        
        # Inicializa MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose_processor = self.mp_pose.Pose(
            min_detection_confidence=0.5, 
            min_tracking_confidence=0.5
        )
        
        # --- Configuração dos Tambores Virtuais ---
        # 'center': Posição normalizada [x, y] (0.0 a 1.0)
        # 'raio': Raio em pixels
        self.circulos = [
            {'center': [0.1, 0.65], 'raio': 50, 'cor': (255, 0, 0)}, # Drum 1 (Canto superior esquerdo)
            {'center': [0.3, 0.85], 'raio': 50, 'cor': (255, 0, 0)},  # Drum 2 (Centro-esquerda)
            {'center': [0.7, 0.85], 'raio': 50, 'cor': (255, 0, 0)},  # Drum 3 (Centro-direita)
            {'center': [0.9, 0.65], 'raio': 50, 'cor': (255, 0, 0)} # Drum 4 (Canto superior direito)
        ]
        self.prev_inside = [False] * len(self.circulos)

        # --- Novos: sustain de hit (manter botão pressionado por mais frames) ---
        # Ajuste self.hold_frames para aumentar/diminuir a duração (em frames)
        self.hold_frames = 6  # por padrão ~200ms @30FPS
        self.hold_counters = [0] * len(self.circulos)

        # Limites de ângulos para coloração visual
        self.limite_angulo_vert = 130.0
        self.limite_angulo_cotovelo = 150.0

    def start(self):
        """ Tenta iniciar a captura de vídeo. """
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
            return self.cap.isOpened()
        return True

    def stop(self):
        """ Libera a câmera. """
        if self.cap:
            self.cap.release()
            self.cap = None

    def is_active(self):
        return self.cap is not None and self.cap.isOpened()

    def process_frame(self):
        """ 
        Captura um frame, processa a pose e detecta colisões.
        Retorna:
            - final_image_rgb: Imagem pronta para o Qt (QImage)
            - data: Dicionário com ângulos e vetor de bateria
        """
        if not self.is_active():
            return None, None

        ret, frame = self.cap.read()
        if not ret:
            self.stop()
            return None, None

        # 1. Espelha horizontalmente (efeito espelho)
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        
        # 2. Converte para RGB (MediaPipe exige RGB)
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False # Pequena otimização
        
        # 3. Inferência do MediaPipe
        results = self.pose_processor.process(image_rgb)
        
        # 4. Prepara imagem para desenho (OpenCV usa BGR)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

        # Estrutura de dados de retorno
        data = {
            "Angulo_Esq_Cotovelo": 0, "Angulo_Dir_Cotovelo": 0,
            "Angulo_Esq_Vert": 0, "Angulo_Dir_Vert": 0,
            "Baterias_Ativadas": "Nenhuma",
            "Drum_Vector": [0] * len(self.circulos), # Vetor zerado [0, 0, 0, 0]
            "Limite_Vert": self.limite_angulo_vert,
            "Camera_Ativa": True
        }

        # Posições iniciais dos pulsos (fora da tela)
        pulso_esq = pulso_dir = (-100, -100)

        # --- PROCESSAMENTO DO ESQUELETO ---
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Helper para converter normalizado -> pixel
            def to_px(lm): return int(lm.x * w), int(lm.y * h)

            # Obtém pontos chave
            l_sh = to_px(landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value])
            l_el = to_px(landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value])
            l_wr = to_px(landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value])
            r_sh = to_px(landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value])
            r_el = to_px(landmarks[self.mp_pose.PoseLandmark.RIGHT_ELBOW.value])
            r_wr = to_px(landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST.value])

            pulso_esq, pulso_dir = l_wr, r_wr

            # Cálculos de Ângulos
            ang_esq = self._calcular_angulo(l_sh, l_el, l_wr)
            ang_dir = self._calcular_angulo(r_sh, r_el, r_wr)
            
            # Pontos auxiliares para vertical
            l_vert = (l_sh[0], l_sh[1] - 150)
            r_vert = (r_sh[0], r_sh[1] - 150)
            ang_esq_vert = self._calcular_angulo(l_el, l_sh, l_vert)
            ang_dir_vert = self._calcular_angulo(r_el, r_sh, r_vert)

            # Salva nos dados
            data["Angulo_Esq_Cotovelo"] = ang_esq
            data["Angulo_Dir_Cotovelo"] = ang_dir
            data["Angulo_Esq_Vert"] = ang_esq_vert
            data["Angulo_Dir_Vert"] = ang_dir_vert

            # Define cores baseadas no ângulo (Feedback visual)
            cor_esq = (0, 0, 255) if ang_esq_vert < self.limite_angulo_vert else (0, 255, 128)
            cor_dir = (0, 0, 255) if ang_dir_vert < self.limite_angulo_vert else (255, 128, 0)

            # Desenha linhas do braço
            cv2.line(image_bgr, l_sh, l_el, (0, 255, 0), 3)
            cv2.line(image_bgr, l_el, l_wr, (0, 255, 0), 3)
            cv2.line(image_bgr, r_sh, r_el, (0, 255, 255), 3)
            cv2.line(image_bgr, r_el, r_wr, (0, 255, 255), 3)
            
            # Desenha juntas
            cv2.circle(image_bgr, l_sh, 8, cor_esq, -1)
            cv2.circle(image_bgr, r_sh, 8, cor_dir, -1)
            cv2.circle(image_bgr, l_wr, 10, (0, 200, 200), -1) # Pulso
            cv2.circle(image_bgr, r_wr, 10, (0, 200, 255), -1) # Pulso

        # --- LÓGICA DE COLISÃO (BATERIA) ---
        hits_text = []
        
        # Vetor local para preencher
        current_drum_vector = [0] * len(self.circulos)

        for i, c in enumerate(self.circulos):
            cx = int(c['center'][0] * w) 
            cy = int(c['center'][1] * h)
            cor = c['cor']

            # 1. Verifica se o pulso está ATUALMENTE DENTRO do círculo
            current_inside = False
            for pulso in [pulso_esq, pulso_dir]:
                if pulso[0] > 0: 
                    dist = math.hypot(pulso[0] - cx, pulso[1] - cy)
                    if dist <= c['raio']:
                        current_inside = True
                        break
            
            # 2. LÓGICA ONE-SHOT (Detecção de borda)
            if current_inside and not self.prev_inside[i]:
                # É um NOVO HIT: dispara o evento
                hits_text.append(f"Drum {i+1}")
                # Ao invés de apenas um frame, inicializamos o contador de sustain
                self.hold_counters[i] = self.hold_frames
                cor = (0, 255, 0) # Cor de novo hit (Verde)
                
                # Atualiza o estado: agora está dentro
                self.prev_inside[i] = True
                
            elif not current_inside and self.prev_inside[i]:
                # Saiu do círculo: reseta o estado para permitir o próximo hit
                self.prev_inside[i] = False
                
            elif current_inside and self.prev_inside[i]:
                 # Está dentro, mas não é um novo hit (contínuo)
                 cor = (0, 0, 255) # Cor de contato contínuo (Vermelho)
            
            # Se o contador de sustain está ativo, marca o tambor como acionado
            if self.hold_counters[i] > 0:
                current_drum_vector[i] = 1
                self.hold_counters[i] -= 1
            
            # Desenha o tambor
            cv2.circle(image_bgr, (cx, cy), c['raio'], cor, 2)
            

        # Atualiza os dados finais
        if hits_text:
            data["Baterias_Ativadas"] = ", ".join(hits_text)
        
        # Salva o vetor calculado no dicionário
        data["Drum_Vector"] = current_drum_vector

        # 5. Converte imagem final para RGB (para exibir no PyQt)
        final_image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        
        return final_image_rgb, data

    def _calcular_angulo(self, a, b, c):
        """ Calcula ângulo entre 3 pontos (x,y). """
        ang = math.degrees(math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0]))
        ang = abs(ang)
        if ang > 180: ang = 360 - ang
        return ang
