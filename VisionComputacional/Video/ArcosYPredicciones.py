# LIBRERIAS USADAS
import cv2
import os
import mediapipe as mp
import numpy as np
import csv
from joblib import load

# CARGAR ARCHIVOS
current_dir = os.path.dirname(__file__)

# Modelo y scaler
model_path = os.path.join(current_dir, '..', 'ModelosML', 'PrediccionEtapas.joblib')
model = load(model_path)
scaler_path = os.path.join(current_dir, '..', 'ModelosML', 'Scaler.joblib')
scaler = load(scaler_path)
scaler.feature_names_in_ = None

# Nombre entrada y salidas
input_video_path = os.path.join(current_dir, '..', 'Pruebas', 'Gait.mp4')
output_video_path = os.path.join(current_dir, '..', 'Pruebas', 'Analyzed_Gait.mp4')
csv_path = os.path.join(current_dir, '..', 'Pruebas', 'Analysis.csv')

# INICIALIZAR MEDIAPIPE
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# Colores y parametros
CL = (130,140,40)
CP = (205,218,56)
CCI, CRI, CTOI = (30,180,200), (30,120,200), (30,60,200)
CCD, CRD, CTOD = (200,180,30), (200,120,30), (200,60,30)
font = cv2.FONT_HERSHEY_PLAIN
text_color = (0, 0, 0)
T1 = 2
T2 = T1 + 1

# Diccionario de índices
indices = {
    'N': 0, 'H_I': 11, 'H_D': 12, 'C_I': 23, 'C_D': 24,
    'R_I': 25, 'R_D': 26, 'TO_I': 27, 'TO_D': 28,
    'TA_I': 29, 'TA_D': 30
}

# Diccionario para cambiar etiquetas
mapa_etiquetas = {
    "CONTACTO INICIAL": "INITIAL CONTACT",
    "RESPUESTA A LA CARGA": "LOADING RESPONSE",
    "APOYO MEDIO": "MID-STANCE",
    "APOYO FINAL": "TERMINAL STANCE",
    "PRE OSCILACION": "PRE-SWING",
    "OSCILACION INICIAL": "INITIAL SWING",
    "OSCILACION MEDIA": "MID-SWING",
    "OSCILACION FINAL": "TERMINAL SWING",
}

# FUNCIÓN PARA CALCULAR ANGULOS
def angle(a, b, c):
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    ang = np.degrees(np.arccos(cosine_angle))
    if ang > 180:
        ang = ang - 180
    if ang < 90:
        ang = 180 - ang
    ang = abs(round(ang))
    # Devolvemos el angulo calculado y el punto
    return ang, b

# Configurar la captura de video
cap = cv2.VideoCapture(input_video_path)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
frames = 0
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter(output_video_path, fourcc, fps, (W, H))


with mp_pose.Pose(static_image_mode=False, model_complexity=2, min_detection_confidence=0.5) as pose:
    with open(csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Time [s]','Phase', 'Hip Joint Angle (R)','Knee Joint Angle (R)','Ankle Joint Angle (R)',
                         'Hip Joint Angle (L)','Knee Joint Angle (L)','Ankle Joint Angle (L)'])
        
        while cap.isOpened():
            ret, image = cap.read()
            if not ret:
                break
            frames += 1
            if frames % int(total_frames*0.05) == 0:
              print(f"Progreso: {frames}/{total_frames} frames ({100*frames/total_frames:.0f}%)")   

            ts = cap.get(cv2.CAP_PROP_POS_MSEC)
            ts = round(ts/1000, 2)
            
            CXI, CXD = round(W/55), -round(W/17)
            top_left = (5,5)
            BCX, BCY = round(W/4.8), round(W/24)
            TX, TY = round(W/120), round(W/38)
            bottom_right = (600, BCY)

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)
            image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

            if results.pose_landmarks is None:
                # Si queremos que aparezcan los tiempos fuera de cuadro
                cv2.putText(image, "Persona fuera de cuadro", (W//4, H//2), 
                       font, 2, (0, 0, 255), 3)
                writer.writerow([ts, "NO PERSON", 0, 0, 0, 0, 0, 0])
            else:
              try:
                  landmarks = results.pose_landmarks.landmark
                  
                  # Obtener puntos relevantes
                  puntos = {}
                  for k, i in indices.items():
                      puntos[k] = np.multiply([landmarks[i].x, landmarks[i].y], [W, H]).astype(int)

                  # Dibujar pose
                  mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                          mp_drawing.DrawingSpec(CL, T2, T2),
                                          mp_drawing.DrawingSpec(CP, T2, T2))

                  # Inicializar variables para CSV
                  DCD_ang, DRD_ang, DTOD_ang = 0, 0, 0
                  DCI_ang, DRI_ang, DTOI_ang = 0, 0, 0

                  # Procesar lado derecho si es visible
                  if all(landmarks[i].visibility > 0.5 for i in [24, 26, 28]):
                      DCD_ang, DCD_pos = angle(puntos['H_D'], puntos['C_D'], puntos['R_D'])
                      DRD_ang, DRD_pos = angle(puntos['C_D'], puntos['R_D'], puntos['TO_D'])
                      DTOD_ang, DTOD_pos = angle(puntos['R_D'], puntos['TO_D'], puntos['TA_D'])
                      DRD_ang = 180 - DRD_ang
                      DTOD_ang = 180 - (DTOD_ang - 45)

                      # Dibujar ángulos
                      for ang, pos, color in zip([DCD_ang, DRD_ang, DTOD_ang], 
                                              [DCD_pos, DRD_pos, DTOD_pos], 
                                              [CCD, CRD, CTOD]):
                          cv2.circle(image, pos, T2*2, color, -1)
                          cv2.putText(image, str(ang), np.array(pos) + [CXI, -1], font, T1, color, T2)

                  # Procesar lado izquierdo si es visible
                  if all(landmarks[i].visibility > 0.5 for i in [23, 25, 27]):
                    DCI_ang, DCI_pos = angle(puntos['H_I'], puntos['C_I'], puntos['R_I'])
                    DRI_ang, DRI_pos = angle(puntos['C_I'], puntos['R_I'], puntos['TO_I'])
                    DTOI_ang, DTOI_pos = angle(puntos['R_I'], puntos['TO_I'], puntos['TA_I'])
                    DRI_ang = 180 - DRI_ang
                    DTOI_ang = 180 - (DTOI_ang - 45)

                    # Dibujar ángulos
                    for ang, pos, color in zip([DCI_ang, DRI_ang, DTOI_ang], 
                                            [DCI_pos, DRI_pos, DTOI_pos], 
                                            [CCI, CRI, CTOI]):
                        cv2.circle(image, pos, T2*2, color, -1)
                        cv2.putText(image, str(ang), np.array(pos) + [CXD, -1], font, T1, color, T2)

                    # Calcular diferencias para el modelo
                    # MIRADA DERECHA
                    if puntos['N'][0] > puntos['C_I'][0]:  
                        dif_ac = DCI_ang - DCD_ang
                        dif_ar = DRI_ang - DRD_ang
                        dif_at = DTOI_ang - DTOD_ang
                        dif_pcy = landmarks[23].y - landmarks[24].y
                        dif_pry = landmarks[25].y - landmarks[26].y
                        dif_pty = landmarks[27].y - landmarks[28].y
                    # MIRADA IZQUIERDA    
                    else:  
                        dif_ac = DCD_ang - DCI_ang
                        dif_ar = DRD_ang - DRI_ang
                        dif_at = DTOD_ang - DTOI_ang
                        dif_pcy = landmarks[24].y - landmarks[23].y
                        dif_pry = landmarks[26].y - landmarks[25].y
                        dif_pty = landmarks[28].y - landmarks[27].y

                    dif_pcx = landmarks[23].x - landmarks[24].x
                    dif_prx = landmarks[25].x - landmarks[26].x
                    dif_ptx = landmarks[27].x - landmarks[28].x

                    # Preparar datos para el modelo
                    X = [[dif_ac, dif_ar, dif_at, dif_pcx, dif_pcy, dif_prx, dif_pry, dif_ptx, dif_pty]]
                    X = scaler.transform(X)

                    # Predicción
                    y_pred = model.predict(X)
                    text = [mapa_etiquetas.get(label, label) for label in y_pred][0]

                    # Mostrar fase de marcha
                    (text_width, text_height), baseline = cv2.getTextSize(text, font, T1, T2)
                    center_x = (top_left[0] + bottom_right[0]) // 2
                    center_y = (top_left[1] + bottom_right[1]) // 2
                    text_x = center_x - text_width // 2
                    text_y = center_y + text_height // 2

                    cv2.rectangle(image, top_left, bottom_right, (255,255,255), -1)
                    cv2.rectangle(image, top_left, bottom_right, (0,0,0), T2)
                    cv2.putText(image, text, (text_x, text_y), font, T1, text_color, T2)

                    # Escribir en CSV
                    writer.writerow([ts, text, DCD_ang, DRD_ang, DTOD_ang, 
                                    DCI_ang, DRI_ang, DTOI_ang])

              except Exception as e:
                  print(f"Error: {e}")

            out.write(image)

# Liberar recursos
cap.release()
out.release()
cv2.destroyAllWindows()
print("Video procesado exitosamente.")