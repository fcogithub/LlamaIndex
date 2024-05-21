import os
from typing import Dict, Any, Union, Optional

from ibm_watsonx_ai.foundation_models import ModelInference, Model

from llama_index.core.base.llms.generic_utils import (
    get_from_param_or_env,
)

# Import SecretStr directly from pydantic
# since there is not one in llama_index.core.bridge.pydantic
try:
    from pydantic.v1 import SecretStr
except ImportError:
    from pydantic import SecretStr


def retrive_attributes_from_model(
    model: Union[ModelInference, Model, None]
) -> Dict[str, Any] | None:
    """
    Retrieves following attributes: `model_id`, 'deployment_id`, `project_id`,
    `space_id` and model text generation params, from the model interface object.

    :param model: watsonx.ai model interface
    :type model: Union[ModelInference, Model, None]
    :return: Returns dict with the values of mentioned attributes or None if model is None
    :rtype: Dict[str, Any] | None
    """
    attributes = {}
    if isinstance(model, (ModelInference, Model)):
        attributes["model_id"] = model.model_id
        attributes["deployment_id"] = getattr(model, "deployment_id", None)
        attributes["project_id"] = model._client.default_project_id
        attributes["space_id"] = model._client.default_space_id
        params = model.params or {}
        params.pop("return_options", None)
        attributes["temperature"] = params.pop("temperature", None)
        attributes["max_new_tokens"] = params.pop("max_new_tokens", None)
        attributes["additional_pxarams"] = params

    return attributes


def resolve_watsonx_credentials(
    *,
    url: Optional[SecretStr] = None,
    apikey: Optional[SecretStr] = None,
    token: Optional[SecretStr] = None,
    username: Optional[SecretStr] = None,
    password: Optional[SecretStr] = None,
    instance_id: Optional[SecretStr] = None
) -> Dict[str, SecretStr]:
    """
    Resolve watsonx.ai credentials. If the value of given param is None
    then tries to find corresponding environment variable.


    :raises ValueError: raises when value of required attribute is not found
    :return: Dictionary with resolved credentials items
    :rtype: Dict[str, Any]
    """
    creds = {}
    creds["url"] = convert_to_secret_str(
        get_from_param_or_env("url", url, "WATSONX_URL")
    )

    if "cloud.ibm.com" in creds["url"].get_secret_value():
        creds["apikey"] = convert_to_secret_str(
            get_from_param_or_env("apikey", apikey, "WATSONX_APIKEY")
        )
    else:
        if (
            not token
            and "WATSONX_TOKEN" not in os.environ
            and not password
            and "WATSONX_PASSWORD" not in os.environ
            and not apikey
            and "WATSONX_APIKEY" not in os.environ
        ):
            raise ValueError(
                "Did not find 'token', 'password' or 'apikey',"
                " please add an environment variable"
                " `WATSONX_TOKEN`, 'WATSONX_PASSWORD' or 'WATSONX_APIKEY' "
                "which contains it,"
                " or pass 'token', 'password' or 'apikey'"
                " as a named parameter."
            )
        elif token or "WATSONX_TOKEN" in os.environ:
            creds["token"] = convert_to_secret_str(
                get_from_param_or_env("token", token, "WATSONX_TOKEN")
            )

        elif password or "WATSONX_PASSWORD" in os.environ:
            creds["password"] = convert_to_secret_str(
                get_from_param_or_env("password", password, "WATSONX_PASSWORD")
            )

            creds["username"] = convert_to_secret_str(
                get_from_param_or_env("username", username, "WATSONX_USERNAME")
            )

        elif apikey or "WATSONX_APIKEY" in os.environ:
            creds["apikey"] = convert_to_secret_str(
                get_from_param_or_env("apikey", apikey, "WATSONX_APIKEY")
            )

            creds["username"] = convert_to_secret_str(
                get_from_param_or_env("username", username, "WATSONX_USERNAME")
            )

        if not instance_id or "WATSONX_INSTANCE_ID" not in os.environ:
            creds["instance_id"] = convert_to_secret_str(
                get_from_param_or_env("instance_id", instance_id, "WATSONX_INSTANCE_ID")
            )

    return creds


def convert_to_secret_str(value: Union[SecretStr, str]) -> SecretStr:
    """Convert a string to a SecretStr."""
    if isinstance(value, SecretStr):
        return value
    return SecretStr(value)
