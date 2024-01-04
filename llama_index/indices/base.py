"""Base index classes."""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar, cast

import unique_names_generator as ung

from llama_index.chat_engine.types import BaseChatEngine, ChatMode
from llama_index.core import BaseQueryEngine, BaseRetriever
from llama_index.data_structs.data_structs import IndexStruct
from llama_index.embeddings.base import BaseEmbedding
from llama_index.indices.base_retriever import BaseRetriever
from llama_index.indices.query.base import BaseQueryEngine
from llama_index.indices.service_context import ServiceContext
from llama_index.ingestion.pipeline import (
    DEFAULT_PROJECT_NAME,
    IngestionPipeline,
    run_transformations,
)
from llama_index.llms.openai import OpenAI
from llama_index.llms.openai_utils import is_function_calling_model
from llama_index.schema import BaseNode, Document
from llama_index.service_context import ServiceContext
from llama_index.storage.docstore.types import BaseDocumentStore, RefDocInfo
from llama_index.storage.storage_context import StorageContext

IS = TypeVar("IS", bound=IndexStruct)
IndexType = TypeVar("IndexType", bound="BaseIndex")

logger = logging.getLogger(__name__)


class BaseIndex(Generic[IS], ABC):
    """Base LlamaIndex.

    Args:
        nodes (List[Node]): List of nodes to index
        show_progress (bool): Whether to show tqdm progress bars. Defaults to False.
        service_context (ServiceContext): Service context container (contains
            components like LLM, Embeddings, etc.).

    """

    index_struct_cls: Type[IS]

    def __init__(
        self,
        nodes: Optional[Sequence[BaseNode]] = None,
        index_struct: Optional[IS] = None,
        storage_context: Optional[StorageContext] = None,
        service_context: Optional[ServiceContext] = None,
        show_progress: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize with parameters."""
        if index_struct is None and nodes is None:
            raise ValueError("One of nodes or index_struct must be provided.")
        if index_struct is not None and nodes is not None:
            raise ValueError("Only one of nodes or index_struct can be provided.")
        # This is to explicitly make sure that the old UX is not used
        if nodes is not None and len(nodes) >= 1 and not isinstance(nodes[0], BaseNode):
            if isinstance(nodes[0], Document):
                raise ValueError(
                    "The constructor now takes in a list of Node objects. "
                    "Since you are passing in a list of Document objects, "
                    "please use `from_documents` instead."
                )
            else:
                raise ValueError("nodes must be a list of Node objects.")

        self._service_context = service_context or ServiceContext.from_defaults()
        self._storage_context = storage_context or StorageContext.from_defaults()
        self._docstore = self._storage_context.docstore
        self._show_progress = show_progress
        self._vector_store = self._storage_context.vector_store
        self._graph_store = self._storage_context.graph_store

        with self._service_context.callback_manager.as_trace("index_construction"):
            if index_struct is None:
                assert nodes is not None
                index_struct = self.build_index_from_nodes(nodes)
            self._index_struct = index_struct
            self._storage_context.index_store.add_index_struct(self._index_struct)

    @classmethod
    def from_documents(
        cls: Type[IndexType],
        documents: Sequence[Document],
        storage_context: Optional[StorageContext] = None,
        service_context: Optional[ServiceContext] = None,
        show_progress: bool = False,
        from_pipeline_name: Optional[str] = None,
        remote_pipeline_name: Optional[str] = None,
        project_name: str = DEFAULT_PROJECT_NAME,
        **kwargs: Any,
    ) -> IndexType:
        """Create index from documents.

        Args:
            documents (Optional[Sequence[BaseDocument]]): List of documents to
                build the index from.

        """
        storage_context = storage_context or StorageContext.from_defaults()
        service_context = service_context or ServiceContext.from_defaults()
        docstore = storage_context.docstore

        with service_context.callback_manager.as_trace("index_construction"):
            for doc in documents:
                docstore.set_document_hash(doc.get_doc_id(), doc.hash)

            if from_pipeline_name is not None:
                pipeline = IngestionPipeline.from_pipeline_name(
                    from_pipeline_name,
                    project_name=project_name,
                    disable_cache=True,
                )
                service_context.transformations = pipeline.transformations
            else:
                pipeline = IngestionPipeline(
                    name=remote_pipeline_name
                    or ung.get_random_name(separator="-", style="lowercase"),
                    project_name=project_name,
                    transformations=service_context.transformations,
                    disable_cache=True,
                )

            # check for empty and false
            should_upload = (
                os.environ.get("PLATFORM_AUTO_UPLOAD", "false").lower() != "false"
            )

            if should_upload:
                # we should upload the embeddings, only if
                # they are not already in the pipeline
                print(
                    "Uploading a copy of the ingestion pipeline to the platform.",
                    flush=True,
                )
                embeddings_found = False
                for transformation in pipeline.transformations:
                    if isinstance(transformation, BaseEmbedding):
                        embeddings_found = True
                        break

                if not embeddings_found:
                    pipeline.transformations.append(service_context.embed_model)

                # Register the pipeline -- it will print the URL to the pipeline
                pipeline.register(documents=documents)  # type: ignore

                # remove the embeddings
                if embeddings_found:
                    pipeline.transformations.pop()

            nodes = pipeline.run(
                documents=documents,  # type: ignore
                show_progress=show_progress,
                **kwargs,
            )

            return cls(
                nodes=nodes,
                storage_context=storage_context,
                service_context=service_context,
                show_progress=show_progress,
                **kwargs,
            )

    @property
    def index_struct(self) -> IS:
        """Get the index struct."""
        return self._index_struct

    @property
    def index_id(self) -> str:
        """Get the index struct."""
        return self._index_struct.index_id

    def set_index_id(self, index_id: str) -> None:
        """Set the index id.

        NOTE: if you decide to set the index_id on the index_struct manually,
        you will need to explicitly call `add_index_struct` on the `index_store`
        to update the index store.

        .. code-block:: python
            index.index_struct.index_id = index_id
            index.storage_context.index_store.add_index_struct(index.index_struct)

        Args:
            index_id (str): Index id to set.

        """
        # delete the old index struct
        old_id = self._index_struct.index_id
        self._storage_context.index_store.delete_index_struct(old_id)
        # add the new index struct
        self._index_struct.index_id = index_id
        self._storage_context.index_store.add_index_struct(self._index_struct)

    @property
    def docstore(self) -> BaseDocumentStore:
        """Get the docstore corresponding to the index."""
        return self._docstore

    @property
    def service_context(self) -> ServiceContext:
        return self._service_context

    @property
    def storage_context(self) -> StorageContext:
        return self._storage_context

    @property
    def summary(self) -> str:
        return str(self._index_struct.summary)

    @summary.setter
    def summary(self, new_summary: str) -> None:
        self._index_struct.summary = new_summary
        self._storage_context.index_store.add_index_struct(self._index_struct)

    @abstractmethod
    def _build_index_from_nodes(self, nodes: Sequence[BaseNode]) -> IS:
        """Build the index from nodes."""

    def build_index_from_nodes(self, nodes: Sequence[BaseNode]) -> IS:
        """Build the index from nodes."""
        self._docstore.add_documents(nodes, allow_update=True)
        return self._build_index_from_nodes(nodes)

    @abstractmethod
    def _insert(self, nodes: Sequence[BaseNode], **insert_kwargs: Any) -> None:
        """Index-specific logic for inserting nodes to the index struct."""

    def insert_nodes(self, nodes: Sequence[BaseNode], **insert_kwargs: Any) -> None:
        """Insert nodes."""
        with self._service_context.callback_manager.as_trace("insert_nodes"):
            self.docstore.add_documents(nodes, allow_update=True)
            self._insert(nodes, **insert_kwargs)
            self._storage_context.index_store.add_index_struct(self._index_struct)

    def insert(self, document: Document, **insert_kwargs: Any) -> None:
        """Insert a document."""
        with self._service_context.callback_manager.as_trace("insert"):
            nodes = run_transformations(
                [document],
                self._service_context.transformations,
                show_progress=self._show_progress,
            )

            self.insert_nodes(nodes, **insert_kwargs)
            self.docstore.set_document_hash(document.get_doc_id(), document.hash)

    @abstractmethod
    def _delete_node(self, node_id: str, **delete_kwargs: Any) -> None:
        """Delete a node."""

    def delete_nodes(
        self,
        node_ids: List[str],
        delete_from_docstore: bool = False,
        **delete_kwargs: Any,
    ) -> None:
        """Delete a list of nodes from the index.

        Args:
            doc_ids (List[str]): A list of doc_ids from the nodes to delete

        """
        for node_id in node_ids:
            self._delete_node(node_id, **delete_kwargs)
            if delete_from_docstore:
                self.docstore.delete_document(node_id, raise_error=False)

        self._storage_context.index_store.add_index_struct(self._index_struct)

    def delete(self, doc_id: str, **delete_kwargs: Any) -> None:
        """Delete a document from the index.
        All nodes in the index related to the index will be deleted.

        Args:
            doc_id (str): A doc_id of the ingested document

        """
        logger.warning(
            "delete() is now deprecated, please refer to delete_ref_doc() to delete "
            "ingested documents+nodes or delete_nodes to delete a list of nodes."
        )
        self.delete_ref_doc(doc_id)

    def delete_ref_doc(
        self, ref_doc_id: str, delete_from_docstore: bool = False, **delete_kwargs: Any
    ) -> None:
        """Delete a document and it's nodes by using ref_doc_id."""
        ref_doc_info = self.docstore.get_ref_doc_info(ref_doc_id)
        if ref_doc_info is None:
            logger.warning(f"ref_doc_id {ref_doc_id} not found, nothing deleted.")
            return

        self.delete_nodes(
            ref_doc_info.node_ids,
            delete_from_docstore=False,
            **delete_kwargs,
        )

        if delete_from_docstore:
            self.docstore.delete_ref_doc(ref_doc_id, raise_error=False)

    def update(self, document: Document, **update_kwargs: Any) -> None:
        """Update a document and it's corresponding nodes.

        This is equivalent to deleting the document and then inserting it again.

        Args:
            document (Union[BaseDocument, BaseIndex]): document to update
            insert_kwargs (Dict): kwargs to pass to insert
            delete_kwargs (Dict): kwargs to pass to delete

        """
        logger.warning(
            "update() is now deprecated, please refer to update_ref_doc() to update "
            "ingested documents+nodes."
        )
        self.update_ref_doc(document, **update_kwargs)

    def update_ref_doc(self, document: Document, **update_kwargs: Any) -> None:
        """Update a document and it's corresponding nodes.

        This is equivalent to deleting the document and then inserting it again.

        Args:
            document (Union[BaseDocument, BaseIndex]): document to update
            insert_kwargs (Dict): kwargs to pass to insert
            delete_kwargs (Dict): kwargs to pass to delete

        """
        with self._service_context.callback_manager.as_trace("update"):
            self.delete_ref_doc(
                document.get_doc_id(),
                delete_from_docstore=True,
                **update_kwargs.pop("delete_kwargs", {}),
            )
            self.insert(document, **update_kwargs.pop("insert_kwargs", {}))

    def refresh(
        self, documents: Sequence[Document], **update_kwargs: Any
    ) -> List[bool]:
        """Refresh an index with documents that have changed.

        This allows users to save LLM and Embedding model calls, while only
        updating documents that have any changes in text or metadata. It
        will also insert any documents that previously were not stored.
        """
        logger.warning(
            "refresh() is now deprecated, please refer to refresh_ref_docs() to "
            "refresh ingested documents+nodes with an updated list of documents."
        )
        return self.refresh_ref_docs(documents, **update_kwargs)

    def refresh_ref_docs(
        self, documents: Sequence[Document], **update_kwargs: Any
    ) -> List[bool]:
        """Refresh an index with documents that have changed.

        This allows users to save LLM and Embedding model calls, while only
        updating documents that have any changes in text or metadata. It
        will also insert any documents that previously were not stored.
        """
        with self._service_context.callback_manager.as_trace("refresh"):
            refreshed_documents = [False] * len(documents)
            for i, document in enumerate(documents):
                existing_doc_hash = self._docstore.get_document_hash(
                    document.get_doc_id()
                )
                if existing_doc_hash is None:
                    self.insert(document, **update_kwargs.pop("insert_kwargs", {}))
                    refreshed_documents[i] = True
                elif existing_doc_hash != document.hash:
                    self.update_ref_doc(
                        document, **update_kwargs.pop("update_kwargs", {})
                    )
                    refreshed_documents[i] = True

            return refreshed_documents

    @property
    @abstractmethod
    def ref_doc_info(self) -> Dict[str, RefDocInfo]:
        """Retrieve a dict mapping of ingested documents and their nodes+metadata."""
        ...

    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        ...

    def as_query_engine(self, **kwargs: Any) -> BaseQueryEngine:
        # NOTE: lazy import
        from llama_index.query_engine.retriever_query_engine import RetrieverQueryEngine

        retriever = self.as_retriever(**kwargs)

        kwargs["retriever"] = retriever
        if "service_context" not in kwargs:
            kwargs["service_context"] = self._service_context
        return RetrieverQueryEngine.from_args(**kwargs)

    def as_chat_engine(
        self, chat_mode: ChatMode = ChatMode.BEST, **kwargs: Any
    ) -> BaseChatEngine:
        query_engine = self.as_query_engine(**kwargs)
        if "service_context" not in kwargs:
            kwargs["service_context"] = self._service_context

        # resolve chat mode
        if chat_mode == ChatMode.BEST:
            # get LLM
            service_context = cast(ServiceContext, kwargs["service_context"])
            llm = service_context.llm

            if isinstance(llm, OpenAI) and is_function_calling_model(llm.model):
                chat_mode = ChatMode.OPENAI
            else:
                chat_mode = ChatMode.REACT

        if chat_mode == ChatMode.CONDENSE_QUESTION:
            # NOTE: lazy import
            from llama_index.chat_engine import CondenseQuestionChatEngine

            return CondenseQuestionChatEngine.from_defaults(
                query_engine=query_engine,
                **kwargs,
            )
        elif chat_mode == ChatMode.CONTEXT:
            from llama_index.chat_engine import ContextChatEngine

            return ContextChatEngine.from_defaults(
                retriever=self.as_retriever(**kwargs),
                **kwargs,
            )

        elif chat_mode == ChatMode.CONDENSE_PLUS_CONTEXT:
            from llama_index.chat_engine import CondensePlusContextChatEngine

            return CondensePlusContextChatEngine.from_defaults(
                retriever=self.as_retriever(**kwargs),
                **kwargs,
            )

        elif chat_mode in [ChatMode.REACT, ChatMode.OPENAI]:
            # NOTE: lazy import
            from llama_index.agent import OpenAIAgent, ReActAgent
            from llama_index.tools.query_engine import QueryEngineTool

            # convert query engine to tool
            query_engine_tool = QueryEngineTool.from_defaults(query_engine=query_engine)

            # get LLM
            service_context = cast(ServiceContext, kwargs.pop("service_context"))
            llm = service_context.llm

            if chat_mode == ChatMode.REACT:
                return ReActAgent.from_tools(
                    tools=[query_engine_tool],
                    llm=llm,
                    **kwargs,
                )
            elif chat_mode == ChatMode.OPENAI:
                return OpenAIAgent.from_tools(
                    tools=[query_engine_tool],
                    llm=llm,
                    **kwargs,
                )
            else:
                raise ValueError(f"Unknown chat mode: {chat_mode}")
        elif chat_mode == ChatMode.SIMPLE:
            from llama_index.chat_engine import SimpleChatEngine

            return SimpleChatEngine.from_defaults(
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown chat mode: {chat_mode}")


# legacy
BaseGPTIndex = BaseIndex
