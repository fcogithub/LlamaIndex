import asyncio
import logging
from typing import Optional, Sequence

from langchain.input import get_color_mapping, print_text

from llama_index.async_utils import run_async_tasks
from llama_index.data_structs.node import Node, NodeWithScore
from llama_index.indices.query.base import BaseQueryEngine
from llama_index.indices.query.response_synthesis import ResponseSynthesizer
from llama_index.indices.query.schema import QueryBundle
from llama_index.question_gen.llm_generators import LLMQuestionGenerator
from llama_index.question_gen.types import BaseQuestionGenerator, SubQuestion
from llama_index.response.schema import RESPONSE_TYPE
from llama_index.tools.query_engine import QueryEngineTool

logger = logging.getLogger(__name__)


class SubQuestionQueryEngine(BaseQueryEngine):
    def __init__(
        self,
        question_gen: BaseQuestionGenerator,
        response_synthesizer: ResponseSynthesizer,
        query_engine_tools: Sequence[QueryEngineTool],
        verbose: bool = True,
        use_async: bool = True,
    ) -> None:
        self._question_gen = question_gen
        self._response_synthesizer = response_synthesizer
        self._metadatas = [x.metadata for x in query_engine_tools]
        self._query_engines = {
            tool.metadata.name: tool.query_engine for tool in query_engine_tools
        }
        self._verbose = verbose
        self._use_async = use_async

    @classmethod
    def from_defaults(
        cls,
        query_engine_tools: Sequence[QueryEngineTool],
        question_gen: Optional[BaseQuestionGenerator] = None,
        response_synthesizer: Optional[ResponseSynthesizer] = None,
        verbose: bool = True,
    ) -> "SubQuestionQueryEngine":
        question_gen = question_gen or LLMQuestionGenerator.from_defaults()
        synth = response_synthesizer or ResponseSynthesizer.from_args()

        return cls(question_gen, synth, query_engine_tools, verbose)

    def _query(self, query_bundle: QueryBundle) -> RESPONSE_TYPE:
        sub_questions = self._question_gen.generate(self._metadatas, query_bundle)

        if self._verbose:
            print_text(f"Generated {len(sub_questions)} sub questions.\n")
            colors = get_color_mapping([str(i) for i in range(len(sub_questions))])

        tasks = [
            self.aquery_subq(sub_q, color=colors[str(ind)])
            for ind, sub_q in enumerate(sub_questions)
        ]
        nodes = run_async_tasks(tasks)

        return self._response_synthesizer.synthesize(
            query_bundle=query_bundle,
            nodes=nodes,
        )

    async def _aquery(self, query_bundle: QueryBundle) -> RESPONSE_TYPE:
        sub_questions = await self._question_gen.agenerate(
            self._metadatas, query_bundle
        )

        if self._verbose:
            print_text(f"Generated {len(sub_questions)} sub questions.\n")
            colors = get_color_mapping([str(i) for i in range(len(sub_questions))])

        tasks = [
            self.aquery_subq(sub_q, color=colors[str(ind)])
            for ind, sub_q in enumerate(sub_questions)
        ]
        nodes = await asyncio.gather(*tasks)

        return await self._response_synthesizer.asynthesize(
            query_bundle=query_bundle,
            nodes=nodes,
        )

    async def aquery_subq(
        self, sub_q: SubQuestion, color: Optional[str] = None
    ) -> Optional[NodeWithScore]:
        try:
            question = sub_q.sub_question
            query_engine = self._query_engines[sub_q.tool_name]

            if self._verbose:
                print_text(f"[{sub_q.tool_name}] Q: {question}\n", color=color)

            response = await query_engine.aquery(question)
            response_text = str(response)
            node_text = f"Sub question: {question}\nResponse: {response_text}"

            if self._verbose:
                print_text(f"[{sub_q.tool_name}] A: {response_text}\n", color=color)

            return NodeWithScore(Node(text=node_text))
        except ValueError:
            logger.warn(f"[{sub_q.tool_name}] Failed to run {question}")
            return None
