"""
Correccion deterministica de color de ojos (post-procesamiento).

A diferencia de ajustar pesos en el prompt (que solo aumenta la
*probabilidad* de que el modelo genere el color pedido), este script
edita directamente los pixeles del iris DESPUES de que la imagen ya fue
generada -- por lo tanto GARANTIZA el color, sin depender de que el
modelo "obedezca" el texto.

Requiere:
    pip install mediapipe opencv-python-headless --break-system-packages

Requiere ademas descargar UNA VEZ el modelo de deteccion facial de
mediapipe (unos pocos MB), colocarlo en la ruta indicada en
FACE_LANDMARKER_MODEL_PATH. El contenedor de RunPod si tiene salida a
internet para hacer esta descarga (a diferencia del sandbox donde se
escribio este script, que tiene la red restringida):

    wget -O face_landmarker.task \\
      https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

Uso basico:
    from eye_color_correction import correct_eye_color

    corrected_bytes = correct_eye_color(
        image_bytes=original_png_bytes,
        target_color="green",       # o el valor crudo del Excel, se
                                     # interpreta con extract_primary_eye_color
        model_path="/app/models/face_landmarker.task",
    )
    # corrected_bytes ya tiene los ojos con el color correcto, listo
    # para subir a B2 en vez de la imagen original.

Donde integrarlo: el punto natural es justo antes de subir las imagenes
a B2 (en handler.py, en la funcion que sube los resultados), aplicando
esta correccion solo si el donante tiene un color de ojos "no cafe"
(para no tocar innecesariamente a la mayoria de donantes, que si suelen
salir bien con cafe/negro por ser el sesgo natural del modelo).
"""

import io
import re
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
) -> np.ndarray:
    """
    Cambia el tono (hue) de los pixeles dentro de un circulo suave
    (mascara con borde difuminado), preservando brillo y evitando
    tocar el reflejo de luz (catchlight, muy brillante) y la pupila
    (muy oscura) para que el resultado se vea natural.
    """
    h, w = image_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.circle(mask, center, radius, 1.0, thickness=-1)
    # Difuminar el borde de la mascara para una transicion suave, sin
    # borde duro (que es lo que causaba las "manchas" en el enfoque de
    # prompt).
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=radius * 0.25)

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    # No tocar pupila (muy oscura) ni catchlight (muy brillante) --
    # solo el anillo del iris que tiene brillo intermedio.
    brightness_ok = (val > 25) & (val < 220)
    effective_mask = mask * brightness_ok.astype(np.float32)

    new_hue = hue.copy()
    new_hue = hue * (1 - effective_mask) + target_hue * effective_mask

    hsv[..., 0] = new_hue
    # Empujar levemente la saturacion hacia arriba solo donde se aplico
    # el cambio, para que el color nuevo se note (no solo el matiz).
    hsv[..., 1] = np.clip(sat + effective_mask * 40, 0, 255)

    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return result


def correct_eye_color(
    image_bytes: bytes,
    target_color: str,
    model_path: str = "/app/models/face_landmarker.task",
) -> Optional[bytes]:
    """
    Corrige el color de ambos ojos en una imagen ya generada.

    Args:
        image_bytes: bytes de la imagen generada (PNG/JPEG).
        target_color: color deseado, puede ser una palabra simple
            ("green") o una descripcion larga del Excel (se extrae la
            palabra clave automaticamente).
        model_path: ruta al archivo .task de mediapipe (descargar una
            vez, ver docstring del modulo).

    Returns:
        Los bytes de la imagen corregida (PNG), o None si no se detecto
        ninguna cara (en ese caso, usar la imagen original sin tocar).
    """
    color_name = extract_primary_color_name(target_color)
    target_hue = _COLOR_HUE_MAP.get(color_name)
    if target_hue is None:
        # Color no reconocido: no se puede mapear a un tono, se
        # devuelve None para que el llamador use la imagen original.
        return None

    # Decodificar imagen
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        return None
    img_h, img_w = image_bgr.shape[:2]

    # Detectar landmarks faciales (incluye iris)
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.IMAGE,
        num_faces=1,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=False,
    )
    with FaceLandmarker.create_from_options(options) as landmarker:
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        result = landmarker.detect(mp_image)

    if not result.face_landmarks:
        return None  # no se detecto cara -- devolver None, usar original

    landmarks = result.face_landmarks[0]

    left_center, left_radius = _iris_center_and_radius(landmarks, _LEFT_IRIS_IDX, img_w, img_h)
    right_center, right_radius = _iris_center_and_radius(landmarks, _RIGHT_IRIS_IDX, img_w, img_h)

    corrected = _recolor_iris_region(image_bgr, left_center, left_radius, target_hue)
    corrected = _recolor_iris_region(corrected, right_center, right_radius, target_hue)

    success, encoded = cv2.imencode(".png", corrected)
    if not success:
        return None
    return encoded.tobytes()
