"""Default query for GPTSimpleVectorIndex."""
from typing import Any, List, Optional, cast

import numpy as np

from gpt_index.embeddings.openai import OpenAIEmbedding
from gpt_index.indices.data_structs import IndexDict, Node
from gpt_index.indices.query.base import BaseGPTIndexQuery
from gpt_index.indices.response.builder import ResponseBuilder
from gpt_index.indices.utils import truncate_text
from gpt_index.prompts.default_prompts import (
    DEFAULT_REFINE_PROMPT,
    DEFAULT_TEXT_QA_PROMPT,
)
from gpt_index.indices.query.vector_store.base import BaseGPTVectorStoreIndexQuery
from gpt_index.prompts.prompts import QuestionAnswerPrompt, RefinePrompt


class GPTSimpleVectorIndexQuery(BaseGPTVectorStoreIndexQuery):
    """GPTSimpleVectorIndex query.

    An embedding-based query for GPTSimpleVectorIndex, which queries
    an underlying dict-based embedding store to retrieve top-k nodes by
    embedding similarity to the query.

    .. code-block:: python

        response = index.query("<query_str>", mode="default")

    Args:
        text_qa_template (Optional[QuestionAnswerPrompt]): Question-Answer Prompt
            (see :ref:`Prompt-Templates`).
        refine_template (Optional[RefinePrompt]): Refinement Prompt
            (see :ref:`Prompt-Templates`).
        embed_model (Optional[OpenAIEmbedding]): Embedding model to use for
            embedding similarity.
        similarity_top_k (int): Number of similar nodes to retrieve.

    """

    def __init__(
        self,
        index_struct: IndexDict,
        text_qa_template: Optional[QuestionAnswerPrompt] = None,
        refine_template: Optional[RefinePrompt] = None,
        faiss_index: Optional[Any] = None,
        embed_model: Optional[OpenAIEmbedding] = None,
        similarity_top_k: Optional[int] = 1,
        **kwargs: Any,
    ) -> None:
        """Initialize params."""
        super().__init__(
            index_struct=index_struct, 
            text_qa_template=text_qa_template,
            refine_template=refine_template,
            embed_model=embed_model,
            similarity_top_k=similarity_top_k,
            **kwargs
        )
        if faiss_index is None:
            raise ValueError("faiss_index cannot be None.")
        # NOTE: cast to Any for now
        self._faiss_index = cast(Any, faiss_index)
        self._faiss_index = faiss_index

    def _give_response_for_nodes(
        self, query_str: str, nodes: List[Node], verbose: bool = False
    ) -> str:
        """Give response for nodes."""
        response_builder = ResponseBuilder(
            self._prompt_helper,
            self._llm_predictor,
            self.text_qa_template,
            self.refine_template,
        )
        for node in nodes:
            text = self._get_text_from_node(query_str, node, verbose=verbose)
            response_builder.add_text_chunks([text])
        response = response_builder.get_response(query_str, verbose=verbose)

        return response or ""

    def _get_nodes_for_response(
        self, query_str: str, verbose: bool = False
    ) -> List[Node]:
        """Get nodes for response."""
        query_embedding = self._embed_model.get_query_embedding(query_str)
        query_embedding_np = np.array(query_embedding)[np.newaxis, :]
        _, indices = self._faiss_index.search(query_embedding_np, self.similarity_top_k)
        # if empty, then return an empty response
        if len(indices) == 0:
            return []

        # returned dimension is 1 x k
        node_idxs = list([str(i) for i in indices[0]])
        top_k_nodes = self._index_struct.get_nodes(node_idxs)

        # print verbose output
        if verbose:
            fmt_txts = []
            for node_idx, node in zip(node_idxs, top_k_nodes):
                fmt_txt = f"> [Node {node_idx}] {truncate_text(node.get_text(), 100)}"
                fmt_txts.append(fmt_txt)
            top_k_node_text = "\n".join(fmt_txts)
            print(f"> Top {len(top_k_nodes)} nodes:\n{top_k_node_text}")
        return top_k_nodes

    def _query(self, query_str: str, verbose: bool = False) -> str:
        """Answer a query."""
        print(f"> Starting query: {query_str}")
        nodes = self._get_nodes_for_response(query_str, verbose=verbose)
        return self._give_response_for_nodes(query_str, nodes, verbose=verbose)
