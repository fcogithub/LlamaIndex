from typing import List, Optional, Type, Protocol
import functools
from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.event_management.handlers import BaseEventHandler
from llama_index.core.event_management.events.base import BaseEvent


class Dispatcher(BaseModel):
    name: str = Field(default_factory=str, description="Name of dispatcher")
    handlers: List[BaseEventHandler] = Field(
        default=[], description="List of attached handlers"
    )
    parent: Optional["Dispatcher"] = Field(
        default_factory=None, description="List of parent dispatchers"
    )
    propagate: bool = Field(
        default=True,
        description="Whether to propagate the event to parent dispatchers and their handlers",
    )

    def add_handler(self, handler) -> None:
        """Add handler to set of handlers."""
        self.handlers += [handler]

    def event(self, event_cls: Type[BaseEvent]) -> None:
        """Dispatch event to all registered handlers."""
        event = event_cls()
        for h in self.handlers:
            h.handle(event)

    def span_enter(self, id: str) -> None:
        """Send notice to handlers that a span with id has started."""
        for h in self.handlers:
            h.span_enter(id=id)

    def span_exit(self, id: str) -> None:
        """Send notice to handlers that a span with id has started."""
        for h in self.handlers:
            h.span_exit(id=id)

    @property
    def log_name(self) -> str:
        """Name to be used in logging."""
        if self.parent:
            return f"{self.parent.name}.{self.name}"
        else:
            return self.name

    class Config:
        arbitrary_types_allowed = True


# class protocol
class HasDispatcherProtocol(Protocol):
    @property
    def dispatcher(self) -> Dispatcher:
        ...


class DispatcherMixin:
    @staticmethod
    def span(func):
        @functools.wraps(func)
        def wrapper(self: HasDispatcherProtocol, *args, **kwargs):
            self.dispatcher.span_enter(id=id)
            func(self, *args, **kwargs)
            self.dispatcher.span_exit(id=id)

        return wrapper