"""Guideline evaluation."""
import logging
from typing import Any, Optional, Sequence, Union, cast

from llama_index import ServiceContext
from llama_index.output_parsers import PydanticOutputParser
from llama_index.bridge.pydantic import BaseModel, Field
from llama_index.evaluation.base import BaseEvaluator, EvaluationResult
from llama_index.prompts import BasePromptTemplate, PromptTemplate

logger = logging.getLogger(__name__)


DEFAULT_GUIDELINES = (
    "The response should fully answer the query.\n"
    "The response should avoid being vague or ambiguous.\n"
    "The response should be specific and use statistics or numbers when possible.\n"
)

DEFAULT_EVAL_TEMPLATE = PromptTemplate(
    "Here is the original query:\n"
    "Query: {query}\n"
    "Critique the following response based on the guidelines below:\n"
    "Response: {response}\n"
    "Guidelines: {guidelines}\n"
    "Now please provide constructive criticism in the following format:\n"
    "{format_instructions}"
)


class EvaluationData(BaseModel):
    passing: bool = Field(description="Whether the response passes the guidelines.")
    feedback: str = Field(
        description="The feedback for the response based on the guidelines."
    )


class GuidelineEvaluator(BaseEvaluator):
    """An evaluator which uses guidelines to evaluate a response.

    Args:
        service_context(ServiceContext): The service context to use for evaluation.
        guidelines(str): User-added guidelines to use for evaluation.
        eval_template(str): The template to use for evaluation.
    """

    def __init__(
        self,
        service_context: Optional[ServiceContext] = None,
        guidelines: Optional[str] = None,
        eval_template: Optional[Union[str, BasePromptTemplate]] = None,
    ) -> None:
        self._service_context = service_context or ServiceContext.from_defaults()
        self._guidelines = guidelines or DEFAULT_GUIDELINES

        self._eval_template: BasePromptTemplate
        if isinstance(eval_template, str):
            self._eval_template = PromptTemplate(eval_template)
        else:
            self._eval_template = eval_template or DEFAULT_EVAL_TEMPLATE

    def evaluate(
        self,
        query: Optional[str] = None,
        contexts: Optional[Sequence[str]] = None,
        response: Optional[str] = None,
        **kwargs: Any,
    ) -> EvaluationResult:
        """Evaluate the response for a query and an Evaluation."""
        del contexts  # Unused
        del kwargs  # Unused
        if query is None or response is None:
            raise ValueError("query and response must be provided")

        parser = PydanticOutputParser(output_cls=EvaluationData)
        format_instructions = parser.format_string
        logger.debug("prompt: %s", self._eval_template)
        logger.debug("query: %s", query)
        logger.debug("response: %s", response)
        logger.debug("guidelines: %s", self._guidelines)
        logger.debug("format_instructions: %s", format_instructions)
        eval_response = self._service_context.llm_predictor.predict(
            self._eval_template,
            query=query,
            response=response,
            guidelines=self._guidelines,
            format_instructions=format_instructions,
        )
        eval_data = parser.parse(eval_response)
        eval_data = cast(EvaluationData, eval_data)

        return EvaluationResult(
            query=query,
            response=response,
            passing=eval_data.passing,
            feedback=eval_data.feedback,
        )
