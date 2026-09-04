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
    # NOTA: estos valores estan ajustados +18 respecto al hue "percibido"
    # deseado, para compensar el subvalor sistematico que mide el blend en
    # LAB (probado empiricamente solo para "green": pedir 60 da un
    # resultado final de ~40, un verde oliva natural). El resto de los
    # colores se ajusto con el mismo offset por consistencia, pero solo
    # "green" fue verificado con el test numerico real -- si algun otro
    # color sale desviado, puede necesitar su propio ajuste puntual.
    "green": 68,
    "hazel": 46,
    "amber": 36,
    "blue": 120,
    "gray": 105,
    "grey": 95,
    "brown": 28,
    "black": 10,
}


_HUE_MODIFIERS = [
    ("emerald", 10), ("teal", 12), ("sea green", 12),
    ("olive", -15), ("forest", -8), ("moss", -12),
    ("gray-green", -5), ("grey-green", -5), ("sage", -6),
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
        (hue_final, target_saturation) -- ambos ya listos para usar en
        _recolor_iris_region. target_saturation es un nivel ABSOLUTO
        (no un empuje aditivo) hacia el que se mezcla el iris completo,
        para lograr un color parejo y bien formado en toda la zona
        recoloreada.
    """
    lowered = raw_value.lower()
    hue = base_hue
    for keyword, offset in _HUE_MODIFIERS:
        if keyword in lowered:
            hue += offset
            break  # solo el primer matiz que coincida, para no acumular varios
    hue = int(np.clip(hue, 0, 179))

    # Nivel de saturacion objetivo base: un verde/azul/etc. natural pero
    # con presencia real (no lavado). Los modificadores de intensidad
    # empujan este nivel hacia arriba (vivid/bright) o abajo (muted/pale).
    target_saturation = 45
    for keyword, offset in _INTENSITY_MODIFIERS:
        if keyword in lowered:
            target_saturation += offset * 6  # escalado: offset original pensado para un empuje chico, ahora mueve un objetivo absoluto
            break
    target_saturation = int(np.clip(target_saturation, 70, 200))

    return hue, target_saturation

# Indices de landmarks del iris en el modelo de mediapipe (478 puntos,
# incluye refinamiento de iris). Cada iris tiene 5 puntos: el centro y
# 4 en el borde.
_LEFT_IRIS_IDX = [474, 475, 476, 477]
_RIGHT_IRIS_IDX = [469, 470, 471, 472]


def extract_primary_color_name(raw_value: str) -> str:
    """
    Extrae una palabra de color conocida de una descripcion larga, en
    ingles O ESPAÑOL. Usa la palabra que aparece MAS TEMPRANO en el texto
    (no un orden de prioridad fijo), porque quien carga el CSV suele poner
    el color principal primero y las palabras descriptivas despues --
    ej. "dark gray-green hazel eyes" -> el color principal es "green"
    (aparece antes que "hazel" en el texto), no al reves.
    """
    if not raw_value:
        logger.warning("[EYE_COLOR] raw_value vacio/None -- usando 'brown' por defecto.")
        return "brown"
    lowered = raw_value.lower()

    # PASO 1: compuestos con guion primero. "gray-green" significa "verde
    # con tono gris" -- el color real es green, no gray. Si se buscara
    # "gray" como palabra suelta matchearia antes por posicion en el texto
    # y daria el color equivocado (bug real encontrado: "dark gray-green
    # hazel eyes" resolvia a "gray" en vez de "green").
    compound_overrides = {
        "gray-green": "green", "grey-green": "green",
        "blue-green": "green", "green-blue": "green",
        "gray-blue": "blue", "grey-blue": "blue",
        "hazel-green": "hazel", "green-hazel": "hazel",
    }
    for compound, mapped in compound_overrides.items():
        if compound in lowered:
            return mapped

    # PASO 2: mapa de equivalentes en espanol -> clave interna en ingles.
    spanish_map = {
        "avellana": "hazel", "ambar": "amber", "verde": "green",
        "azul": "blue", "gris": "gray", "cafe": "brown",
        "marron": "brown", "castano": "brown", "castaño": "brown",
        "negro": "black",
    }
    all_keywords = list(spanish_map.items()) + [
        (k, k) for k in ["hazel", "amber", "green", "blue", "gray", "grey", "brown", "black"]
    ]

    # PASO 3: entre las palabras sueltas restantes, la que aparece MAS
    # TEMPRANO en el texto (asumiendo que el color principal se escribe
    # primero, y las palabras descriptivas despues).
    best_match = None
    best_index = len(lowered) + 1
    for word, en_key in all_keywords:
        idx = lowered.find(word)
        if idx != -1 and idx < best_index:
            best_index = idx
            best_match = en_key

    if best_match is not None:
        return best_match

    # Si llegamos aca, no se reconocio NINGUNA palabra de color conocida
    # (ni en ingles ni en espanol). Antes esto caia a "brown" en total
    # silencio -- ahora se deja constancia clara en el log, porque es
    # la causa mas probable de que la correccion "no haga nada visible":
    # el valor del CSV puede tener un formato inesperado (typo, otro
    # idioma, emoji, etc.) que nadie detecto hasta ahora.
    logger.warning(
        f"[EYE_COLOR] No se reconocio ningun color en '{raw_value}' "
        f"(ni ingles ni espanol) -- usando 'brown' por defecto. "
        f"Revisar el formato real del dato en el CSV."
    )
    return "brown"  # fallback seguro si no se reconoce ningun color


def _iris_center_and_radius(landmarks, idx_list, img_w: int, img_h: int) -> Tuple[Tuple[int, int], int]:
    """Calcula el centro y radio aproximado de un iris a partir de sus landmarks."""
    points = np.array([
        (landmarks[i].x * img_w, landmarks[i].y * img_h) for i in idx_list
    ])
    center = points.mean(axis=0)
    radius = np.max(np.linalg.norm(points - center, axis=1))
    # FIX: se vio en produccion que el circulo, tal cual salia del calculo,
    # llegaba a teñir hasta la esclerotica (blanco del ojo) en fotos de
    # alta resolucion -- el radio derivado de los landmarks resulto ser
    # mas grande que el iris real (por imprecision del modelo, angulo del
    # ojo, parpadeo parcial, etc.). Se aplica un margen de seguridad del
    # 20% hacia adentro para que el circulo quede firmemente DENTRO del
    # iris, nunca tocando el blanco del ojo.
    radius = radius * 0.75
    return (int(center[0]), int(center[1])), int(radius) + 1


def _recolor_iris_region(
    image_bgr: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    target_a: float,
    target_b: float,
    opacity: float = 0.65,
) -> np.ndarray:
    """
    Recolorea el iris trabajando en espacio LAB, modificando SOLO los
    canales cromaticos (a, b) y dejando L (luminancia/textura) intacto.
    Esto preserva el patron de fibra y sombreado natural del iris en vez
    de aplastarlo con un relleno de tono plano.

    Incluye un anillo interior protegido (sin recolorear) para simular
    la heterocromia central natural (centro avellana/miel con borde
    verde) que tienen muchos ojos verdes/hazel reales.

    A diferencia de versiones anteriores, esta funcion recibe target_a/
    target_b YA CALCULADOS (en el espacio cromatico LAB), en vez de un
    hue/saturacion en HSV -- asi el mismo blend sirve tanto para un color
    aproximado por texto como para un color MUESTREADO de una foto real
    de referencia, sin tablas de compensacion. `opacity` es mas alta
    cuando el color viene de una foto real (confiable, empujar fuerte) y
    mas baja cuando es una aproximacion por texto (menos confiable,
    dejar que se note menos para no arriesgar un color equivocado).
    """
    h, w = image_bgr.shape[:2]

    # Mascara circular con anillo interior protegido (heterocromia central).
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.circle(mask, center, radius, 1.0, thickness=-1)
    inner_radius = max(1, int(radius * 0.35))
    cv2.circle(mask, center, inner_radius, 0.0, thickness=-1)

    # Desenfoque de borde contenido, con tope absoluto en pixeles para que
    # no escale sin control en imagenes de alta resolucion (portrait sale
    # a ~2048px) -- esto fue lo que causaba el sangrado hacia el parpado
    # y la esclerotica en versiones anteriores.
    sigma = min(radius * 0.15, 3.5)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma)

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_channel, a_channel, b_channel = lab[..., 0], lab[..., 1], lab[..., 2]

    # No tocar reflejos de luz (catchlight) ni sombra muy profunda.
    valid_range = ((l_channel > 30) & (l_channel < 220)).astype(np.float32)
    effective_mask = mask * valid_range * opacity

    new_a = a_channel * (1.0 - effective_mask) + target_a * effective_mask
    new_b = b_channel * (1.0 - effective_mask) + target_b * effective_mask

    lab[..., 1] = new_a
    lab[..., 2] = new_b
    # L (luminancia/textura) queda exactamente igual al original -- por
    # eso se conserva el patron de fibra natural del iris.

    result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result


def _sample_iris_lab_ab(image_bgr: np.ndarray, center: Tuple[int, int], radius: int) -> Optional[Tuple[float, float]]:
    """
    Promedia el color (canales a, b de LAB) del anillo del iris en una
    imagen -- usado para MUESTREAR el color real del ojo de una foto de
    referencia de la donante, en vez de adivinarlo por una tabla de texto.
    Excluye el centro (heterocromia/pupila) y los reflejos de luz, igual
    que al recolorear.
    """
    h, w = image_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, center, radius, 255, thickness=-1)
    inner_radius = max(1, int(radius * 0.35))
    cv2.circle(mask, center, inner_radius, 0, thickness=-1)

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[..., 0]
    valid = (mask > 0) & (l_channel > 30) & (l_channel < 220)

    if not np.any(valid):
        return None

    avg_a = float(lab[..., 1][valid].mean())
    avg_b = float(lab[..., 2][valid].mean())
    return avg_a, avg_b


def sample_target_color_from_reference(
    reference_image_bytes: bytes,
    model_path: str = "/runpod-volume/models/mediapipe/face_landmarker.task",
) -> Optional[Tuple[float, float]]:
    """
    Detecta la cara en una foto de referencia REAL de la donante y
    muestrea el color promedio de sus dos iris (en LAB a/b). Este color
    se usa despues como objetivo exacto al recolorear las imagenes
    generadas, en vez de aproximar por un nombre de color en texto.

    Returns:
        (avg_a, avg_b) promediado entre ambos ojos, o None si no se pudo
        detectar cara o muestrear color (en ese caso, el llamador debe
        caer al metodo de texto como respaldo).
    """
    try:
        landmarker = _get_landmarker(model_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None

    arr = np.frombuffer(reference_image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        logger.warning("[EYE_COLOR] No se pudo decodificar la foto de referencia.")
        return None
    img_h, img_w = image_bgr.shape[:2]

    detection_image = _resize_for_detection(image_bgr)
    image_rgb = cv2.cvtColor(detection_image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

    result = _detect_with_timeout(landmarker, mp_image, timeout_seconds=25.0)
    if result is None or not result.face_landmarks:
        logger.warning("[EYE_COLOR] No se detecto cara en la foto de referencia -- no se pudo muestrear color real.")
        return None

    landmarks = result.face_landmarks[0]
    left_center, left_radius = _iris_center_and_radius(landmarks, _LEFT_IRIS_IDX, img_w, img_h)
    right_center, right_radius = _iris_center_and_radius(landmarks, _RIGHT_IRIS_IDX, img_w, img_h)

    left_sample = _sample_iris_lab_ab(image_bgr, left_center, left_radius)
    right_sample = _sample_iris_lab_ab(image_bgr, right_center, right_radius)

    samples = [s for s in (left_sample, right_sample) if s is not None]
    if not samples:
        logger.warning("[EYE_COLOR] No se pudo muestrear color de ningun ojo en la foto de referencia.")
        return None

    avg_a = sum(s[0] for s in samples) / len(samples)
    avg_b = sum(s[1] for s in samples) / len(samples)
    logger.info(f"[EYE_COLOR] Color real muestreado de la referencia: a={avg_a:.1f}, b={avg_b:.1f} (de {len(samples)} ojo/s)")
    return avg_a, avg_b


def correct_eye_color(
    image_bytes: bytes,
    target_color: str,
    model_path: str = "/runpod-volume/models/mediapipe/face_landmarker.task",
    reference_image_bytes: Optional[bytes] = None,
) -> Optional[bytes]:
    """
    Corrige el color de ojos de una imagen generada.

    Si se pasa `reference_image_bytes` (una foto REAL de la donante), se
    intenta muestrear su color de ojos exacto y usarlo como objetivo,
    con un blend fuerte (0.90) porque el color es confiable. Si no hay
    foto de referencia, o no se pudo muestrear (no se detecto cara en
    ella, etc.), se cae al metodo anterior: aproximar el color por el
    texto de la columna del CSV, con un blend mas suave (0.65) porque
    es una aproximacion, no el color real.
    """
    target_a = target_b = None
    opacity = 0.65

    if reference_image_bytes:
        sampled = sample_target_color_from_reference(reference_image_bytes, model_path)
        if sampled is not None:
            target_a, target_b = sampled
            opacity = 0.90
            logger.info(f"[EYE_COLOR] Usando color REAL muestreado de la referencia (a={target_a:.1f}, b={target_b:.1f}, opacity={opacity})")
        else:
            logger.warning("[EYE_COLOR] No se pudo muestrear la foto de referencia -- se cae al metodo de texto como respaldo.")

    if target_a is None:
        # --- Metodo de respaldo: aproximar por texto ---
        color_name = extract_primary_color_name(target_color)
        logger.info(f"[EYE_COLOR] target_color recibido={target_color!r} -> color_name resuelto={color_name!r}")
        base_hue = _COLOR_HUE_MAP.get(color_name)
        if base_hue is None:
            logger.error(f"[EYE_COLOR] color_name '{color_name}' no tiene hue asociado en _COLOR_HUE_MAP -- se omite correccion.")
            return None

        target_hue, target_saturation = _compute_hue_and_intensity(target_color, base_hue)
        target_bgr = cv2.cvtColor(np.uint8([[[target_hue, target_saturation, 160]]]), cv2.COLOR_HSV2BGR)
        target_lab = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)[0][0]
        target_a, target_b = target_lab[1], target_lab[2]
        logger.info(f"[EYE_COLOR] Usando color aproximado por texto (a={target_a:.1f}, b={target_b:.1f}, opacity={opacity})")

    # Decodificar imagen a corregir
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
    if result is None:
        # _detect_with_timeout ya logueo el motivo especifico (timeout o excepcion).
        return None
    if not result.face_landmarks:
        logger.warning(
            f"[EYE_COLOR] No se detecto ninguna cara en la imagen "
            f"(tamaño usado para deteccion: {detection_image.shape[1]}x{detection_image.shape[0]}, "
            f"original: {img_w}x{img_h}). Se omite correccion, se mantiene original."
        )
        return None

    landmarks = result.face_landmarks[0]

    left_center, left_radius = _iris_center_and_radius(landmarks, _LEFT_IRIS_IDX, img_w, img_h)
    right_center, right_radius = _iris_center_and_radius(landmarks, _RIGHT_IRIS_IDX, img_w, img_h)

    corrected = _recolor_iris_region(image_bgr, left_center, left_radius, target_a, target_b, opacity=opacity)
    corrected = _recolor_iris_region(corrected, right_center, right_radius, target_a, target_b, opacity=opacity)

    success, encoded = cv2.imencode(".png", corrected)
    if not success:
        return None
    return encoded.tobytes()
