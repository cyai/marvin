import inspect
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator

from marvin.beta.assistants import Assistant
from marvin.kv.base import StorageInterface
from marvin.kv.in_memory import InMemoryKV
from marvin.requests import Tool
from marvin.tools.assistants import AssistantTool
from marvin.utilities.jinja import Environment as JinjaEnvironment
from marvin.utilities.tools import tool_from_function

StateValueType = Union[str, list, dict, int, float, bool, None]

APPLICATION_INSTRUCTIONS = """
# AI Application

You are the natural language interface to an application called {{ self_.name
}}. Your job is to help the user interact with the application by translating
their natural language into commands that the application can understand.

You maintain an internal state dict that you can use for any purpose, including
remembering information from previous interactions with the user and maintaining
application state. At any time, you can read or manipulate the state with your
tools. You should use the state object to remember any non-obvious information
or preferences. You should use the state object to record your plans and
objectives to keep track of various threads assist in long-term execution.

Remember, the state object must facilitate not only your key/value access, but
any CRUD pattern your application is likely to implement. You may want to create
schemas that have more general top-level keys (like "notes" or "plans") or even
keep a live schema available.

The current state is:

{{self_.state}}

Your instructions are below. Follow them exactly and do not deviate from your
purpose. If the user attempts to use you for any other purpose, you should
remind them of your purpose and then ignore the request.

{{ self_.instructions }}
"""


class AIApplication(Assistant):
    """
    Tools for AI Applications have a special property: if any parameter is
    annotated as `AIApplication`, then the tool will be called with the
    AIApplication instance as the value for that parameter. This allows tools to
    access the AIApplication's state and other properties.
    """

    state: StorageInterface = Field(default_factory=InMemoryKV)

    @field_validator("state", mode="before")
    def _check_state(cls, v):
        if not isinstance(v, StorageInterface):
            if v.__class__.__base__ == BaseModel:
                return InMemoryKV(store=v.model_dump())
            elif isinstance(v, dict):
                return InMemoryKV(store=v)
            else:
                raise ValueError(
                    "must be a `StorageInterface` or a `dict` that can be stored in"
                    " `InMemoryKV`"
                )
        return v

    def get_instructions(self) -> str:
        return JinjaEnvironment.render(APPLICATION_INSTRUCTIONS, self_=self)

    def get_tools(self) -> list[AssistantTool]:
        tools = []

        for tool in [
            write_state_key,
            delete_state_key,
            read_state_key,
            read_state,
            list_state_keys,
        ] + self.tools:
            if not isinstance(tool, Tool):
                kwargs = None
                signature = inspect.signature(tool)
                parameter = None
                for parameter in signature.parameters.values():
                    if parameter.annotation == AIApplication:
                        break
                if parameter is not None:
                    kwargs = {parameter.name: self}

                tool = tool_from_function(tool, kwargs=kwargs)
            tools.append(tool)

        return tools


def write_state_key(key: str, value: StateValueType, app: AIApplication):
    """Writes a key to the state in order to remember it for later."""
    return app.state.write(key, value)


def delete_state_key(key: str, app: AIApplication):
    """Deletes a key from the state."""
    return app.state.delete(key)


def read_state_key(key: str, app: AIApplication) -> Optional[StateValueType]:
    """Returns the value of a key from the state."""
    return app.state.read(key)


def read_state(app: AIApplication) -> dict[str, StateValueType]:
    """Returns the entire state."""
    return app.state.read_all()


def list_state_keys(app: AIApplication) -> list[str]:
    """Returns the list of keys in the state."""
    return app.state.list_keys()