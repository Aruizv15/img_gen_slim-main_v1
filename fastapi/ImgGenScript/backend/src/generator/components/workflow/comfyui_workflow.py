import json
from typing import Any

from src.utils.io import load_json_file, save_json_file

class ComfyUIWorkflow:
    """
    A helper class to load, manipulate, and save ComfyUI workflow files.

    This class provides an object-oriented interface to interact with the
    structure of a ComfyUI workflow, which is represented as a JSON object.
    It allows for loading a workflow from a file and programmatically editing
    nodes, inputs, and connections.

    Attributes:
        workflow (dict): A dictionary representing the loaded ComfyUI workflow.
    """
    def __init__(self, workflow_path : str =None):
        """
        Initializes the ComfyUI workflow editor.

        Args:
            workflow_path (str, optional): The path to a workflow JSON file to
                load upon initialization. Defaults to None.
        """
        self.workflow = {}
        if workflow_path:
            self.load_workflow(workflow_path)

    def load_workflow(self, workflow_path: str, verbose: bool = False):
        """
        Loads a workflow from a JSON file into the instance.

        Args:
            workflow_path (str): The path to the ComfyUI workflow JSON file.
            verbose (bool, optional): If True, prints a success message upon loading.

        Raises:
            FileNotFoundError: If the file is not found at the specified path.
            json.JSONDecodeError: If the file is not a valid JSON.
        """
        try:
            self.workflow = load_json_file(workflow_path)
            if verbose:
                print(f"Workflow successfully loaded from: {workflow_path}")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"The workflow file was not found at the path: {workflow_path}") from e
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Could not decode JSON file at: {workflow_path}", e.doc, e.pos) from e

    def node_check(self, node_id : str):
        """
        Checks if a node exists in the workflow by its ID.

        Args:
            node_id (str): The ID of the node to check.

        Raises:
            ValueError: If the node with the given ID is not found.
        """
        if node_id not in self.workflow:
            raise ValueError(f"Node '{node_id}' was not found in the workflow.")
        
    def input_check(self, node_id : str, input_name : str):
        """
        Checks if a node exists and has a specific input field.

        Args:
            node_id (str): The ID of the node to check.
            input_name (str): The name of the input field to check for.

        Raises:
            ValueError: If the node or its specified input is not found.
        """
        self.node_check(node_id)
        if input_name not in self.workflow[node_id]["inputs"]:
            raise ValueError(f"Node '{node_id}' does not have an input named '{input_name}'.")

    def get_node_by_id(self, node_id : str):
        """
        Gets a workflow node by its ID.

        Args:
            node_id (str): The ID of the node to retrieve.

        Returns:
            A dictionary representing the requested node.

        Raises:
            ValueError: If the node is not found.
        """
        self.node_check(node_id)
        return self.workflow.get(node_id)
    
    def remove_node(self, node_id : str):
        """
        Removes a single node from the workflow by its ID.

        Args:
            node_id (str): The ID of the node to remove.
        """
        self.node_check(node_id)
        del self.workflow[node_id]

    def remove_nodes(self, list_nodes_ids : list, verbose : bool = False):
        """
        Removes multiple nodes from the workflow.

        Args:
            list_nodes_ids (list): A list of node ID strings to be removed.
            verbose (bool): If True, prints a confirmation message for each removal.
        """
        for node_id in list_nodes_ids:
            self.remove_node(node_id)
        if verbose:
            print(f"\r[WORKFLOW - STRUCTURE] Removed node{'s' if len(list_nodes_ids) > 1 else ''}: {list_nodes_ids}")

    def edit_node_input(self, node_id : str, input_name : str, new_value : Any, verbose : bool = False):
        """
        Edits the value of a specific input for a given node.

        Args:
            node_id (str): The ID of the node to edit.
            input_name (str): The name of the input field to modify.
            new_value (Any): The new value to set for the input.
            verbose (bool, optional): If True, prints a confirmation message.
        """
        node = self.get_node_by_id(node_id)
        self.input_check(node_id, input_name)
        node["inputs"][input_name] = new_value
        if verbose:
            print(f"\r[WORKFLOW - INPUT] {node_id}.{input_name} = {new_value}.")

    def edit_workflow_inputs(self, args : list[tuple], verbose : bool = False):
        """
        Edits multiple node inputs in the workflow in a single call.

        Args:
            args (list[tuple]): A list of tuples, where each tuple contains
                (node_id, input_name, new_value).
            verbose (bool, optional): If True, prints confirmation messages for each edit.
        """
        for node_id, input_name, new_value in args:
            self.edit_node_input(node_id, input_name, new_value, verbose)

    def remove_connection(
            self,
            from_node_id : str,
            from_output_index : int,
            to_node_id : str,
            to_input_name : str,
            verbose : bool = False
        ):
        """
        Removes a connection between two nodes.

        This works by setting the target input to `None`.

        Args:
            from_node_id (str): The ID of the source node.
            from_output_index (int): The index of the output on the source node.
            to_node_id (str): The ID of the destination node.
            to_input_name (str): The name of the input on the destination node.
            verbose (bool, optional): If True, prints a confirmation message.
        """
        self.input_check(to_node_id, to_input_name)
        to_node = self.get_node_by_id(to_node_id)
        input_value = to_node["inputs"][to_input_name]
        if isinstance(input_value, list) and len(input_value) == 2 and \
           input_value[0] == from_node_id and input_value[1] == from_output_index:
            to_node["inputs"][to_input_name] = None
            if verbose:
                print(f"\r[WORKFLOW - STRUCTURE] Removed connection from {from_node_id}[{from_output_index}] → {to_node_id}.{to_input_name}")
        else:
            raise ValueError(f"Connection from {from_node_id}[{from_output_index}] → {to_node_id}.{to_input_name} was not found.")

    def connect_nodes(
            self,
            from_node_id: str,
            from_output_index : int,
            to_node_id : str,
            to_input_name: str,
            verbose : bool = False
        ):
        """
        Connects the output of one node to the input of another.

        This creates the standard ComfyUI link format: `[source_node_id, source_output_index]`.

        Args:
            from_node_id (str): The ID of the source node.
            from_output_index (int): The index of the output on the source node.
            to_node_id (str): The ID of the destination node.
            to_input_name (str): The name of the input on the destination node.
            verbose (bool, optional): If True, prints a confirmation message.
        """
        self.input_check(to_node_id, to_input_name)
        to_node = self.get_node_by_id(to_node_id)
        to_node["inputs"][to_input_name] = [from_node_id, from_output_index]
        if verbose:
            print(f"\r[WORKFLOW - STRUCTURE] Connected {from_node_id}[{from_output_index}] → {to_node_id}.{to_input_name}")

    def save_workflow(self, output_path: str, verbose : bool = False):
        """
        Saves the current state of the workflow to a JSON file.

        Args:
            output_path (str): The file path where the workflow will be saved.
            verbose (bool, optional): If True, prints a confirmation message.

        Raises:
            RuntimeError: If there is an error during the file-saving process.
        """
        try:
            save_json_file(output_path, self.workflow, indent=4)
            if verbose:
                print(f"Workflow successfully saved to: {output_path}")
        except Exception as e:
            raise RuntimeError(f"Error saving workflow to '{output_path}': {e}") from e