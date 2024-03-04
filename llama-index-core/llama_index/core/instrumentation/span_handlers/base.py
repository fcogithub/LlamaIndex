from abc import abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar

from llama_index.core.bridge.pydantic import BaseModel, Field
from llama_index.core.instrumentation.span.base import BaseSpan

T = TypeVar("T", bound=BaseSpan)


class BaseSpanHandler(BaseModel, Generic[T]):
    open_spans: Dict[str, T] = Field(
        default_factory=dict, description="Dictionary of open spans."
    )
    current_span_id: Optional[str] = Field(
        default=None, description="Id of current span."
    )

    class Config:
        arbitrary_types_allowed = True

    def class_name(cls) -> str:
        """Class name."""
        return "BaseSpanHandler"

    def span_enter(self, id: str) -> None:
        """Logic for entering a span."""
        if id in self.open_spans:
            pass  # should probably raise an error here
        else:
            # TODO: thread safe
            span = self.new_span(id=id, parent_span_id=self.current_span_id)
            if span:
                self.open_spans[id] = span
                self.current_span_id = id
        print(f"current span: {self.current_span_id}")

    def span_exit(self, id: str) -> None:
        """Logic for exiting a span."""
        self.prepare_to_drop_span(id)
        if self.current_span_id == id:
            self.current_span_id = self.open_spans[id].parent_id
        del self.open_spans[id]

    @abstractmethod
    def new_span(self, id: str, parent_span_id: Optional[str]) -> Optional[T]:
        """Create a span."""
        ...

    @abstractmethod
    def prepare_to_drop_span(self, id: str) -> Any:
        """Logic for preparing to drop a span."""
        ...
