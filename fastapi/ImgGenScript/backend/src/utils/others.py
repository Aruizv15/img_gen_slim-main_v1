def int_to_ovod_string(number: int) -> str:
    """
    Converts an integer to a zero-padded 'OVODXXXXX' string format.

    This function takes an integer, validates that it is within the acceptable
    range (0 to 99999), and formats it into a 5-digit string with leading
    zeros. It then prepends the 'OVOD' prefix to create the final identifier.

    Args:
        number (int): The integer to convert, which must be between 0 and 99999.

    Returns:
        str: The formatted string, such as 'OVOD00012'.

    Raises:
        ValueError: If the input is not an integer or is outside the valid range.
    """
    if not isinstance(number, int):
        raise ValueError("The input must be an integer.")
    if number > 99999 or number < 0:
        raise ValueError("The input must be in the range 0 - 99999.")

    formatted_number = str(number).zfill(5)[-5:]
    return f"OVOD{formatted_number}"

def workflow_key_mapping(workflow_data: dict, key_map: dict) -> dict:
    """
    Remaps node IDs in a workflow and updates internal references.

    This function takes a dictionary representing a ComfyUI workflow and a
    key map. It performs two main operations:
    1. It creates a new workflow dictionary where the top-level keys (node IDs)
       are renamed according to the `key_map`.
    2. It iterates through each node's `inputs` and updates any internal
       references (e.g., `["12", 0]`) to use the new, remapped node IDs.

    Args:
        workflow_data (dict): The original workflow data as a dictionary.
        key_map (dict): A dictionary mapping old node IDs (str) to new node IDs (str).

    Returns:
        dict: A new workflow dictionary with remapped keys and updated references.
    """
    # 1. Create the new dictionary with the main keys remapped
    new_workflow = {}
    for old_key, value in workflow_data.items():
        new_key = key_map.get(old_key, old_key)
        new_workflow[new_key] = value

    # 2. Iterate over the new workflow to update internal references
    for _, node in new_workflow.items():
        if "inputs" in node and isinstance(node["inputs"], dict):
            
            # Iterate through all entries within 'inputs'
            for input_name, input_value in node["inputs"].items():
                
                # Find values that are lists of the form ["NODE_ID", 0]
                if isinstance(input_value, list) and len(input_value) == 2 and isinstance(input_value[0], str):
                    old_reference = input_value[0]
                    
                    # If the old reference is in our map, update it
                    if old_reference in key_map:
                        new_reference = key_map[old_reference]
                        node["inputs"][input_name][0] = new_reference
    
    return new_workflow