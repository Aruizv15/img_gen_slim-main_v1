from typing import List, Tuple, Any, Dict

def compare_lists(list1: List[Any], list2: List[Any]) -> Tuple[List[Any], List[Any]]:
    """
    Compares two lists and identifies common and differing elements.

    This function takes two lists and returns two new lists: one containing
    elements present in both input lists, and another containing elements
    that are in the first list but not in the second.

    Args:
        list1 (list): The primary list to check against.
        list2 (list): The secondary list for comparison.

    Returns:
        A tuple containing two lists:
        - The first list holds elements common to both `list1` and `list2`.
        - The second list holds elements present in `list1` but absent from `list2`.
    """
    set1 = set(list1)
    set2 = set(list2)

    common_elements = list(set1.intersection(set2))
    uncommon_elements = list(set1.difference(set2))

    return common_elements, uncommon_elements

def get_with_default(data: Dict[str, Any], key: str, default_value: Any) -> Any:
    """
    Safely retrieves a value from a dictionary with a fallback default.

    This function attempts to get a value for a given key from a dictionary.
    It returns a default value if the key does not exist or if the retrieved
    value is considered "falsy" (e.g., `None`, an empty string `""`, `0`, `False`).

    Args:
        data (dict): The dictionary to search within.
        key  (str): The key whose value is to be retrieved.
        default_value (Any): The value to return if the key is not found or its
            associated value is falsy.

    Returns:
        The value from the dictionary corresponding to the key, or the
        `default_value`.
    """
    value = data.get(key)
    return value or default_value
