from typing import Type, Dict, Any

from src.request import (
    FullBodyRequest, PortraitRequest,
    FullBodySceneData, PortraitSceneData, SceneData,
    FullBodyWorkflowData, PortraitWorkflowData, 
)
from src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

class RequestFactory:
    """
    A factory for creating the necessary data objects for a generation request.

    This class centralizes the logic for retrieving the correct set of classes
    and configuration settings based on the specified generation type (e.g.,
    'fullbody' or 'portrait'). It simplifies the process of assembling the
    components needed to build a `BaseRequest` instance.
    """
    @staticmethod
    def get_request_data(generation_type: str) -> Dict[str, Any]:
        """
        Gets a dictionary of data and classes for a specific generation type.

        Args:
            generation_type (str): The type of generation ('fullbody' or 'portrait').

        Returns:
            A dictionary containing the appropriate request class, data classes,
            settings, and template names for the given generation type.

        Raises:
            ValueError: If an invalid generation type is provided.
        """
        if generation_type == "fullbody":
            return {
                "request_class": FullBodyRequest,
                "scene_data_class": FullBodySceneData,
                "workflow_data_class": FullBodyWorkflowData,
                "settings": SETTINGS.fullbody,
                "positive_prompt_template": SETTINGS.fullbody_prompt_template,
                "hairstyle_options": "hairstyle_fullbody_types",
                "outfit_options": "outfit_fullbody_types",
                "ref_dir": SETTINGS.ref_fullbody_dir,
            }
        elif generation_type == "portrait":
            return {
                "request_class": PortraitRequest,
                "scene_data_class": PortraitSceneData,
                "workflow_data_class": PortraitWorkflowData,
                "settings": SETTINGS.portrait,
                "positive_prompt_template": SETTINGS.portrait_prompt_template,
                "hairstyle_options": "hairstyle_portrait_types",
                "outfit_options": "outfit_portrait_types",
                "ref_dir": SETTINGS.ref_portrait_dir,
            }
        else:
            raise ValueError(f"Invalid generation type: {generation_type}")

    @staticmethod
    def create_scene_data(scene_class: Type[SceneData], generation_type: str, **kwargs) -> SceneData:
        """
        Creates an instance of a specific SceneData subclass.

        This method correctly instantiates either a `FullBodySceneData` or a
        `PortraitSceneData` object by passing the appropriate keyword arguments.

        Args:
            scene_class (Type[SceneData]): The specific `SceneData` class to instantiate.
            generation_type (str): The type of generation ('fullbody' or 'portrait').
            **kwargs: Keyword arguments containing the scene attributes.

        Returns:
            An instance of the specified `SceneData` subclass.
        """
        if generation_type == "fullbody":
            return scene_class(
                expression=kwargs["expression"],
                lighting=kwargs["lighting"],
                pose=kwargs["pose"],
                location=kwargs["location"],
                environment=kwargs["environment"],
                light_temperature=kwargs["light_temperature"]
            )
        elif generation_type == "portrait":
            return scene_class(
                expression=kwargs["expression"],
                lighting=kwargs["lighting"],
                background=kwargs["background"],
                environment=kwargs["environment"],
                light_temperature=kwargs["light_temperature"]
            )
        raise ValueError(f"Invalid generation type for SceneData: {generation_type}")
