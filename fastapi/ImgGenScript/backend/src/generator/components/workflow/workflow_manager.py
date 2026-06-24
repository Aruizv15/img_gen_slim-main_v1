import copy

from typing import List, Tuple, Dict, Any, Optional, Sequence
from .comfyui_workflow import ComfyUIWorkflow

class WorkflowManager:
    """
    Manages the lifecycle of a ComfyUI workflow.

    This class acts as an abstraction layer over `ComfyUIWorkflow`.
    It allows loading a workflow template, creating a working copy for
    modifications, and finally, getting the processed workflow dictionary
    for execution. This approach ensures that the original template
    remains untouched.

    Attributes:
        template (ComfyUIWorkflow, optional): The base workflow template.
        workflow (ComfyUIWorkflow, optional): The active working copy of the workflow.
    """

    def __init__(self, template_path: Optional[str] = None):
        """
        Initializes the WorkflowManager.

        Args:
            template_path: If provided, loads a workflow template from this
                path upon initialization.
        """
        self.template: Optional[ComfyUIWorkflow] = None
        self.workflow: Optional[ComfyUIWorkflow] = None
        if template_path:
            self.load_template(template_path)

    def load_template(self, path: str) -> None:
        """
        Loads the base workflow template from a JSON file.

        Args:
            path (str): Path to the workflow JSON file.
        """
        self.template = ComfyUIWorkflow(path)
        self.workflow = None

    def start(self) -> None:
        """
        Creates a working copy from the loaded template.

        Raises:
            ValueError: If no template has been loaded.
        """
        if not self.template:
            raise ValueError("No template loaded")
        self.workflow = copy.deepcopy(self.template)

    def reset(self) -> None:
        """
        Discards the current working copy of the workflow.
        """
        self.workflow = None

    def edit_inputs(self, modifications: List[Tuple[str, str, Any]], verbose: bool = False) -> None:
        """
        Applies a series of modifications to the active workflow.

        If no active workflow exists, one is created from the template
        before applying the modifications.

        Args:
            modifications (List[Tuple[str, str, Any]]): A list of tuples, where each tuple defines a
                modification (e.g., ('node_id', 'input_name', 'value')).
            verbose (bool, optional): If True, prints additional information.
        """
        if not self.workflow:
            self.start()
        assert self.workflow is not None
        self.workflow.edit_workflow_inputs(modifications, verbose)

    def connect_nodes(self, from_node: str, from_output: int, to_node: str, to_input: str, verbose: bool = False) -> None:
        """
        Adds a new connection between two nodes in the workflow.

        Args:
            from_node (str): The ID of the source node.
            from_output (int): The ID of the output on the source node.
            to_node (str): The ID of the destination node.
            to_input (str): The name of the input on the destination node.
            verbose (bool, optional): If True, prints a confirmation message.
        """
        if not self.workflow:
            self.start()
        assert self.workflow is not None
        self.workflow.connect_nodes(from_node, from_output, to_node, to_input, verbose)

    def remove_nodes(self, node_ids: List[str] | str, verbose: bool = False) -> None:
        """
        Removes one or more nodes from the current workflow.

        Args:
            node_ids (List[str] | str): The ID (str) of a single node or a list of node IDs.
            verbose (bool, optional): If True, prints a confirmation message.
        """
        if not self.workflow:
            self.start()
        assert self.workflow is not None
        if isinstance(node_ids, str):
            node_ids = [node_ids]
        self.workflow.remove_nodes(node_ids, verbose)

    def edit_structure(
        self,
        remove: Optional[Sequence[str]] = None,
        reconnect: Optional[List[Tuple[str, int, str, str]]] = None,
        verbose: bool = False,
    ) -> None:
        """
        Apply structural changes: remove nodes and reconnect others.

        Args:
            remove (Sequence[str], optional): List of node IDs to remove.
            reconnect (List[Tuple[str, int, str, str]], optional): List of (from_node, from_output, to_node, to_input).
            verbose (bool, optional): Print actions.
        """
        if not self.workflow:
            self.start()

        if remove:
            self.remove_nodes(list(remove), verbose)

        if reconnect:
            for src, out, dst, inp in reconnect:
                self.connect_nodes(src, out, dst, inp, verbose)

    def get_dict(self) -> Dict[str, Any]:
        """
        Returns the current, processed workflow dictionary.

        Returns:
            The workflow as a dictionary.
        """
        if not self.workflow:
            raise ValueError("No active workflow")
        return self.workflow.workflow