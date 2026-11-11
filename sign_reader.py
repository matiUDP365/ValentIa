"""Adaptador web para el lector de señas entregado por el equipo.

La cámara y los archivos binarios se abren solo cuando un operador inicia el
lector. El proceso original usa una ventana OpenCV; aquí los fotogramas y la
frase se entregan a Flask para mostrarlos en el panel.
"""

from __future__ import annotations

import io
import os
import queue
import threading
import time
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "assets" / "sign_reader" / "modelo_random_forest.pkl"
LANDMARKER_PATH = ROOT / "assets" / "sign_reader" / "hand_landmarker.task"
AUDIO_PATH = ROOT / "assets" / "audios"

CONFIDENCE_THRESHOLD = 0.85
LETTER_HOLD_SECONDS = 2.0
WORD_PAUSE_SECONDS = 2.0
SENTENCE_PAUSE_SECONDS = 5.0
LOSS_TOLERANCE_SECONDS = 0.4
LETTER_PAUSE_MS = 40
WORD_PAUSE_MS = 150
SEPARATOR = "|"


def _key(text: str) -> str:
    normalized = text.strip().upper().replace("Ñ", "\x00")
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", normalized)
        if not unicodedata.combining(char)
    )
    return normalized.replace("\x00", "Ñ")


def _words(elements: list[str]) -> list[str]:
    words: list[str] = []
    letters = ""
    for element in elements:
        if element == SEPARATOR:
            if letters:
                words.append(letters)
                letters = ""
        elif len(element) > 1:
            if letters:
                words.append(letters)
                letters = ""
            words.append(element)
        else:
            letters += element
    if letters:
        words.append(letters)
    return words


def _format(elements: list[str]) -> str:
    parts: list[str] = []
    letters = ""
    for element in elements:
        if element == SEPARATOR:
            if letters:
                parts.append(letters)
                letters = ""
        elif len(element) > 1:
            if letters:
                parts.append(letters)
                letters = ""
            parts.append(f"[{element}]")
        else:
            letters += element
    if letters:
        parts.append(letters)
    return " ".join(parts)


class SignReader:
    """One camera/model worker shared by the authenticated dashboard."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._audio_queue: queue.Queue[list[str]] = queue.Queue()
        self._audio_thread: threading.Thread | None = None
        self._frame: bytes | None = None
        self._elements: list[str] = []
        self._phrase = ""
        self._state = "stopped"
        self._model_ready = False
        self._camera_ready = False
        self._audio_ready = False
        self._sign = ""
        self._confidence = 0.0
        self._last_updated: float | None = None
        self._error = ""

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "running": self._state in {"starting", "running", "stopping"},
                "model_ready": self._model_ready,
                "camera_ready": self._camera_ready,
                "audio_ready": self._audio_ready,
                "sign": self._sign,
                "confidence": round(self._confidence * 100),
                "phrase": self._phrase,
                "last_updated": self._last_updated,
                "error": self._error,
            }

    def current_frame(self) -> bytes | None:
        with self._lock:
            return self._frame

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._state = "starting"
            self._model_ready = False
            self._camera_ready = False
            self._audio_ready = False
            self._sign = ""
            self._confidence = 0.0
            self._error = ""
            self._frame = None
            self._elements = []
            self._phrase = ""
            self._thread = threading.Thread(target=self._run, name="sign-reader", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            if self._state in {"starting", "running"}:
                self._state = "stopping"

    def clear(self) -> None:
        with self._lock:
            self._elements = []
            self._phrase = ""
            self._sign = ""
            self._confidence = 0.0

    def undo(self) -> None:
        with self._lock:
            if self._elements:
                self._elements.pop()
            self._phrase = _format(self._elements)

    def new_word(self) -> None:
        with self._lock:
            if self._elements and self._elements[-1] != SEPARATOR:
                self._elements.append(SEPARATOR)
                self._phrase = _format(self._elements)

    def speak(self) -> bool:
        with self._lock:
            elements = list(self._elements)
            while elements and elements[-1] == SEPARATOR:
                elements.pop()
        if not elements or not self.status()["audio_ready"]:
            return False
        self._audio_queue.put(elements)
        return True

    def _set_error(self, message: str, error: Exception | None = None) -> None:
        if error:
            print(f"[LECTOR] {message}: {error}")
        with self._lock:
            self._state = "error"
            self._error = message

    def _load_audio(self):
        try:
            import pygame
            from pydub import AudioSegment
            from pydub.effects import normalize
            from pydub.silence import detect_leading_silence

            pygame.mixer.init()
            clips = {}
            if AUDIO_PATH.is_dir():
                for path in AUDIO_PATH.iterdir():
                    if path.suffix.lower() != ".mp3":
                        continue
                    segment = AudioSegment.from_file(path)
                    leading = detect_leading_silence(segment, silence_threshold=-50.0)
                    trailing = detect_leading_silence(segment.reverse(), silence_threshold=-50.0)
                    cropped = segment[leading:len(segment) - trailing]
                    clips[_key(path.stem)] = normalize(cropped if len(cropped) else segment)

            with self._lock:
                self._audio_ready = bool(clips)
            if clips and (not self._audio_thread or not self._audio_thread.is_alive()):
                self._audio_thread = threading.Thread(
                    target=self._audio_worker,
                    args=(clips, AudioSegment, pygame),
                    name="sign-reader-audio",
                    daemon=True,
                )
                self._audio_thread.start()
            return clips, AudioSegment, pygame
        except Exception as error:
            print(f"[LECTOR] Audio no disponible: {error}")
            with self._lock:
                self._audio_ready = False
            return {}, None, None

    def _audio_worker(self, clips, AudioSegment, pygame) -> None:
        while True:
            elements = self._audio_queue.get()
            try:
                composed = AudioSegment.empty()
                for word in _words(elements):
                    key = _key(word)
                    clip = clips.get(key)
                    if clip is None:
                        # Keep the reader's fallback: spell unknown words when
                        # the matching letter recordings are available.
                        spelled = [clips.get(letter) for letter in word]
                        spelled = [part for part in spelled if part is not None]
                        if not spelled:
                            continue
                        clip = AudioSegment.empty()
                        for part in spelled:
                            if len(clip):
                                clip += AudioSegment.silent(duration=LETTER_PAUSE_MS)
                            clip += part
                    if len(composed):
                        composed += AudioSegment.silent(duration=WORD_PAUSE_MS)
                    composed += clip

                if len(composed):
                    buffer = io.BytesIO()
                    composed.export(buffer, format="wav")
                    buffer.seek(0)
                    channel = pygame.mixer.Sound(file=buffer).play()
                    while channel is not None and channel.get_busy():
                        time.sleep(0.05)
            except Exception as error:
                print(f"[LECTOR] No se pudo reproducir el audio: {error}")
            finally:
                self._audio_queue.task_done()

    def _run(self) -> None:
        camera = None
        detector = None
        try:
            import cv2
            import joblib
            import mediapipe as mp
            import numpy as np
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            if not MODEL_PATH.is_file() or not LANDMARKER_PATH.is_file():
                self._set_error("Faltan los archivos del modelo o del detector de manos.")
                return

            model = joblib.load(MODEL_PATH)
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(LANDMARKER_PATH)),
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            detector = vision.HandLandmarker.create_from_options(options)
            with self._lock:
                self._model_ready = True

            self._load_audio()
            camera_index = int(os.environ.get("SIGN_READER_CAMERA_INDEX", "0"))
            camera = cv2.VideoCapture(camera_index)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not camera.isOpened():
                self._set_error("No se pudo abrir la cámara del equipo que ejecuta Flask.")
                return

            with self._lock:
                self._camera_ready = True
                self._state = "running"

            stable_sign = ""
            stable_since = 0.0
            last_detection = time.time()
            last_no_hand_transition = 0.0

            while not self._stop_event.is_set():
                success, frame = camera.read()
                if not success:
                    self._set_error("La cámara dejó de entregar imagen.")
                    break

                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = detector.detect(image)
                now = time.time()
                accepted = []

                for landmarks in result.hand_landmarks:
                    for landmark in landmarks:
                        cv2.circle(
                            frame,
                            (int(landmark.x * width), int(landmark.y * height)),
                            4,
                            (0, 210, 150),
                            -1,
                        )
                    raw = np.array([[point.x, point.y, point.z] for point in landmarks])
                    normalized = (raw - raw[0]).flatten().reshape(1, -1)
                    prediction = str(model.predict(normalized)[0]).strip().upper()
                    confidence = float(np.max(model.predict_proba(normalized)))
                    wrist_x = int(landmarks[0].x * width)
                    wrist_y = int(landmarks[0].y * height)
                    if confidence > CONFIDENCE_THRESHOLD:
                        accepted.append((prediction, confidence, wrist_x, wrist_y))
                    else:
                        cv2.putText(frame, "Analizando...", (wrist_x - 30, wrist_y - 20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

                best = max(accepted, key=lambda item: item[1]) if accepted else None
                if best:
                    sign, confidence, wrist_x, wrist_y = best
                    last_detection = now
                    if sign != stable_sign:
                        stable_sign = sign
                        stable_since = now
                    progress = min(100, int((now - stable_since) / LETTER_HOLD_SECONDS * 100))
                    cv2.putText(frame, f"{sign} ({progress}%)", (wrist_x - 30, wrist_y - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 210, 150), 2)
                    with self._lock:
                        self._sign = sign
                        self._confidence = confidence
                        if now - stable_since >= LETTER_HOLD_SECONDS:
                            self._elements.append(sign)
                            self._phrase = _format(self._elements)
                            stable_since = now
                elif now - last_detection > LOSS_TOLERANCE_SECONDS:
                    stable_sign = ""
                    with self._lock:
                        self._sign = ""
                        self._confidence = 0.0

                silence = now - last_detection
                if silence > WORD_PAUSE_SECONDS:
                    with self._lock:
                        if self._elements and self._elements[-1] != SEPARATOR:
                            self._elements.append(SEPARATOR)
                            self._phrase = _format(self._elements)
                            last_no_hand_transition = now

                if silence > SENTENCE_PAUSE_SECONDS:
                    with self._lock:
                        sentence = list(self._elements)
                        while sentence and sentence[-1] == SEPARATOR:
                            sentence.pop()
                        if sentence:
                            self._phrase = _format(sentence)
                            self._audio_queue.put(sentence)
                            self._elements = []
                            last_detection = now
                            last_no_hand_transition = now

                with self._lock:
                    phrase = self._phrase
                preview = phrase[-40:] if phrase else "Esperando una seña"
                cv2.putText(frame, f"Texto: {preview}", (18, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 245, 100), 2)
                if last_no_hand_transition and now - last_no_hand_transition < 3:
                    cv2.putText(frame, "Pausa detectada", (18, 64),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 220, 255), 1)

                encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                if encoded:
                    with self._lock:
                        self._frame = buffer.tobytes()
                        self._last_updated = now

        except Exception as error:
            self._set_error("No se pudo iniciar el lector. Revisa sus dependencias y los archivos del modelo.", error)
        finally:
            if camera is not None:
                camera.release()
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    pass
            with self._lock:
                self._camera_ready = False
                if self._state != "error":
                    self._state = "stopped"


reader = SignReader()
