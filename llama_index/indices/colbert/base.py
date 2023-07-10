from typing import Any, List, Optional, Sequence, Dict

from llama_index.data_structs.data_structs import IndexDict
from llama_index.indices.base_retriever import BaseRetriever
from llama_index.indices.service_context import ServiceContext
from llama_index.storage.storage_context import StorageContext
from llama_index.indices.base import BaseIndex
from llama_index.storage.docstore.types import RefDocInfo
from llama_index.schema import BaseNode, NodeWithScore

# Only implement __init__, _build_index_from_nodes,
# _insert/_delete (NotImplementedError), ref_doc_info??


class ColbertIndex(BaseIndex[IndexDict]):
    """
    Store for ColBERT v2 with PLAID indexing.

    Parameters:

    index_path: directory containing PLAID index files.
    checkpoint_path: directory containing ColBERT checkpoint model files.
    collection_path: a csv/tsv data file of the form (id,content), no header line.

    create: whether to create a new index or load an index from disk. Default: False.

    nbits: number of bits to quantize the residual vectors. Default: 2.
    kmeans_niters: number of kmeans clustering iterations. Default: 1.
    gpus: number of GPUs to use for indexing. Default: 0.
    rank: number of ranks to use for indexing. Default: 1.
    doc_maxlen: max document length. Default: 120.
    query_maxlen: max query length. Default: 60.

    """

    def __init__(
        self,
        nodes: Optional[Sequence[BaseNode]] = None,
        index_struct: Optional[IndexDict] = None,
        service_context: Optional[ServiceContext] = None,
        storage_context: Optional[StorageContext] = None,
        use_async: bool = False,
        model_name: str = "colbert-ir/colbertv2.0",
        store_nodes_override: bool = False,
        show_progress: bool = False,
        nbits: int = 2,
        gpus: int = 0,
        ranks: int = 1,
        doc_maxlen: int = 120,
        query_maxlen: int = 60,
        kmeans_niters: int = 4,
        **kwargs: Any,
    ) -> None:
        self.model_name = model_name
        self.index_path = "storage/colbert_index"
        self.nbits = nbits
        self.gpus = gpus
        self.ranks = ranks
        self.doc_maxlen = doc_maxlen
        self.query_maxlen = query_maxlen
        self.kmeans_niters = kmeans_niters
        self._docs_pos_to_node_id: Dict[int, str] = {}
        super().__init__(
            nodes=nodes,
            index_struct=index_struct,
            service_context=service_context,
            storage_context=storage_context,
            show_progress=show_progress,
            **kwargs,
        )

    def _insert(self, nodes: Sequence[BaseNode], **insert_kwargs: Any) -> None:
        raise NotImplementedError("ColbertStoreIndex does not support insertion yet.")

    def _delete_node(self, node_id: str, **delete_kwargs: Any) -> None:
        raise NotImplementedError("ColbertStoreIndex does not support deletion yet.")

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        from llama_index.indices.colbert.retriever import ColbertRetriever

        return ColbertRetriever(index=self, **kwargs)

    @property
    def ref_doc_info(self) -> Dict[str, RefDocInfo]:
        raise NotImplementedError("ColbertStoreIndex does not support ref_doc_info.")

    def _build_index_from_nodes(self, nodes: Sequence[BaseNode]) -> IndexDict:
        """Generate a PLAID index from the ColBERT checkpoint via its hugging face
        model_name.

        """

        from colbert import Indexer, Searcher
        from colbert.infra import ColBERTConfig, Run, RunConfig

        index_struct = IndexDict()

        docs_list = []
        for i, node in enumerate(nodes):
            docs_list.append(node.get_content())
            self._docs_pos_to_node_id[i] = node.node_id
            index_struct.add_node(node, text_id=str(i))

        with Run().context(
            RunConfig(index_root=self.index_path, nranks=self.ranks, gpus=self.gpus)
        ):
            config = ColBERTConfig(
                doc_maxlen=self.doc_maxlen,
                query_maxlen=self.query_maxlen,
                nbits=self.nbits,
                kmeans_niters=self.kmeans_niters,
            )
            indexer = Indexer(checkpoint=self.model_name, config=config)
            indexer.index("", collection=docs_list, overwrite=True)
            self.store = Searcher(
                index="", collection=docs_list, checkpoint=self.model_name
            )

        return index_struct

    # @staticmethod
    # def _normalize_scores(docs: List[Document]) -> None:
    #     "Normalizing the MaxSim scores using softmax."
    #     Z = sum(math.exp(doc.score) for doc in docs)
    #     for doc in docs:
    #         doc.score = math.exp(doc.score) / Z

    def query(self, query_str: str, top_k: int = 10) -> List[NodeWithScore]:
        """
        Query the Colbert v2 + Plaid store.

        Returns: list of NodeWithScore.
        """

        doc_ids, _, scores = self.store.search(text=query_str, k=top_k)

        node_doc_ids = list(map(lambda id: self._docs_pos_to_node_id[id], doc_ids))
        nodes = self.docstore.get_nodes(node_doc_ids)

        nodes_with_score = []

        for node, score in zip(nodes, scores):
            nodes_with_score.append(NodeWithScore(node=node, score=score))

        return nodes_with_score
