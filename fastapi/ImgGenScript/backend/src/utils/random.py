import random
from typing import List, Any

def get_random_option(options_list: List[Any]) -> Any:
    """
    Selects a random element from a list.

    Args:
        options_list (List[Any]): The list of options to choose from.

    Returns:
        Any: A randomly selected element from the list. Returns an None
            if the list is empty or None.
    """
    if not options_list:
        return None
    return random.choice(options_list)


def make_random_seed() -> int:
    """
    Generates a large random integer suitable for use as a seed.

    The seed is generated within the range of 0 to 999,999,999,999,999, inclusive,
    which is a common range for seeds in generation models.

    Returns:
        int: A random integer within the specified range.
    """
    return random.randint(0, 999_999_999_999_999)
