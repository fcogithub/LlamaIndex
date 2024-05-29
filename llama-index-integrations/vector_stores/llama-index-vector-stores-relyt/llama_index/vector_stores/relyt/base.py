import logging
from typing import Any, List, Sequence

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
    FilterCondition,
    MetadataFilters,
    FilterOperator,
)
from llama_index.core.vector_stores.utils import (
    metadata_dict_to_node,
    node_to_metadata_dict,
)

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text, TEXT, Table, Column, String, create_engine, Engine, insert

logger = logging.getLogger(__name__)
import_err_msg = (
    '`pgvecto_rs.sdk` package not found, please run `pip install "pgvecto_rs[sdk]"`'
)

Base = declarative_base()  # type: Any


class RelytVectorStore(BasePydanticVectorStore):
    """Relyt Vector Store.

    Examples:
        `pip install llama-index-vector-stores-relyt`

        ```python
        from llama_index.vector_stores.relyt import RelytVectorStore

        # Setup relyt client
        from pgvecto_rs.sdk import PGVectoRs
        import os

        URL = "postgresql+psycopg://{username}:{password}@{host}:{port}/{db_name}".format(
            port=os.getenv("RELYT_PORT", "5432"),
            host=os.getenv("RELYT_HOST", "localhost"),
            username=os.getenv("RELYT_USER", "postgres"),
            password=os.getenv("RELYT_PASS", "mysecretpassword"),
            db_name=os.getenv("RELYT_NAME", "postgres"),
        )

        client = PGVectoRs(
            db_url=URL,
            collection_name="example",
            dimension=1536,  # Using OpenAI’s text-embedding-ada-002
        )

        # Initialize RelytVectorStore
        vector_store = RelytVectorStore(client=client)
        ```
    """

    stores_text = True

    _client: Engine = PrivateAttr()
    _collection_name: str = PrivateAttr()
    _enable_vector_index: bool = PrivateAttr()
    _dimension: int = PrivateAttr()

    def __init__(
        self,
        connection_url: str,
        collection_name: str,
        dimension: int,
        addition_columns: dict = None,
        enable_vector_index: bool = False,
    ) -> None:
        self._client = create_engine(connection_url)
        self._collection_name = collection_name
        self._dimension = dimension
        self._enable_vector_index = enable_vector_index
        self.init_table(addition_columns)
        self.init_index(addition_columns)
        super().__init__()

    @classmethod
    def class_name(cls) -> str:
        return "RelytStore"

    def init_table(self, addition_columns: dict) -> None:
        with self._client.connect() as conn:
            with conn.begin():
                table_query = text(
                    f"""
                        SELECT 1
                        FROM pg_class
                        WHERE relname = '{self._collection_name}';
                    """
                )
                result = conn.execute(table_query).scalar()
                if not result:
                    table_statement = text(
                        f"""
                            CREATE TABLE {self._collection_name} (
                                id TEXT not null DEFAULT (md5(random()::text || clock_timestamp()::text)::uuid),
                                collection_id text not null,
                                embedding vector({self._dimension}),
                                text TEXT,
                                meta JSONB,
                                primary key (collection_id, id)
                            ) distributed by (id) partition by range(collection_id);
                        """
                    )
                    conn.execute(table_statement)
                    conn.execute(
                        text(
                            f"create table {self._collection_name}_part_default partition of {self._collection_name} default;"
                        )
                    )
                    conn.execute(
                        text(
                            f"alter table {self._collection_name} alter column id set storage plain"
                        )
                    )
                    conn.execute(
                        text(
                            f"alter table {self._collection_name} alter column collection_id set storage plain"
                        )
                    )
                    conn.execute(
                        text(
                            f"alter table {self._collection_name} alter column embedding set storage plain"
                        )
                    )
                    conn.execute(
                        text(
                            f"alter table {self._collection_name} alter column text set storage plain"
                        )
                    )
                    conn.execute(
                        text(
                            f"alter table {self._collection_name} alter column meta set storage plain"
                        )
                    )
                    if addition_columns is not None:
                        alter_statement = f"ALTER TABLE {self._collection_name} "
                        for column in addition_columns:
                            type = addition_columns[column]
                            conn.execute(
                                text(
                                    alter_statement
                                    + f"ADD COLUMN {column} {type} GENERATED ALWAYS AS (meta->>'{column}') STORED;"
                                )
                            )
                            conn.execute(
                                text(
                                    f"alter table {self._collection_name} alter column {column} set storage plain"
                                )
                            )

    def init_index(self, addition_columns: dict) -> None:
        index_name = f"idx_{self._collection_name}_embedding"
        with self._client.connect() as conn:
            with conn.begin():
                index_query = text(
                    f"""
                        SELECT 1
                        FROM pg_indexes
                        WHERE indexname = '{index_name}';
                    """
                )
                result = conn.execute(index_query).scalar()
                if not result and self._enable_vector_index:
                    index_statement = text(
                        f"""
                            CREATE INDEX {index_name}
                            ON {self._collection_name}
                            USING vectors (embedding vector_l2_ops)
                            WITH (options = $$
                            optimizing.optimizing_threads = 10
                            segment.max_growing_segment_size = 2000
                            segment.max_sealed_segment_size = 30000000
                            [indexing.hnsw]
                            m=30
                            ef_construction=500
                            $$);
                        """
                    )
                    conn.execute(index_statement)
                index_name = f"meta_{self._collection_name}_embedding"
                index_query = text(
                    f"""
                        SELECT 1
                        FROM pg_indexes
                        WHERE indexname = '{index_name}';
                    """
                )
                result = conn.execute(index_query).scalar()
                if not result:
                    index_statement = text(
                        f""" CREATE INDEX {index_name} ON {self._collection_name} USING gin (meta); """
                    )
                    conn.execute(index_statement)
                    if addition_columns is not None:
                        for column in addition_columns:
                            column_index_statement = f" CREATE INDEX {self._collection_name}_{column} ON {self._collection_name} USING btree ({column}); "
                            conn.execute(text(column_index_statement))

    @property
    def client(self) -> Any:
        return self._client

    def add(
        self,
        nodes: List[BaseNode],
    ) -> List[str]:
        from pgvecto_rs.sqlalchemy import Vector

        ids, content, embeddings, meta = zip(
            *[
                (
                    node.id_,
                    node.get_content(metadata_mode=MetadataMode.NONE),
                    node.get_embedding(),
                    node_to_metadata_dict(node, remove_text=True),
                )
                for node in nodes
            ]
        )

        collection_ids = []
        for metadata in meta:
            collection_ids.append(metadata["collection_id"])

            # Define the table schema
        chunks_table = Table(
            self._collection_name,
            Base.metadata,
            Column("id", TEXT, primary_key=True),
            Column("collection_id", TEXT, primary_key=True),
            Column("embedding", Vector(self._dimension)),
            Column("text", String, nullable=True),
            Column("meta", JSONB, nullable=True),
            extend_existing=True,
        )

        chunks_table_data = []
        with self._client.connect() as conn:
            with conn.begin():
                for document, metadata, chunk_id, embedding, collection_id in zip(
                    content, meta, ids, embeddings, collection_ids
                ):
                    chunks_table_data.append(
                        {
                            "id": chunk_id,
                            "collection_id": collection_id,
                            "embedding": embedding,
                            "text": document,
                            "meta": metadata,
                        }
                    )

                    # Execute the batch insert when the batch size is reached
                    if len(chunks_table_data) == 500:
                        conn.execute(insert(chunks_table).values(chunks_table_data))
                        # Clear the chunks_table_data list for the next batch
                        chunks_table_data.clear()

                # Insert any remaining records that didn't make up a full batch
                if chunks_table_data:
                    conn.execute(insert(chunks_table).values(chunks_table_data))

        return ids

    def delete(self, filters: str, **delete_kwargs: Any) -> None:
        if filters is None:
            raise ValueError("filters cannot be None")

        filter_condition = f"WHERE {filters}"

        with self._client.connect() as conn:
            with conn.begin():
                sql_query = (
                    f""" DELETE FROM {self._collection_name} {filter_condition}"""
                )
                conn.execute(text(sql_query))

    def drop(self) -> None:
        drop_statement = text(f"DROP TABLE IF EXISTS {self._collection_name};")
        with self._client.connect() as conn:
            with conn.begin():
                conn.execute(drop_statement)

    def to_postgres_operator(self, operator: FilterOperator) -> str:
        if operator == FilterOperator.EQ:
            return " = "
        elif operator == FilterOperator.GT:
            return " > "
        elif operator == FilterOperator.LT:
            return " < "
        elif operator == FilterOperator.NE:
            return " != "
        elif operator == FilterOperator.GTE:
            return " >= "
        elif operator == FilterOperator.LTE:
            return " <= "
        elif operator == FilterOperator.IN:
            return " in "
        return " = "

    def to_postgres_conditions(self, operator: FilterOperator) -> str:
        if operator == FilterCondition.AND:
            return " AND "
        elif operator == FilterCondition.OR:
            return " OR "
        return " AND "

    def transformer_filter(self, filters) -> str:
        filter_statement = ""
        for filter in filters.filters:
            if isinstance(filter, MetadataFilters):
                f_stmt = self.transformer_filter(filter)
                if filter_statement == "":
                    filter_statement = f_stmt
                else:
                    filter_statement += (
                        self.to_postgres_conditions(filter.condition) + f_stmt
                    )
            else:
                key = filter.key
                value = filter.value
                op = filter.operator
                if isinstance(value, str):
                    value = f"'{value}'"
                if op == FilterOperator.IN:
                    new_val = []
                    for v in value:
                        if isinstance(v, str):
                            new_val.append(f"'{v}'")
                        else:
                            new_val.append(str(v))
                    value = "(" + ",".join(new_val) + ")"
                filter_cond = key + self.to_postgres_operator(op) + value
                if filter_statement == "":
                    filter_statement = filter_cond
                else:
                    filter_statement += (
                        self.to_postgres_conditions(filters.condition) + filter_cond
                    )
        return filter_statement

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        # Add the filter if provided
        try:
            from sqlalchemy.engine import Row
        except ImportError:
            raise ImportError(
                "Could not import Row from sqlalchemy.engine. "
                "Please 'pip install sqlalchemy>=1.4'."
            )

        embedding = query.query_embedding
        k = query.similarity_top_k
        filter_condition = ""
        filters = query.filters

        if filters and filters.filters:
            filter_condition += f"WHERE {self.transformer_filter(filters)}"

        sql_query = f"""
                        SELECT id, text, meta, embedding <-> :embedding as distance
                        FROM {self._collection_name}
                        {filter_condition}
                        ORDER BY embedding <-> :embedding
                        LIMIT :k
                    """

        # Set up the query parameters
        embedding_str = ", ".join(format(x) for x in embedding)
        embedding_str = "[" + embedding_str + "]"
        params = {"embedding": embedding_str, "k": k}

        # Execute the query and fetch the results
        with self._client.connect() as conn:
            results: Sequence[Row] = conn.execute(text(sql_query), params).fetchall()

        nodes = [
            metadata_dict_to_node(reocrd.meta, text=reocrd.text) for reocrd in results
        ]

        return VectorStoreQueryResult(
            nodes=nodes,
            similarities=[r.distance for r in results],
            ids=[str(r.id) for r in results],
        )
