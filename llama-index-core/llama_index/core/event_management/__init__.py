from llama_index.core.event_management.dispatcher import Dispatcher
from llama_index.core.event_management.handlers import NullHandler

root_dispatcher: Dispatcher = Dispatcher(
    name="root",
    handlers=[NullHandler],
    parent=None,
    propagate=False,
)


def get_dispatcher(name: str) -> Dispatcher:
    """Module method that should be used for creating a new Dispatcher."""
    return Dispatcher(name=name, parent=root_dispatcher)
