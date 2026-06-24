from typing import Dict, Any
from pathlib import Path

class PromptBuilder:
    """
    Manages the creation of formatted text prompts from templates.

    This class allows for adding named template strings and then building
    final prompts by formatting these templates with provided arguments.
    It supports multi-pass formatting for nested placeholders.
    """
    def __init__(self):
        """
        Initializes the PromptBuilder.

        Attributes:
            templates (Dict[str, str]): A dictionary to store prompt templates.
            prompts (Dict[str, str]): A dictionary to store the final, built prompts.
        """
        self.templates: Dict[str, str] = {}
        self.prompts: Dict[str, str] = {}

    def add(self, name: str, template: str) -> None:
        """
        Adds a prompt template string to the collection.

        Args:
            name (str): The name of the prompt (e.g., 'positive_prompt').
            template (str): The template string itself.
        """
        self.templates[name] = template

    def build(self, name: str, args: Dict[str, Any], in_depth: bool = True) -> str:
        """
        Creates a formatted prompt from a template and arguments.

        Args:
            name (str): The type of prompt template to use.
            args (Dict[str, Any]): A dictionary of arguments to format the template with.
            in_depth (bool): If True, performs a second formatting pass, useful for nested placeholders.
        """
        if name not in self.templates:
            raise ValueError(f"Template '{name}' not found")
        prompt = self.templates[name].format(**args)
        if in_depth:
            prompt = prompt.format(**args)
        self.prompts[name] = prompt
        return prompt

    def build_all(self, config: Dict[str, Any]) -> None:
        """
        Builds multiple prompts based on a configuration dictionary.

        Iterates through the config, building each prompt for which a template exists.
        The config can specify arguments and an optional 'in_depth' flag for each prompt.

        Args:
            config: A dictionary where keys are prompt names.
                Each value can be a dictionary of arguments, or a dictionary
                containing 'args' (dict) and an optional 'in_depth' (bool).
                If 'in_depth' is not provided, it defaults to False.
        """
        for name, prompt_config in config.items():
            if name in self.templates:
                if isinstance(prompt_config, dict) and "args" in prompt_config:
                    args = prompt_config.get("args", {})
                    in_depth = prompt_config.get("in_depth", False)
                else:
                    args = prompt_config
                    in_depth = False
                self.build(name, args, in_depth)