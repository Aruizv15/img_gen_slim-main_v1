import io
import re
import os
import logging
import threading
from typing import Optional, Tuple, List

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
_DETECTION_MAX_DIM = 1024  # subido de 640: en fullbody (1024x1024) la cara ya ocupa poco espacio; reducirla mas hacia 640px hacia que mediapipe no la detectara en algunas fotos ("Corregidas 0/1" confirmado en logs de produccion)


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
    radius = radius * 0.88
    return (int(center[0]), int(center[1])), int(radius) + 1


def _recolor_iris_two_zones(
    image_bgr: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    inner_a: float,
    inner_b: float,
    inner_opacity: float,
    outer_a: float,
    outer_b: float,
    outer_opacity: float,
) -> np.ndarray:
    """
    Recolorea el iris en DOS zonas concentricas independientes, cada una
    con su propio color y opacidad -- reproduce heterocromia real
    (centro miel/ambar + anillo exterior verde) en vez de un solo tono
    plano para todo el iris. Trabaja en LAB, tocando solo los canales
    cromaticos (a, b) y dejando L (luminancia/textura) intacto, igual
    que la version de una sola zona.

    Zonas (como fraccion del radio, mismas que en el muestreo):
      - 0 a 0.30: pupila/reflejo, nunca se toca.
      - 0.30 a 0.60: zona interior (inner_a/inner_b).
      - 0.60 a 0.70: transicion, se deja mezclar naturalmente por el
        desenfoque de ambas mascaras.
      - 0.70 a 1.0: zona exterior (outer_a/outer_b).
    """
    h, w = image_bgr.shape[:2]
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_channel, a_channel, b_channel = lab[..., 0], lab[..., 1], lab[..., 2]
    # FIX: antes valid_range era un corte binario duro (> 30 y < 220), sin
    # suavizar -- aunque el circulo de color SI estaba difuminado, al
    # multiplicarlo por esta mascara binaria se reintroducia un borde
    # duro y dentado justo donde el brillo cruzaba el umbral (tipicamente
    # en la sombra del parpado superior). Ahora se suaviza tambien esta
    # mascara, para que la inclusion/exclusion por brillo sea gradual,
    # no un corte abrupto.
    valid_range = ((l_channel > 30) & (l_channel < 220)).astype(np.float32)
    valid_range = cv2.GaussianBlur(valid_range, (0, 0), sigmaX=2.0)

    sigma = min(radius * 0.12, 2.8)

    def _zone_mask(inner_frac, outer_frac, opacity):
        m = np.zeros((h, w), dtype=np.float32)
        outer_px = max(1, int(radius * outer_frac))
        inner_px = max(1, int(radius * inner_frac))
        cv2.circle(m, center, outer_px, 1.0, thickness=-1)
        if inner_px > 0:
            cv2.circle(m, center, inner_px, 0.0, thickness=-1)
        m = cv2.GaussianBlur(m, (0, 0), sigmaX=sigma)
        return m * valid_range * opacity

    inner_mask = _zone_mask(_INNER_ZONE[0], _INNER_ZONE[1], inner_opacity)
    outer_mask = _zone_mask(_OUTER_ZONE[0], _OUTER_ZONE[1], outer_opacity)

    # FIX: aplicar las mascaras en secuencia (primero centro, despues
    # anillo) hacia que en la zona de superposicion el anillo (verde)
    # pisara al centro (ambar), empujando mas verde hacia adentro de lo
    # que correspondia -- el color ya no coincidia con la referencia real.
    # Ahora se calcula un blend PROPORCIONAL, independiente del orden: en
    # la superposicion, se mezclan ambos colores segun su peso relativo,
    # en vez de que uno gane sobre el otro.
    total_weight = np.clip(inner_mask + outer_mask, 0.0, None)
    safe_weight = np.maximum(total_weight, 1e-6)
    combined_target_a = (inner_mask * inner_a + outer_mask * outer_a) / safe_weight
    combined_target_b = (inner_mask * inner_b + outer_mask * outer_b) / safe_weight
    combined_opacity = np.clip(total_weight, 0.0, 1.0)

    new_a = a_channel * (1.0 - combined_opacity) + combined_target_a * combined_opacity
    new_b = b_channel * (1.0 - combined_opacity) + combined_target_b * combined_opacity

    lab[..., 1] = new_a
    lab[..., 2] = new_b

    # Anillo limbico: una linea oscura fina justo en el borde exterior del
    # iris (contra la esclerotica), que es lo que le da al ojo la
    # sensacion de forma "redonda" bien definida en vez de difusa. Solo
    # oscurece L en una franja muy angosta (0.92 a 1.0 del radio), sin
    # tocar el color -- es sutil, no un borde negro duro.
    limbal_mask = np.zeros((h, w), dtype=np.float32)
    limbal_outer_px = max(1, int(radius * 1.0))
    limbal_inner_px = max(1, int(radius * 0.92))
    cv2.circle(limbal_mask, center, limbal_outer_px, 1.0, thickness=-1)
    cv2.circle(limbal_mask, center, limbal_inner_px, 0.0, thickness=-1)
    limbal_mask = cv2.GaussianBlur(limbal_mask, (0, 0), sigmaX=max(1.0, sigma * 0.5))
    limbal_mask = limbal_mask * valid_range * 0.5  # sutil, no un borde duro

    # FIX: se detecto en produccion que el verde salia "oscuro" -- no era
    # el tono (a/b) sino que la zona del ojo en la foto GENERADA ya venia
    # con brillo bajo (sombra de parpado, iluminacion de esa toma), y como
    # L nunca se tocaba, el color heredaba esa oscuridad. Se aplica un
    # realce PROPORCIONAL (no un valor plano) de brillo, PERO SOLO en la
    # zona exterior (verde) -- el centro (cafe/ambar) queda con su L
    # original, sin tocar, tal como se pidio explicitamente.
    _L_BOOST = 1.10
    _L_MIN_FLOOR = 78
    boosted_l = np.clip(l_channel * _L_BOOST, 0, 215)
    boosted_l = np.maximum(boosted_l, _L_MIN_FLOOR)
    # Solo outer_mask participa aca -- inner_mask NO se incluye, para que
    # el centro (cafe) quede exactamente como estaba.
    new_l = l_channel * (1.0 - outer_mask) + boosted_l * outer_mask

    # Aplicar el anillo limbico oscuro DESPUES del realce de brillo, para
    # que quede como un borde definido sobre el color ya corregido, no se
    # pierda mezclado con el resto del realce.
    darkened_limbal = np.clip(new_l * 0.55, 0, 255)
    new_l = new_l * (1.0 - limbal_mask) + darkened_limbal * limbal_mask

    lab[..., 0] = new_l
    # L (luminancia/textura) se preserva relativamente -- solo se realza,
    # nunca se aplana a un valor fijo.

    result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result


def _sample_iris_zone_lab_ab(
    image_bgr: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    inner_frac: float,
    outer_frac: float,
) -> Optional[Tuple[float, float]]:
    """
    Promedia el color (canales a, b de LAB) de una ZONA especifica del
    iris (un anillo entre inner_frac y outer_frac del radio total).
    Generaliza la version anterior para poder muestrear el centro
    (miel/ambar) y el borde exterior (verde) POR SEPARADO -- muchos ojos
    hazel/verdes tienen heterocromia real: centro de un color, anillo
    exterior de otro. Un solo promedio de todo el iris diluye ambos.
    """
    h, w = image_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    outer_radius_px = max(1, int(radius * outer_frac))
    inner_radius_px = max(1, int(radius * inner_frac))
    cv2.circle(mask, center, outer_radius_px, 255, thickness=-1)
    if inner_radius_px > 0:
        cv2.circle(mask, center, inner_radius_px, 0, thickness=-1)

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[..., 0]
    valid = (mask > 0) & (l_channel > 30) & (l_channel < 220)

    if not np.any(valid):
        return None

    avg_a = float(lab[..., 1][valid].mean())
    avg_b = float(lab[..., 2][valid].mean())
    return avg_a, avg_b


# Limites de las dos zonas, como fraccion del radio del iris:
# - pupila/reflejo: 0 a 0.30 -- nunca se toca
# - zona interior (centro miel/ambar): 0.30 a 0.60
# - zona exterior (anillo verde, cerca del limbo oscuro): 0.70 a 1.0
# (0.60-0.70 se deja como transicion, sin muestrear ahi para no mezclar)
_INNER_ZONE = (0.30, 0.65)
_OUTER_ZONE = (0.60, 1.0)


def _sample_from_single_reference(
    reference_image_bytes: bytes,
    landmarker,
) -> Optional[Tuple[float, float, float, float, int]]:
    """
    Intenta muestrear el color de iris de UNA foto de referencia puntual,
    por ZONA (interior/miel y exterior/verde) por separado.

    Returns (inner_a, inner_b, outer_a, outer_b, min_radius) o None si no
    se pudo, donde min_radius es el menor de los dos radios de iris
    detectados (util para comparar calidad entre varias fotos candidatas).
    """
    arr = np.frombuffer(reference_image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        return None
    img_h, img_w = image_bgr.shape[:2]

    detection_image = _resize_for_detection(image_bgr)
    image_rgb = cv2.cvtColor(detection_image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

    result = _detect_with_timeout(landmarker, mp_image, timeout_seconds=25.0)
    if result is None or not result.face_landmarks:
        return None

    landmarks = result.face_landmarks[0]
    left_center, left_radius = _iris_center_and_radius(landmarks, _LEFT_IRIS_IDX, img_w, img_h)
    right_center, right_radius = _iris_center_and_radius(landmarks, _RIGHT_IRIS_IDX, img_w, img_h)
    min_radius = min(left_radius, right_radius)

    logger.info(
        f"[EYE_COLOR] Candidata: radio izq={left_radius}px, der={right_radius}px (imagen {img_w}x{img_h})"
    )

    def _sample_both_eyes(inner_frac, outer_frac):
        l = _sample_iris_zone_lab_ab(image_bgr, left_center, left_radius, inner_frac, outer_frac)
        r = _sample_iris_zone_lab_ab(image_bgr, right_center, right_radius, inner_frac, outer_frac)
        samples = [s for s in (l, r) if s is not None]
        if not samples:
            return None
        a = sum(s[0] for s in samples) / len(samples)
        b = sum(s[1] for s in samples) / len(samples)
        return a, b

    inner = _sample_both_eyes(*_INNER_ZONE)
    outer = _sample_both_eyes(*_OUTER_ZONE)
    if inner is None or outer is None:
        return None

    return inner[0], inner[1], outer[0], outer[1], min_radius


def sample_target_color_from_reference(
    reference_images: List[bytes],
    model_path: str = "/runpod-volume/models/mediapipe/face_landmarker.task",
    min_acceptable_radius: int = 8,
) -> Optional[Tuple[float, float, float, float]]:
    """
    Prueba TODAS las fotos de referencia disponibles de la donante y se
    queda con el muestreo de la que tenga el iris mas grande (mas
    confiable). Muestrea DOS zonas por separado: el centro (miel/ambar,
    tal cual es en la realidad) y el anillo exterior cerca del limbo
    (donde vive el verde en un ojo con heterocromia). Si ninguna foto
    alcanza `min_acceptable_radius` pixeles, se descarta el muestreo por
    completo y se cae al metodo de texto.

    Returns:
        (inner_a, inner_b, outer_a, outer_b) de la mejor foto encontrada,
        o None si ninguna foto alcanzo el minimo de confiabilidad.
    """
    if not reference_images:
        return None

    try:
        landmarker = _get_landmarker(model_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None

    best_result = None  # (inner_a, inner_b, outer_a, outer_b, min_radius)
    for idx, ref_bytes in enumerate(reference_images):
        sample = _sample_from_single_reference(ref_bytes, landmarker)
        if sample is None:
            continue
        inner_a, inner_b, outer_a, outer_b, min_radius = sample
        if best_result is None or min_radius > best_result[4]:
            best_result = (inner_a, inner_b, outer_a, outer_b, min_radius)

    if best_result is None:
        logger.warning("[EYE_COLOR] Ninguna foto de referencia produjo un muestreo valido.")
        return None

    inner_a, inner_b, outer_a, outer_b, min_radius = best_result
    if min_radius < min_acceptable_radius:
        logger.warning(
            f"[EYE_COLOR] La mejor foto disponible tiene radio de iris={min_radius}px, "
            f"por debajo del minimo aceptable ({min_acceptable_radius}px) -- el muestreo "
            f"no es confiable. Se descarta y se cae al metodo de texto como respaldo."
        )
        return None

    # Boost de crominancia SOLO en la zona exterior (donde necesitamos que
    # el verde se note con claridad). El centro se deja tal cual se
    # muestreo -- se busca fidelidad real ahi, no intensidad.
    _OUTER_CHROMA_BOOST = 1.1
    outer_a = 128 + (outer_a - 128) * _OUTER_CHROMA_BOOST
    outer_b = 128 + (outer_b - 128) * _OUTER_CHROMA_BOOST
    outer_a = float(np.clip(outer_a, 0, 255))
    outer_b = float(np.clip(outer_b, 0, 255))

    logger.info(
        f"[EYE_COLOR] Mejor foto de referencia: radio={min_radius}px -- "
        f"centro(a={inner_a:.1f},b={inner_b:.1f}) anillo(a={outer_a:.1f},b={outer_b:.1f}, boost x{_OUTER_CHROMA_BOOST})"
    )
    return inner_a, inner_b, outer_a, outer_b


def correct_eye_color(
    image_bytes: bytes,
    target_color: str,
    model_path: str = "/runpod-volume/models/mediapipe/face_landmarker.task",
    reference_images: Optional[List[bytes]] = None,
) -> Optional[bytes]:
    """
    Corrige el color de ojos de una imagen generada, en DOS zonas
    independientes (heterocromia real):

      - CENTRO (miel/ambar): se prioriza fidelidad al color real
        muestreado de la donante -- empuje minimo hacia el ancla de
        texto, para que se vea como es ella de verdad.
      - ANILLO EXTERIOR (verde, cerca del limbo): se prioriza que el
        color pedido (ej. "green") sea claramente visible -- empuje
        fuerte hacia el ancla de texto, porque el promedio de pixeles
        crudos de esta zona suele salir mas apagado de lo que se
        percibe a simple vista.

    Si no hay fotos de referencia confiables, las dos zonas usan
    directamente el ancla de texto (mismo color en todo el iris).
    """
    # --- Ancla de color por texto: SIEMPRE se calcula, es la base garantizada ---
    color_name = extract_primary_color_name(target_color)
    logger.info(f"[EYE_COLOR] target_color recibido={target_color!r} -> color_name resuelto={color_name!r}")
    base_hue = _COLOR_HUE_MAP.get(color_name)
    if base_hue is None:
        logger.error(f"[EYE_COLOR] color_name '{color_name}' no tiene hue asociado en _COLOR_HUE_MAP -- se omite correccion.")
        return None

    anchor_hue, anchor_saturation = _compute_hue_and_intensity(target_color, base_hue)
    anchor_bgr = cv2.cvtColor(np.uint8([[[anchor_hue, anchor_saturation, 160]]]), cv2.COLOR_HSV2BGR)
    anchor_lab = cv2.cvtColor(anchor_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)[0][0]
    anchor_a, anchor_b = float(anchor_lab[1]), float(anchor_lab[2])

    # Valores por defecto (sin foto confiable): en vez de que las dos zonas
    # usen exactamente el mismo ancla (lo que se veia "todo verde parejo,
    # sin centro"), se simula una heterocromia generica -- el centro se
    # mezcla hacia un tono ambar/miel generico, para que incluso el
    # respaldo por texto tenga la sensacion de un ojo real con dos tonos.
    _GENERIC_WARM_A, _GENERIC_WARM_B = 140.0, 138.0  # ambar/miel generico
    _GENERIC_WARM_MIX = 0.55
    inner_target_a = anchor_a * (1 - _GENERIC_WARM_MIX) + _GENERIC_WARM_A * _GENERIC_WARM_MIX
    inner_target_b = anchor_b * (1 - _GENERIC_WARM_MIX) + _GENERIC_WARM_B * _GENERIC_WARM_MIX
    outer_target_a, outer_target_b = anchor_a, anchor_b
    inner_opacity = 0.65
    outer_opacity = 0.65

    if reference_images:
        sampled = sample_target_color_from_reference(reference_images, model_path)
        if sampled is not None:
            s_inner_a, s_inner_b, s_outer_a, s_outer_b = sampled

            # CENTRO: fidelidad real, empuje minimo hacia el ancla.
            INNER_ANCHOR_PULL = 0.05
            inner_target_a = s_inner_a * (1 - INNER_ANCHOR_PULL) + anchor_a * INNER_ANCHOR_PULL
            inner_target_b = s_inner_b * (1 - INNER_ANCHOR_PULL) + anchor_b * INNER_ANCHOR_PULL

            # ANILLO EXTERIOR: empuje fuerte hacia el ancla, para que el
            # verde se note con claridad (el promedio crudo de esta zona
            # suele salir muy apagado).
            OUTER_ANCHOR_PULL = 0.45
            outer_target_a = s_outer_a * (1 - OUTER_ANCHOR_PULL) + anchor_a * OUTER_ANCHOR_PULL
            outer_target_b = s_outer_b * (1 - OUTER_ANCHOR_PULL) + anchor_b * OUTER_ANCHOR_PULL

            inner_opacity = 0.85
            outer_opacity = 0.90

            logger.info(
                f"[EYE_COLOR] Dos zonas -- centro: muestreado=({s_inner_a:.1f},{s_inner_b:.1f}) "
                f"empuje={INNER_ANCHOR_PULL} -> final=({inner_target_a:.1f},{inner_target_b:.1f}); "
                f"anillo: muestreado=({s_outer_a:.1f},{s_outer_b:.1f}) empuje={OUTER_ANCHOR_PULL} "
                f"-> final=({outer_target_a:.1f},{outer_target_b:.1f})"
            )
        else:
            logger.warning(f"[EYE_COLOR] No se pudo muestrear la foto de referencia -- se usa solo el ancla de texto en ambas zonas (a={anchor_a:.1f}, b={anchor_b:.1f}).")
    else:
        logger.info(f"[EYE_COLOR] Sin fotos de referencia -- se usa solo el ancla de texto en ambas zonas (a={anchor_a:.1f}, b={anchor_b:.1f}).")

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


    unified_radius = int(round((left_radius + right_radius) / 2))

    corrected = _recolor_iris_two_zones(
        image_bgr, left_center, unified_radius,
        inner_target_a, inner_target_b, inner_opacity,
        outer_target_a, outer_target_b, outer_opacity,
    )
    corrected = _recolor_iris_two_zones(
        corrected, right_center, unified_radius,
        inner_target_a, inner_target_b, inner_opacity,
        outer_target_a, outer_target_b, outer_opacity,
    )

    success, encoded = cv2.imencode(".png", corrected)
    if not success:
        return None
    return encoded.tobytes()
