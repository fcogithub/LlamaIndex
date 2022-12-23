"""Response builder class.

This class provides general functions for taking in a set of text 
and generating a response.

Will support different modes, from 1) stuffing chunks into prompt,
2) create and refine separately over each chunk, 3) tree summarization.

"""

from gpt_index.indices.prompt_helper import PromptHelper
from gpt_index.indices.utils import truncate_text
from gpt_index.indices.prompt_helper import PromptHelper
from gpt_index.langchain_helpers.chain_wrapper import LLMPredictor
from enum import Enum
from gpt_index.prompts.prompts import QuestionAnswerPrompt, RefinePrompt
from gpt_index.indices.response.utils import give_response, refine_response
from typing import List, Optional


class ResponseMode(str, Enum):
    """Response modes."""
    DEFAULT = "default"
    COMPACT = "compact"
    TREE_SUMMARIZE = "tree_summarize"


class ResponseBuilder:
    """Response builder class."""

    def __init__(
        self, 
        prompt_helper: PromptHelper, 
        llm_predictor: LLMPredictor,
        text_qa_template: QuestionAnswerPrompt,
        refine_template: RefinePrompt,
        texts: List[str] = None,
    ) -> None:
        """Init params."""
        self.prompt_helper = prompt_helper
        self.llm_predictor = llm_predictor
        self.text_qa_template = text_qa_template
        self.refine_template = refine_template
        self._texts = texts or []

    def add_text_chunks(self, text_chunks: List[str]) -> None:
        """Add text chunk."""
        self._texts.extend(text_chunks)

    def refine_response_single(
        self,
        response: str,
        query_str: str,
        text_chunk: str,
        verbose: bool = False,
    ) -> str:
        """Refine response."""
        fmt_text_chunk = truncate_text(text_chunk, 50)
        if verbose:
            print(f"> Refine context: {fmt_text_chunk}")
        refine_text_splitter = self.prompt_helper.get_text_splitter_given_prompt(
            self.refine_template, 1
        )
        text_chunks = refine_text_splitter.split_text(text_chunk)
        for cur_text_chunk in text_chunks:
            response, _ = self.llm_predictor.predict(
                self.refine_template,
                query_str=query_str,
                existing_answer=response,
                context_msg=cur_text_chunk,
            )
            if verbose:
                print(f"> Refined response: {response}")
        return response


    def give_response_single(
        self,
        query_str: str,
        text_chunk: str,
        verbose: bool = False,
    ) -> str:
        """Give response given a query and a corresponding text chunk."""
        qa_text_splitter = self.prompt_helper.get_text_splitter_given_prompt(self.text_qa_template, 1)
        text_chunks = qa_text_splitter.split_text(text_chunk)
        response = None
        # TODO: consolidate with loop in get_response_default
        for cur_text_chunk in text_chunks:
            if response is None:
                response, _ = self.llm_predictor.predict(
                    self.text_qa_template, query_str=query_str, context_str=cur_text_chunk
                )
                if verbose:
                    print(f"> Initial response: {response}")
            else:
                response = self.refine_response_single(
                    response,
                    query_str,
                    cur_text_chunk,
                    verbose=verbose,
                )
        return response or ""


    def get_response_over_chunks(
        self, query_str: str, text_chunks: List[str], prev_response: Optional[str] = None, 
        verbose: bool = False
    ) -> str:
        """Give response over chunks."""
        for text_chunk in text_chunks:
            if prev_response is None:
                response = self.give_response_single(
                    query_str,
                    text_chunk,
                    verbose=verbose,
                )
            else:
                response = self.refine_response_single(
                    prev_response,
                    query_str,
                    text_chunk,
                    verbose=verbose
                )
        return response

    def _get_response_default(self, query_str: str, prev_response: Optional[str], verbose: bool = False) -> str:
        return self.get_response_over_chunks(
            query_str, self._texts, prev_response=prev_response, verbose=verbose
        )

    def _get_response_compact(self, query_str: str, prev_response: Optional[str], verbose: bool = False) -> str:
        """Get compact response."""
        # use prompt helper to fix compact text_chunks under the prompt limitation
        new_text_chunks = self.prompt_helper.compact_text_chunks(self._texts)
        return self.get_response_over_chunks(query_str, new_text_chunks, prev_response=prev_response, verbose=verbose)

    def _get_response_tree_summarize(self, query_str: str, prev_response: Optional[str], verbose: bool = False) -> str:
        """Get tree summarize response."""
        raise NotImplementedError

    def get_response(
        self, 
        query_str: str, 
        prev_response: Optional[str] = None,
        mode: ResponseMode = ResponseMode.DEFAULT, 
        verbose: bool = False
    ) -> str:
        """Get response."""
        if mode == ResponseMode.DEFAULT:
            return self._get_response_default(query_str, prev_response, verbose=verbose)
        elif mode == ResponseMode.COMPACT:
            return self._get_response_compact(query_str, prev_response, verbose=verbose)
        elif mode == ResponseMode.TREE_SUMMARIZE:
            return self._get_response_tree_summarize(query_str, prev_response, verbose=verbose)
        else:
            raise ValueError(f"Invalid mode: {mode}")

    