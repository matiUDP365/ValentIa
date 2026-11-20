import cv2
import csv
import os
from send_sample import send_sample
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

model_path = './hand_landmarker.task'

options = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path=model_path),
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

detector = vision.HandLandmarker.create_from_options(options)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]

# --- CONFIGURACIÓN DE LA SEÑA ---
ETIQUETA_ACTUAL = os.environ.get("SIGN_LABEL", "GRACIAS").strip().upper()
REQUIERE_DOS_MANOS = os.environ.get("REQUIERE_DOS_MANOS", "1").strip().lower() not in ("0", "false", "no")
NOMBRE_ARCHIVO_CSV = os.environ.get("DATASET_CSV", "dataset_senias_2manos.csv")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 620)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("Error: No se pudo acceder a la cámara web.")
    exit()

print(f"\n=== CAPTURA DE DATASET | SEÑA: '{ETIQUETA_ACTUAL}' | 2 MANOS OBLIGATORIAS: {REQUIERE_DOS_MANOS} ===")
print(" - Presiona ' ' (BARRA ESPACIADORA) para guardar cuando ambas posiciones estén confirmadas.")
print(" - Presiona 'q' para salir.\n")

with open(NOMBRE_ARCHIVO_CSV, mode='a', newline='') as f:
    writer = csv.writer(f)
    muestras_guardadas = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        flip_frame = cv2.flip(frame, 1)
        h, w, _ = flip_frame.shape

        rgb_frame = cv2.cvtColor(flip_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        detection_result = detector.detect(mp_image)

        vector_izq = np.zeros(63, dtype=np.float32)
        vector_der = np.zeros(63, dtype=np.float32)
        izq_confirmada = False
        der_confirmada = False

        if detection_result.hand_landmarks:
            for idx, hand_landmarks in enumerate(detection_result.hand_landmarks):
                raw_landmarks = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks], dtype=np.float32)
                landmarks_norm = (raw_landmarks - raw_landmarks[0]).flatten()

                # Asignar cada mano a su bloque fijo sin sobrescribir
                lateralidad = detection_result.handedness[idx][0].category_name
                if lateralidad == "Left" and not izq_confirmada:
                    vector_izq = landmarks_norm
                    izq_confirmada = True
                    color_muneca = (255, 0, 0)   # Azul = Izquierda
                elif not der_confirmada:
                    vector_der = landmarks_norm
                    der_confirmada = True
                    color_muneca = (0, 0, 255)   # Rojo = Derecha[cite: 1]
                else:
                    vector_izq = landmarks_norm
                    izq_confirmada = True
                    color_muneca = (255, 0, 0)

                for start_idx, end_idx in HAND_CONNECTIONS:
                    p1 = hand_landmarks[start_idx]
                    p2 = hand_landmarks[end_idx]
                    cv2.line(flip_frame, (int(p1.x * w), int(p1.y * h)),
                             (int(p2.x * w), int(p2.y * h)), (200, 200, 200), 2)

                for lm in hand_landmarks:
                    cv2.circle(flip_frame, (int(lm.x * w), int(lm.y * h)), 4, (0, 255, 0), -1)

                wrist_x, wrist_y = int(hand_landmarks[0].x * w), int(hand_landmarks[0].y * h)
                cv2.circle(flip_frame, (wrist_x, wrist_y), 7, color_muneca, -1)

        vector_126 = np.concatenate([vector_izq, vector_der])

        # Indicadores visuales de confirmación de cada mano
        estado_izq = "IZQ: OK" if izq_confirmada else "IZQ: --"
        estado_der = "DER: OK" if der_confirmada else "DER: --"
        listo_para_guardar = (izq_confirmada and der_confirmada) if REQUIERE_DOS_MANOS else (izq_confirmada or der_confirmada)
        color_banner = (0, 255, 0) if listo_para_guardar else (0, 165, 255)

        cv2.putText(flip_frame, f"Senia: {ETIQUETA_ACTUAL} | {estado_izq} | {estado_der} | Guardadas: {muestras_guardadas}",
                    (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color_banner, 2)

        cv2.imshow("Generador Dataset 2 Manos (PC)", flip_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            if listo_para_guardar:
                writer.writerow([ETIQUETA_ACTUAL] + np.round(vector_126, 6).tolist())
                muestras_guardadas += 1
                f.flush()
                lateralidad = "Both" if (izq_confirmada and der_confirmada) else ("Left" if izq_confirmada else "Right")
                send_sample(vector_126.tolist(), ETIQUETA_ACTUAL, lateralidad)
                print(f"[OK] Muestra #{muestras_guardadas} guardada ({estado_izq}, {estado_der})")
            else:
                print(f"[BLOQUEADO] Faltan manos por confirmar ({estado_izq}, {estado_der}).")

        elif key == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
