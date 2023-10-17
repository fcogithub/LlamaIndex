import logging
from typing import Any, List

import requests
from llama_index.embeddings.base import BaseEmbedding

logger = logging.getLogger(__name__)


class LLMRailsEmbeddings(BaseEmbedding):
    """LLMRails embedding models.

    This class provides an interface to generate embeddings using a model deployed
    in an LLMRails cluster. It requires a model_id of the model deployed in the cluster and api key you can obtain 
    from https://console.llmrails.com/api-keys.

    """  

    model_id: str
    api_key: str

    @classmethod
    def class_name(self) -> str:
        return "LLMRailsEmbeddings"

    def __init__(
        self,
        api_key: str,
        model_id: str = 'embedding-english-v1', # or embedding-multi-v1
        **kwargs: Any,
    ):
        super().__init__(model_id=model_id, api_key=api_key, **kwargs)

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for a single query text.

        Args:
            text (str): The query text to generate an embedding for.

        Returns:
            List[float]: The embedding for the input query text.
        """
        try:
            response = requests.post('https://api.llmrails.com/v1/embeddings',
                headers={'X-API-KEY': self.api_key},
                json={
                    'input':[text],
                    'model':self.model_id
                }
            )

            response.raise_for_status()
            return response.json()['data'][0]['embedding']
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error while embedding text {e}.")
            raise ValueError(f"Unable to embed given text {e}")

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)
