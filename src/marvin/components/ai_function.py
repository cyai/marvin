import asyncio
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Optional,
    TypeVar,
    Union,
    overload,
)

from pydantic import BaseModel, Field
from typing_extensions import ParamSpec, Self

from marvin._mappings.chat_completion import chat_completion_to_model
from marvin.client.openai import MarvinChatCompletion
from marvin.components.prompt.fn import PromptFunction
from marvin.utilities.jinja import BaseEnvironment

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion

T = TypeVar("T")

P = ParamSpec("P")


class AIFunction(
    MarvinChatCompletion,
    Generic[P, T],
):
    fn: Optional[Callable[P, T]] = None
    environment: Optional[BaseEnvironment] = None
    prompt: Optional[str] = Field(default=inspect.cleandoc("""
        Your job is to generate likely outputs for a Python function with the
        following signature and docstring:

        {{_source_code}}

        The user will provide function inputs (if any) and you must respond with
        the most likely result.

        user: The function was called with the following inputs:
        {%for (arg, value) in _arguments.items()%}
        - {{ arg }}: {{ value }}
        {% endfor %}

        What is its output?
    """))
    name: str = "FormatResponse"
    description: str = "Formats the response."
    field_name: str = "data"
    field_description: str = "The data to format."

    def __call__(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> Union[T, Coroutine[Any, Any, T]]:
        if asyncio.iscoroutinefunction(self.fn):
            return self.acall(*args, **kwargs)
        return self.call(*args, **kwargs)

    def call(self, *args: P.args, **kwargs: P.kwargs) -> T:
        prompt, model = self.as_prompt(*args, **kwargs).model_pair()
        response = self.create(**prompt.serialize())
        return getattr(chat_completion_to_model(model, response), self.field_name)

    async def acall(self, *args: P.args, **kwargs: P.kwargs) -> T:
        prompt, model = self.as_prompt(*args, **kwargs).model_pair()
        response = await self.acreate(**prompt.serialize())
        return getattr(chat_completion_to_model(model, response), self.field_name)

    def map(self, *arg_list: list[Any], **kwarg_list: list[Any]) -> list[T]:
        return [
            self.call(*args, **{k: v[i] for k, v in kwarg_list.items()})
            for i, args in enumerate(zip(*arg_list))
        ]

    async def amap(self, *arg_list: list[Any], **kwarg_list: list[Any]) -> list[T]:
        return await asyncio.gather(
            *[
                self.acall(*args, **{k: v[i] for k, v in kwarg_list.items()})
                for i, args in enumerate(zip(*arg_list))
            ]
        )

    def as_prompt(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> PromptFunction[BaseModel]:
        return PromptFunction[BaseModel].as_tool_call(
            fn=self.fn,
            environment=self.environment,
            prompt=self.prompt,
            model_name=self.name,
            model_description=self.description,
            field_name=self.field_name,
            field_description=self.field_description,
        )(*args, **kwargs)

    def model_dump(
        self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> dict[str, Any]:
        return self.as_prompt(*args, **kwargs).serialize()

    @overload
    @classmethod
    def as_decorator(
        cls: type[Self],
        *,
        environment: Optional[BaseEnvironment] = None,
        prompt: Optional[str] = None,
        model_name: str = "FormatResponse",
        model_description: str = "Formats the response.",
        field_name: str = "data",
        field_description: str = "The data to format.",
        create: Optional[Callable[..., "ChatCompletion"]] = None,
        acreate: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> Callable[P, Self]:
        pass

    @overload
    @classmethod
    def as_decorator(
        cls: type[Self],
        fn: Callable[P, Union[T, Coroutine[Any, Any, T]]],
        *,
        environment: Optional[BaseEnvironment] = None,
        prompt: Optional[str] = None,
        model_name: str = "FormatResponse",
        model_description: str = "Formats the response.",
        field_name: str = "data",
        field_description: str = "The data to format.",
        create: Optional[Callable[..., "ChatCompletion"]] = None,
        acreate: Optional[Callable[..., Awaitable[Any]]] = None,
    ) -> Self:
        pass

    @classmethod
    def as_decorator(
        cls: type[Self],
        fn: Optional[Callable[P, Union[T, Coroutine[Any, Any, T]]]] = None,
        *,
        environment: Optional[BaseEnvironment] = None,
        prompt: Optional[str] = None,
        model_name: str = "FormatResponse",
        model_description: str = "Formats the response.",
        field_name: str = "data",
        field_description: str = "The data to format.",
        **render_kwargs: Any,
    ) -> Union[Callable[[Callable[P, Union[T, Coroutine[Any, Any, T]]]], Self], Self]:
        def decorator(func: Callable[P, Union[T, Coroutine[Any, Any, T]]]) -> Self:
            return cls(
                fn=func,
                environment=environment,
                name=model_name,
                description=model_description,
                field_name=field_name,
                field_description=field_description,
                **({"prompt": prompt} if prompt else {}),
                **render_kwargs,
            )

        if fn is not None:
            return decorator(fn)

        return decorator


@overload
def ai_fn(
    *,
    environment: Optional[BaseEnvironment] = None,
    prompt: Optional[str] = None,
    model_name: str = "FormatResponse",
    model_description: str = "Formats the response.",
    field_name: str = "data",
    field_description: str = "The data to format.",
    create: Optional[Callable[..., "ChatCompletion"]] = None,
    acreate: Optional[Callable[..., Awaitable["ChatCompletion"]]] = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    pass


@overload
def ai_fn(
    fn: Callable[P, T],
    *,
    environment: Optional[BaseEnvironment] = None,
    prompt: Optional[str] = None,
    model_name: str = "FormatResponse",
    model_description: str = "Formats the response.",
    field_name: str = "data",
    field_description: str = "The data to format.",
    create: Optional[Callable[..., "ChatCompletion"]] = None,
    acreate: Optional[Callable[..., Awaitable["ChatCompletion"]]] = None,
) -> Callable[P, T]:
    pass


def ai_fn(
    fn: Optional[Callable[P, Union[T, Coroutine[Any, Any, T]]]] = None,
    *,
    environment: Optional[BaseEnvironment] = None,
    prompt: Optional[str] = None,
    model_name: str = "FormatResponse",
    model_description: str = "Formats the response.",
    field_name: str = "data",
    field_description: str = "The data to format.",
    create: Optional[Callable[..., "ChatCompletion"]] = None,
    acreate: Optional[Callable[..., Awaitable["ChatCompletion"]]] = None,
) -> Union[
    Callable[
        [Callable[P, Union[T, Coroutine[Any, Any, T]]]],
        Callable[P, Union[T, Coroutine[Any, Any, T]]],
    ],
    Callable[P, Union[T, Coroutine[Any, Any, T]]],
]:
    if fn is not None:
        return AIFunction[P, T].as_decorator(
            fn=fn,
            environment=environment,
            prompt=prompt,
            model_name=model_name,
            model_description=model_description,
            field_name=field_name,
            field_description=field_description,
            create=create,
            acreate=acreate,
        )

    def decorator(
        func: Callable[P, Union[T, Coroutine[Any, Any, T]]]
    ) -> Callable[P, Union[T, Coroutine[Any, Any, T]]]:
        return AIFunction[P, T].as_decorator(
            fn=func,
            environment=environment,
            prompt=prompt,
            model_name=model_name,
            model_description=model_description,
            field_name=field_name,
            field_description=field_description,
            create=create,
            acreate=acreate,
        )

    return decorator
