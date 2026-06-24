import random

from PIL import Image
from typing import Dict, Any

from ..effects import random_tint,lens_dust_spots, flash_effect, get_effect_map

effect_map = get_effect_map()

def update_effect_probability(
        effect_name: str,
        base_prob: float,
        environment_type: str,
        light_temp: str
    ) -> float:
    """
    Calculates the final probability of an effect based on context.

    Args:
        effect_name (str): The name of the effect.
        base_prob (float): The base probability from the config.
        environment_type (str): The environment of the image.
        light_temp (str): The light temperature of the scene.

    Returns:
        float: The adjusted probability.
    """
    effect_funct = effect_map.get(effect_name)
    if not effect_funct:
        return 0.0

    if effect_funct == lens_dust_spots:
        if environment_type in ["indoor", "studio"]:
            return base_prob * 0.5
        elif environment_type in ["outdoor", "natural", "urban"]:
            return base_prob * 1.5
    
    if effect_funct == flash_effect:
        if environment_type in ["studio"]:
            return base_prob * 1.5
        elif environment_type in ["outdoor", "natural", "urban"]:
            return 0.0

    return base_prob

def inject_effect_params(
        effect_name: str,
        base_params: Dict[str, Any],
        environment_type: str,
        light_temp: str
    ) -> Dict[str, Any]:
    """
    Prepares the parameters for an effect, adding contextual ones if needed.

    Args:
        effect_name (str): The name of the effect.
        base_params (Dict[str, Any]): The base parameters from the config.
        environment_type (str): The environment of the image.
        light_temp (str): The light temperature of the scene.

    Returns:
        Dict[str, Any]: The final parameters for the effect function.
    """
    effect_funct = effect_map.get(effect_name)
    if effect_funct == random_tint:
        base_params = base_params.copy()
        base_params["light_temp"] = light_temp
    
    if effect_funct == lens_dust_spots:
        base_params = base_params.copy()
        if environment_type in ["indoor", "studio"]:
            base_params["num_spots"] = int(base_params["num_spots"] * 1.5)
        elif environment_type in ["outdoor", "natural", "urban"]:
            base_params["num_spots"] = int(base_params["num_spots"] * 0.5)

    return base_params

def apply_effects_in_block(image: Image.Image, block_config: Dict, effects_config: Dict, environment_type: str, light_temp: str, verbose: bool = False) -> Image.Image:
    """
    Applies a random number of effects from a single processing block.

    This method orchestrates the application of effects within a specific
    block (e.g., 'geometry', 'color'). It determines how many effects to
    apply based on the block's configuration, then randomly selects and
    applies them according to their individual probabilities and parameters.

    Args:
        image (Image.Image): The image to be processed.
        block_config (Dict): The configuration for the current block, specifying
            min/max effects and the list of available effects.
        effects_config (Dict): The style-specific configuration for all effects,
            containing probabilities and parameters.
        environment_type (str): The environment context (e.g., 'indoor', 'outdoor')
            to adjust effect probabilities.
        light_temp (str): The light temperature context (e.g., 'warm', 'cool')
            to inject into effect parameters.
        verbose (bool, optional): If True, prints details about applied effects.
            Defaults to False.

    Returns:
        Image.Image: The image after applying the selected effects from the block.
    """
    num_to_apply = random.randint(block_config["min"], block_config["max"])
    if num_to_apply == 0:
        return image

    available_effects = block_config["effects"]
    random.shuffle(available_effects)
    
    applied_count = 0
    for effect_name in available_effects:
        if applied_count >= num_to_apply:
            break

        effect_settings = effects_config.get(effect_name, {})
        base_prob = effect_settings.get("probability", 0.5)
        final_prob = update_effect_probability(effect_name, base_prob, environment_type, light_temp)

        if random.random() < final_prob:
            params = inject_effect_params(effect_name, effect_settings.get("params", {}), environment_type, light_temp)
            image = effect_map[effect_name](image, **params)
            applied_count += 1

    return image