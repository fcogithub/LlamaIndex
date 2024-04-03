import pytest
from unittest.mock import MagicMock, patch

from llama_index.core.vector_stores import VectorStoreQueryResult
from llama_index.vector_stores.wordlift import WordliftVectorStore


class MockNode:
    def __init__(self, node_id, embedding, content):
        self.node_id = node_id
        self._embedding = embedding
        self._content = content

    def dict(self):
        return {"metadata": {}, "entity_id": "123", "node_id": self.node_id}

    def get_embedding(self):
        return self._embedding

    def get_content(self, metadata_mode):
        return self._content


@pytest.fixture()
def mock_vector_search_service():
    return MagicMock()


@pytest.fixture()
def mock_key_provider():
    return MagicMock()


@pytest.fixture()
def wordlift_vector_store(mock_key_provider, mock_vector_search_service):
    return WordliftVectorStore(mock_key_provider, mock_vector_search_service)


def test_instance_creation(mock_key_provider, mock_vector_search_service) -> None:
    store = WordliftVectorStore(mock_key_provider, mock_vector_search_service)
    assert isinstance(store, WordliftVectorStore)


def test_instance_creation_create() -> None:
    store = WordliftVectorStore.create("dummy_key")
    assert isinstance(store, WordliftVectorStore)


# @pytest.mark.asyncio
def test_add_with_mocked_NodeRequest_and_VectorSearchQueryRequest(
    wordlift_vector_store,
):
    # Create mock node data
    mock_nodes = [
        MockNode(node_id="1", embedding=[0.1, 0.2, 0.3], content="Sample content 1"),
        MockNode(node_id="2", embedding=[0.4, 0.5, 0.6], content="Sample content 2"),
    ]

    # Mock the key provider behavior
    wordlift_vector_store.key_provider.for_add.return_value = "dummy_key"

    # Mock NodeRequest class
    with patch("manager_client.NodeRequest") as MockNodeRequest:
        # Configure the behavior of MockNodeRequest
        mock_requests = []
        for mock_node in mock_nodes:
            mock_node_request_instance = MockNodeRequest.return_value
            mock_node_request_instance.node_id = mock_node.node_id
            mock_node_request_instance.get_embedding = mock_node.get_embedding()
            mock_node_request_instance.get_content = mock_node.get_content(
                metadata_mode="dummy_mode"
            )

            mock_requests.append(mock_node_request_instance)

        # Call the add method
        result = wordlift_vector_store.add(mock_nodes)

        # Assert the behavior
        assert result == ["1", "2"]


@pytest.mark.xfail(raises=NotImplementedError)
def test_delete(wordlift_vector_store):
    wordlift_vector_store.delete("dummy_id")


# @pytest.mark.asyncio
async def test_query_with_mocked_VectorSearchQueryRequest(
    wordlift_vector_store, mock_vector_search_service
):
    # Mock the query data
    mock_query = MagicMock()
    mock_query.query_embedding = [0.1, 0.2, 0.3]
    mock_query.similarity_top_k = 10

    # Mock the key provider behavior
    wordlift_vector_store.key_provider.for_query.return_value = "dummy_key"

    # Mock VectorSearchQueryRequest class
    with patch(
        "manager_client.VectorSearchQueryRequest"
    ) as MockVectorSearchQueryRequest:
        # Configure the behavior of MockVectorSearchQueryRequest instance
        mock_request_instance = MockVectorSearchQueryRequest.return_value
        mock_request_instance.query_embedding = mock_query.query_embedding
        mock_request_instance.similarity_top_k = mock_query.similarity_top_k

        # Call the query method
        result = wordlift_vector_store.query(mock_query)

        # Assert the behavior
        assert isinstance(result, VectorStoreQueryResult)
