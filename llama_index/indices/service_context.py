from copy import deepcopy
import dataclasses
import logging
from dataclasses import dataclass
from typing import Optional

from llama_index.bridge.langchain import BaseLanguageModel

import llama_index
from llama_index.callbacks.base import CallbackManager
from llama_index.embeddings.base import BaseEmbedding
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.indices.prompt_helper import PromptHelper
from llama_index.llm_predictor import LLMPredictor
from llama_index.llm_predictor.base import BaseLLMPredictor, LLMMetadata
from llama_index.llms.utils import LLMType
from llama_index.logger import LlamaLogger
from llama_index.node_parser.interface import NodeParser
from llama_index.node_parser.simple import SimpleNodeParser

logger = logging.getLogger(__name__)

# default service context. Inherited from when calling `from_defaults`.
default_service_context: Optional["ServiceContext"] = None

# global service context. All newly created services without explicitly
# passed service context will use this one. Overrides any default service context.
# Changes made to this context will directly affect downstream services.
global_service_context: Optional["ServiceContext"] = None

def _get_default_node_parser(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    callback_manager: Optional[CallbackManager] = None,
) -> NodeParser:
    """Get default node parser."""
    return SimpleNodeParser.from_defaults(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        callback_manager=callback_manager,
    )


def _get_default_prompt_helper(
    llm_metadata: LLMMetadata,
    context_window: Optional[int] = None,
    num_output: Optional[int] = None,
) -> PromptHelper:
    """Get default prompt helper."""
    if context_window is not None:
        llm_metadata = dataclasses.replace(llm_metadata, context_window=context_window)
    if num_output is not None:
        llm_metadata = dataclasses.replace(llm_metadata, num_output=num_output)
    return PromptHelper.from_llm_metadata(llm_metadata=llm_metadata)


@dataclass
class ServiceContext:
    """Service Context container.

    The service context container is a utility container for LlamaIndex
    index and query classes. It contains the following:
    - llm_predictor: BaseLLMPredictor
    - prompt_helper: PromptHelper
    - embed_model: BaseEmbedding
    - node_parser: NodeParser
    - llama_logger: LlamaLogger (deprecated)
    - callback_manager: CallbackManager

    """

    llm_predictor: BaseLLMPredictor
    prompt_helper: PromptHelper
    embed_model: BaseEmbedding
    node_parser: NodeParser
    llama_logger: LlamaLogger
    callback_manager: CallbackManager

    @classmethod
    def from_defaults(
        cls,
        llm_predictor: Optional[BaseLLMPredictor] = None,
        llm: Optional[LLMType] = None,
        prompt_helper: Optional[PromptHelper] = None,
        embed_model: Optional[BaseEmbedding] = None,
        node_parser: Optional[NodeParser] = None,
        llama_logger: Optional[LlamaLogger] = None,
        callback_manager: Optional[CallbackManager] = None,
        # node parser kwargs
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        # prompt helper kwargs
        context_window: Optional[int] = None,
        num_output: Optional[int] = None,
        # deprecated kwargs
        chunk_size_limit: Optional[int] = None,
        local=False,
    ) -> "ServiceContext":
        """Create a ServiceContext from defaults.
        If an argument is specified, then use the argument value provided for that
        parameter. If an argument is not specified, then use the default value.

        You can change the base defaults by setting llama_index.global_service_context
        to a ServiceContext object with your desired settings.

        Args:
            llm_predictor (Optional[BaseLLMPredictor]): LLMPredictor
            prompt_helper (Optional[PromptHelper]): PromptHelper
            embed_model (Optional[BaseEmbedding]): BaseEmbedding
            node_parser (Optional[NodeParser]): NodeParser
            llama_logger (Optional[LlamaLogger]): LlamaLogger (deprecated)
            chunk_size (Optional[int]): chunk_size
            callback_manager (Optional[CallbackManager]): CallbackManager

        Deprecated Args:
            chunk_size_limit (Optional[int]): renamed to chunk_size

        """
        if chunk_size_limit is not None and chunk_size is None:
            logger.warning(
                "chunk_size_limit is deprecated, please specify chunk_size instead"
            )
            chunk_size = chunk_size_limit

        global default_service_context
        # Inherit from the global `default_service_context`
        if default_service_context is not None:
            return cls.from_service_context(
                default_service_context,
                llm_predictor=llm_predictor,
                prompt_helper=prompt_helper,
                embed_model=embed_model,
                node_parser=node_parser,
                llama_logger=llama_logger,
                callback_manager=callback_manager,
                chunk_size=chunk_size,
                chunk_size_limit=chunk_size_limit,
            )

        callback_manager = callback_manager or CallbackManager([])
        if llm is not None:
            if llm_predictor is not None:
                raise ValueError("Cannot specify both llm and llm_predictor")
            llm_predictor = LLMPredictor(llm=llm)
        llm_predictor = llm_predictor or LLMPredictor()
        llm_predictor.callback_manager = callback_manager

        # NOTE: the embed_model isn't used in all indices
        embed_model = embed_model or OpenAIEmbedding()
        embed_model.callback_manager = callback_manager

        prompt_helper = prompt_helper or _get_default_prompt_helper(
            llm_metadata=llm_predictor.metadata,
            context_window=context_window,
            num_output=num_output,
        )

        node_parser = node_parser or _get_default_node_parser(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            callback_manager=callback_manager,
        )

        llama_logger = llama_logger or LlamaLogger()

        return cls(
            llm_predictor=llm_predictor,
            embed_model=embed_model,
            prompt_helper=prompt_helper,
            node_parser=node_parser,
            llama_logger=llama_logger,  # deprecated
            callback_manager=callback_manager,
        )

    @classmethod
    def from_service_context(
        cls,
        service_context: "ServiceContext",
        llm_predictor: Optional[BaseLLMPredictor] = None,
        llm: Optional[BaseLanguageModel] = None,
        prompt_helper: Optional[PromptHelper] = None,
        embed_model: Optional[BaseEmbedding] = None,
        node_parser: Optional[NodeParser] = None,
        llama_logger: Optional[LlamaLogger] = None,
        callback_manager: Optional[CallbackManager] = None,
        # node parser kwargs
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        # prompt helper kwargs
        context_window: Optional[int] = None,
        num_output: Optional[int] = None,
        # deprecated kwargs
        chunk_size_limit: Optional[int] = None,
    ) -> "ServiceContext":
        """Instantiate a new service context using a previous as the defaults."""
        if chunk_size_limit is not None and chunk_size is None:
            logger.warning(
                "chunk_size_limit is deprecated, please specify chunk_size",
                DeprecationWarning,
            )
            chunk_size = chunk_size_limit

        callback_manager = callback_manager or service_context.callback_manager
        if llm is not None:
            if llm_predictor is not None:
                raise ValueError("Cannot specify both llm and llm_predictor")
            llm_predictor = LLMPredictor(llm=llm)

        llm_predictor = llm_predictor or service_context.llm_predictor
        llm_predictor.callback_manager = callback_manager

        # NOTE: the embed_model isn't used in all indices
        embed_model = embed_model or service_context.embed_model
        embed_model.callback_manager = callback_manager

        prompt_helper = prompt_helper or _get_default_prompt_helper(
            llm_metadata=llm_predictor.metadata,
            context_window=context_window,
            num_output=num_output,
        )

        node_parser = node_parser or service_context.node_parser
        if chunk_size is not None or chunk_overlap is not None:
            node_parser = _get_default_node_parser(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                callback_manager=callback_manager,
            )

        llama_logger = llama_logger or service_context.llama_logger

        return cls(
            llm_predictor=llm_predictor,
            embed_model=embed_model,
            prompt_helper=prompt_helper,
            node_parser=node_parser,
            llama_logger=llama_logger,  # deprecated
            callback_manager=callback_manager,
        )

    def set_global(self) -> "ServiceContext":
        """Sets this context as the default service context for all downstream services except
        when explicitly passed a service context.
        Changes made to this service context will affect all downstream services that depend upon it."""
        global global_service_context
        global_service_context = self
        return self

    @classmethod
    def get_global(cls) -> Optional["ServiceContext"]:
        """Get the global service context. Changes made to the global service context that is
        returned will affect all downstream services that depend upon it.
        The global service context is by default initialized to `ServiceContext.from_defaults()`."""
        global global_service_context
        return global_service_context

    @classmethod
    def set_global_to_none(cls):
        """Set the global service context. When new services are created without an explicit context, it will not
        will not utilize a global context, but instead instantiate a local service context via `from_defaults`."""
        global global_service_context
        global_service_context = None

    def set_to_global_default(self) -> "ServiceContext":
        """All calls to from_defaults will inherit from this service context, which is frozen."""
        global default_service_context
        default_service_context = deepcopy(self)
        return self

# Set the default service context as the global service context
ServiceContext.from_defaults().set_global()