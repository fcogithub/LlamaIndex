
   
import logging
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
)

from langchain.input import print_text

from gpt_index.data_structs.node_v2 import Node, NodeWithScore
from gpt_index.indices.query.schema import QueryBundle
from gpt_index.indices.response.response_builder import (
    BaseResponseBuilder,
    BaseResponseBuilder,
    ResponseMode,
    get_response_builder,
)
from gpt_index.indices.service_context import ServiceContext
from gpt_index.optimization.optimizer import BaseTokenUsageOptimizer
from gpt_index.prompts.default_prompt_selectors import DEFAULT_REFINE_PROMPT_SEL
from gpt_index.prompts.default_prompts import DEFAULT_SIMPLE_INPUT_PROMPT, DEFAULT_TEXT_QA_PROMPT
from gpt_index.prompts.prompts import QuestionAnswerPrompt, RefinePrompt, SimpleInputPrompt
from gpt_index.response.schema import (
    RESPONSE_TYPE,
    Response,
    StreamingResponse,
)
from gpt_index.types import RESPONSE_TEXT_TYPE
from gpt_index.utils import truncate_text

logger = logging.getLogger(__name__)


class ResponseSynthesizer:
    def __init__(
        self, 
        response_builder: BaseResponseBuilder,
        response_mode: ResponseMode,
        response_kwargs: Optional[Dict] = None,
        optimizer: Optional[BaseTokenUsageOptimizer] = None,
        verbose: bool = False,
    ) -> None:
        self._response_builder = response_builder
        self._response_mode = response_mode
        self._response_kwargs = response_kwargs or {}
        self._optimizer = optimizer
        self._verbose = verbose

    @classmethod
    def from_args(
        cls,
        service_context:  ServiceContext, 
        streaming: bool, 
        use_async: bool,
        text_qa_template: Optional[QuestionAnswerPrompt] = None,
        refine_template: Optional[RefinePrompt] = None, 
        simple_template: Optional[SimpleInputPrompt] = None,
        response_mode: ResponseMode = ResponseMode.DEFAULT,
        response_kwargs: Optional[Dict] = None,
        optimizer: Optional[BaseTokenUsageOptimizer] = None,
    ) -> "ResponseSynthesizer":
        response_builder = get_response_builder(
            service_context,
            text_qa_template,
            refine_template,
            simple_template, 
            response_mode,
            use_async=use_async,
            streaming=streaming,

        )
        return cls(response_builder, response_mode, response_kwargs, optimizer)
    

    def _get_text_from_node(
        self,
        node: Node,
        level: Optional[int] = None,
    ) -> str:
        """Get text from node."""
        level_str = "" if level is None else f"[Level {level}]"
        fmt_text_chunk = truncate_text(node.get_text(), 50)
        logger.debug(f">{level_str} Searching in chunk: {fmt_text_chunk}")

        response_txt = node.get_text()
        fmt_response = truncate_text(response_txt, 200)
        if self._verbose:
            print_text(f">{level_str} Got node text: {fmt_response}\n", color="blue")
        return response_txt

    def _get_extra_info_for_response(
        self,
        nodes: List[Node],
    ) -> Optional[Dict[str, Any]]:
        """Get extra info for response."""
        return None

    def _prepare_response_output(
        self,
        response_str: Optional[RESPONSE_TEXT_TYPE],
        source_nodes: List[NodeWithScore],
    ) -> RESPONSE_TYPE:
        """Prepare response object from response string."""
        response_extra_info = self._get_extra_info_for_response(
            [node_with_score.node for node_with_score in source_nodes]
        )

        if response_str is None or isinstance(response_str, str):
            return Response(
                response_str,
                source_nodes=source_nodes,
                extra_info=response_extra_info,
            )
        elif response_str is None or isinstance(response_str, Generator):
            return StreamingResponse(
                response_str,
                source_nodes=source_nodes,
                extra_info=response_extra_info,
            )
        else:
            raise ValueError("Response must be a string or a generator.")

    def synthesize(
        self,
        query_bundle: QueryBundle,
        nodes: List[NodeWithScore],
        additional_source_nodes: Optional[List[NodeWithScore]] = None,
    ) -> RESPONSE_TYPE:
        text_chunks = []
        for node_with_score in nodes:
            text = self._get_text_from_node(node_with_score.node)
            if self._optimizer is not None:
                text = self._optimizer.optimize(query_bundle, text.text)
            text_chunks.append(text)

        if self._response_mode != ResponseMode.NO_TEXT:
            response_str = self._response_builder.get_response(
                query_str=query_bundle.query_str,
                text_chunks=text_chunks,
                **self._response_kwargs,
            )
        else:
            response_str = None
        
        additional_source_nodes = additional_source_nodes or []
        source_nodes = nodes + additional_source_nodes

        return self._prepare_response_output(response_str, source_nodes)

    async def asynthesize(
        self,
        query_bundle: QueryBundle,
        nodes: List[NodeWithScore],
        additional_source_nodes: Optional[List[NodeWithScore]] = None,
    ) -> RESPONSE_TYPE:
        text_chunks = []
        for node_with_score in nodes:
            text = self._get_text_from_node(node_with_score.node)
            if self._optimizer is not None:
                text = self._optimizer.optimize(query_bundle, text)
            text_chunks.append(text)

        if self._response_mode != ResponseMode.NO_TEXT:
            response_str = await self._response_builder.aget_response(
                query_str=query_bundle.query_str,
                text_chunks=text_chunks,
                **self._response_kwargs,
            )
        else:
            response_str = None

        additional_source_nodes = additional_source_nodes or []
        source_nodes = nodes + additional_source_nodes

        return self._prepare_response_output(response_str, source_nodes)
