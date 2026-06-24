from .geometry import random_rotation, random_crop
from .color import (
    hdr_simulation, sdr_simulation, limited_dynamic_range,
    random_contrast, random_saturation, random_tint
)
from .optical import (
    lens_distortion, chromatic_aberration, vignette,
    lens_dust_spots, flash_effect
)
from .noise import blur, motion_blur, add_noise, over_sharpening
from .artifacts import jpeg_compression_artifacts

__all__ = [
    "random_rotation", "random_crop",
    "hdr_simulation", "sdr_simulation", "limited_dynamic_range",
    "random_contrast", "random_saturation", "random_tint",
    "lens_distortion", "chromatic_aberration", "vignette",
    "lens_dust_spots", "flash_effect",
    "blur", "motion_blur", "add_noise", "over_sharpening",
    "jpeg_compression_artifacts",
]

def get_effect_map():
    return {name: globals()[name] for name in __all__}