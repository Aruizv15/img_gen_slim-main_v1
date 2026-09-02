import io
import re
import os
import logging
import threading
from typing import Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

logger = logging.getLogger(__name__)

# --- FIX #1: cachear el FaceLandmarker en vez de recrearlo en cada llamada ---
# Antes, "with FaceLandmarker.create_from_options(options) as landmarker:"
# corria DENTRO de correct_eye_color(), asi que cada foto volvia a leer el
# .task de disco y reinicializar el interprete TFLite desde cero. Esa carga
# es la parte mas cara de todo el proceso. En un batch de varias fotos, ese
# costo se multiplica por cada una -- la causa mas probable del cuelgue de
# 10+ minutos en produccion. Ahora el modelo se carga UNA sola vez por
# proceso y se reutiliza.
_landmarker_lock = threading.Lock()
_landmarker_cache: dict = {}


def _get_landmarker(model_path: str) -> FaceLandmarker:
    if model_path in _landmarker_cache:
        return _landmarker_cache[model_path]
    with _landmarker_lock:
        if model_path not in _landmarker_cache:
            if not os.path.exists(model_path):
                # Fallar rapido y con mensaje claro, en vez de dejar que
                # mediapipe intente cargar algo inexistente y se quede
                # esperando/reintentando en silencio.
                raise FileNotFoundError(
                    f"[EYE_COLOR] Modelo de landmarks no encontrado en {model_path}. "
                    f"Verificar que face_landmarker.task este presente en esa ruta."
                )
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=model_path),
                running_mode=RunningMode.IMAGE,
                num_faces=1,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            _landmarker_cache[model_path] = FaceLandmarker.create_from_options(options)
            logger.info(f"[EYE_COLOR] Modelo de landmarks cargado y cacheado desde {model_path}")
    return _landmarker_cache[model_path]


# --- FIX #2: detectar landmarks sobre una copia reducida ---
# Los landmarks de mediapipe son coordenadas NORMALIZADAS (0-1), no pixeles
# absolutos -- asi que detectar sobre una copia chica da el mismo resultado
# relativo que detectar sobre la imagen completa, pero mucho mas rapido.
# Esto importa mas ahora que las fullbody finales salen a ~2048px (fix de
# nitidez reciente) en vez de ~1024px.
_DETECTION_MAX_DIM = 640


def _resize_for_detection(image_bgr: np.ndarray) -> np.ndarray:
    h, w = image_bgr.shape[:2]
    scale = _DETECTION_MAX_DIM / max(h, w)
    if scale >= 1.0:
        return image_bgr
    return cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


# --- FIX #3: timeout duro sobre la deteccion ---
# landmarker.detect() es una llamada sincronica/bloqueante en C++. Si algo
# interno se traba (contencion de CPU con ComfyUI, inicializacion rara del
# delegate, etc.), esto garantiza que NUNCA vuelva a colgar el proceso
# 10+ minutos: pasado el timeout se abandona esa foto puntual (se sigue
# usando la imagen sin corregir) en vez de tumbar el job entero.
def _detect_with_timeout(landmarker: FaceLandmarker, mp_image: "mp.Image", timeout_seconds: float = 25.0):
    result_holder: dict = {}

    def _run():
        try:
            result_holder["result"] = landmarker.detect(mp_image)
        except Exception as e:
            result_holder["error"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_seconds)
    if t.is_alive():
        logger.error(f"[EYE_COLOR] Timeout de {timeout_seconds}s detectando landmarks. Se omite correccion para esta imagen.")
        return None
    if "error" in result_holder:
        logger.error(f"[EYE_COLOR] Error detectando landmarks: {result_holder['error']}")
        return None
    return result_holder.get("result")


# --- Mapeo de nombre de color a tono (Hue) en el espacio HSV de OpenCV (0-179) ---
_COLOR_HUE_MAP = {
    "green": 65,
    "hazel": 30,
    "amber": 20,
    "blue": 110,
    "gray": 95,
    "grey": 95,
    "brown": 12,
    "black": 10,
}


_HUE_MODIFIERS = [
    ("emerald", 10), ("teal", 12), ("sea green", 12),
    ("olive", -15), ("forest", -8), ("moss", -12),
    ("gray-green", -5), ("grey-green", -5), ("sage", -10),
    ("turquoise", 15), ("sky blue", 8), ("steel blue", 5),
    ("navy", -10), ("cobalt", -5),
    ("golden", -5), ("honey", -3),
]


_INTENSITY_MODIFIERS = [
    ("muted", -6), ("soft", -4), ("pale", -8), ("light", -4), ("dull", -6),
    ("vivid", 8), ("bright", 6), ("intense", 8), ("deep", 4), ("dark", 3),
]


def _compute_hue_and_intensity(raw_value: str, base_hue: int) -> Tuple[int, int]:
    """
    Ajusta el tono base segun palabras descriptivas presentes en la frase
    completa del Excel, para que distintos donantes del mismo color
    general (ej. "green") no salgan todos con el iris identico.

    Returns:
        (hue_final, saturation_boost) -- ambos ya listos para usar en
        _recolor_iris_region.
    """
    lowered = raw_value.lower()
    hue = base_hue
    for keyword, offset in _HUE_MODIFIERS:
        if keyword in lowered:
            hue += offset
            break  # solo el primer matiz que coincida, para no acumular varios
    hue = int(np.clip(hue, 0, 179))

    saturation_boost = 8  # valor base, mismo que antes del ajuste de matices
    for keyword, offset in _INTENSITY_MODIFIERS:
        if keyword in lowered:
            saturation_boost += offset
            break
    saturation_boost = int(np.clip(saturation_boost, 0, 25))

    return hue, saturation_boost

# Indices de landmarks del iris en el modelo de mediapipe (478 puntos,
# incluye refinamiento de iris). Cada iris tiene 5 puntos: el centro y
# 4 en el borde.
_LEFT_IRIS_IDX = [474, 475, 476, 477]
_RIGHT_IRIS_IDX = [469, 470, 471, 472]


def extract_primary_color_name(raw_value: str) -> str:
    """
    Extrae una palabra de color conocida de una descripcion larga
    (ej. "soft muted gray-green eyes, cool olive undertones" -> "green").
    Reutiliza la misma logica de eye_color_helper.py.
    """
    if not raw_value:
        return "brown"
    lowered = raw_value.lower()
    # Orden de prioridad: colores compuestos antes que sus componentes.
    for keyword in ["hazel", "amber", "green", "blue", "gray", "grey", "brown", "black"]:
        if keyword in lowered:
            return keyword
    return "brown"  # fallback seguro si no se reconoce ningun color


def _iris_center_and_radius(landmarks, idx_list, img_w: int, img_h: int) -> Tuple[Tuple[int, int], int]:
    """Calcula el centro y radio aproximado de un iris a partir de sus landmarks."""
    points = np.array([
        (landmarks[i].x * img_w, landmarks[i].y * img_h) for i in idx_list
    ])
    center = points.mean(axis=0)
    radius = np.max(np.linalg.norm(points - center, axis=1))
    return (int(center[0]), int(center[1])), int(radius) + 1


def _recolor_iris_region(
    image_bgr: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    target_hue: int,
    saturation_boost: int = 8,
) -> np.ndarray:

    h, w = image_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.circle(mask, center, radius, 1.0, thickness=-1)
    # Difuminar el borde de la mascara para una transicion suave, sin
    # borde duro (que es lo que causaba las "manchas" en el enfoque de
    # prompt).
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=radius * 0.25)
    # Limitar la opacidad maxima (no llegar a 1.0 puro) para que se
    # conserve algo de la textura/sombreado natural del iris original en
    # vez de un relleno de color completamente plano y "pintado".
    mask = mask * 0.82

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    # No tocar pupila (muy oscura) ni catchlight (muy brillante) --
    # solo el anillo del iris que tiene brillo intermedio.
    brightness_ok = (val > 25) & (val < 220)
    effective_mask = mask * brightness_ok.astype(np.float32)

    new_hue = hue.copy()
    new_hue = hue * (1 - effective_mask) + target_hue * effective_mask

    hsv[..., 0] = new_hue
    # Empuje de saturacion MUY leve -- el valor anterior (+40) dejaba un
    # verde plano y sobresaturado, muy distinto al tono natural y sutil
    # de un ojo real. +8 es suficiente para que el color se note sin
    # verse pintado.
    hsv[..., 1] = np.clip(sat + effective_mask * saturation_boost, 0, 255)

    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return result


def correct_eye_color(
    image_bytes: bytes,
    target_color: str,
    model_path: str = "/app/models/face_landmarker.task",
) -> Optional[bytes]:

    color_name = extract_primary_color_name(target_color)
    base_hue = _COLOR_HUE_MAP.get(color_name)
    if base_hue is None:
        return None

    target_hue, saturation_boost = _compute_hue_and_intensity(target_color, base_hue)

    # Decodificar imagen
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        return None
    img_h, img_w = image_bgr.shape[:2]

    try:
        landmarker = _get_landmarker(model_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None

    # Detectar sobre una copia reducida (FIX #2); el recoloreado final usa
    # SIEMPRE la imagen original a resolucion completa, sin perdida de calidad.
    detection_image = _resize_for_detection(image_bgr)
    image_rgb = cv2.cvtColor(detection_image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

    result = _detect_with_timeout(landmarker, mp_image, timeout_seconds=25.0)
    if result is None or not result.face_landmarks:
        return None  # no se detecto cara, hubo timeout, o hubo error -- devolver None, usar original

    landmarks = result.face_landmarks[0]

    left_center, left_radius = _iris_center_and_radius(landmarks, _LEFT_IRIS_IDX, img_w, img_h)
    right_center, right_radius = _iris_center_and_radius(landmarks, _RIGHT_IRIS_IDX, img_w, img_h)

    corrected = _recolor_iris_region(image_bgr, left_center, left_radius, target_hue, saturation_boost)
    corrected = _recolor_iris_region(corrected, right_center, right_radius, target_hue, saturation_boost)

    success, encoded = cv2.imencode(".png", corrected)
    if not success:
        return None
    return encoded.tobytes()
