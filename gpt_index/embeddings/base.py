"""Base embeddings file."""

from abc import abstractmethod
from typing import List, Optional, Callable
from gpt_index.utils import globals_helper

import numpy as np

# TODO: change to numpy array
EMB_TYPE = List


class BaseEmbedding:
    """Base class for embeddings."""
    def __init__(self) -> None:
        self._total_tokens_used = 0
        self._last_token_usage: Optional[int] = None
        self._tokenizer: Callable = globals_helper.tokenizer

    @abstractmethod
    def _get_query_embedding(self, query: str) -> List[float]:
        """Get query embedding."""

    def get_query_embedding(self, query: str) -> List[float]:
        """Get query embedding."""
        query_embedding = self._get_query_embedding(query)
        query_tokens_count = len(self._tokenizer(query))
        self._total_tokens_used += query_tokens_count
        return query_embedding

    @abstractmethod
    def _get_text_embedding(self, text: str) -> List[float]:
        """Get text embedding."""

    def get_text_embedding(self, text: str) -> List[float]:
        """Get text embedding."""
        text_embedding = self._get_text_embedding(text)
        text_tokens_count = len(self._tokenizer(text))
        self._total_tokens_used += text_tokens_count
        return text_embedding

    def similarity(self, embedding1: EMB_TYPE, embedding2: EMB_TYPE) -> float:
        """Get embedding similarity."""
        product = np.dot(embedding1, embedding2)
        norm = np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        return product / norm
