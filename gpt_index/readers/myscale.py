"""MyScale reader."""
import json
import logging
from typing import Any, Dict, List, Optional

from gpt_index.readers.base import BaseReader
from gpt_index.readers.schema.base import Document

logger = logging.getLogger(__name__)

BS = "\\"
must_escape = (BS, "'")
escape_str = (
    lambda value: "".join(f"{BS}{c}" if c in must_escape else c for c in value)
    if value
    else ""
)
format_list_to_string = lambda list: "[" + ",".join(str(item) for item in list) + "]"


class MyScaleSettings:
    """MyScale Client Configuration

    Attribute:
        table (str) : Table name to operate on.
        database (str) : Database name to find the table.
        index_type (str): index type string
        metric (str) : metric type to compute distance
        batch_size (int): the size of documents to insert
        index_params (dict, optional): index build parameter
        search_params (dict, optional): index search parameters for MyScale query
    """

    def __init__(
        self,
        table: str,
        database: str,
        index_type: str,
        metric: str,
        batch_size: int,
        index_params: Optional[dict] = None,
        search_params: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        self.table = table
        self.database = database
        self.index_type = index_type
        self.metric = metric
        self.batch_size = batch_size
        self.index_params = index_params
        self.search_params = search_params

    def build_query_statement(
        self,
        query_embed: List[float],
        where_str: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        query_embed_str = format_list_to_string(query_embed)
        where_str = f"PREWHERE {where_str}" if where_str else ""
        order = "DESC" if self.metric.lower() == "ip" else "ASC"

        search_params_str = (
            (
                "("
                + ",".join([f"'{k}={v}'" for k, v in self.search_params.items()])
                + ")"
            )
            if self.search_params
            else ""
        )

        query_statement = f"""
            SELECT id, doc_id, text, node_info, extra_info, distance{search_params_str}(vector, {query_embed_str}) AS dist
            FROM {self.database}.{self.table} {where_str}
            ORDER BY dist {order}
            LIMIT {limit}
            """
        return query_statement


class MyscaleReader(BaseReader):
    """MyScale reader.

    Args:
        myscale_host (str) : An URL to connect to MyScale backend.
        username (str) : Usernamed to login.
        password (str) : Password to login.
        myscale_port (int) : URL port to connect with HTTP. Defaults to 8443.
        database (str) : Database name to find the table. Defaults to 'default'.
        table (str) : Table name to operate on. Defaults to 'vector_table'.
        index_type (str): index type string. Default to "IVFLAT"
        metric (str) : Metric to compute distance, supported are ('l2', 'cosine', 'ip'). Defaults to 'cosine'
        index_param (dict): index build parameter. Default to None

    """

    def __init__(
        self,
        myscale_host: str,
        username: str,
        password: str,
        myscale_port: Optional[int] = 8443,
        database: str = "default",
        table: str = "llama_index",
        index_type: str = "IVFLAT",
        metric: str = "cosine",
        index_params: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize params."""
        import_err_msg = "`clickhouse_connect` package not found, please run `pip install clickhouse-connect`"
        try:
            import clickhouse_connect  # noqa: F401
        except ImportError:
            raise ImportError(import_err_msg)

        self.client = clickhouse_connect.get_client(
            host=myscale_host,
            port=myscale_port,
            username=username,
            password=password,
        )

        self.config = MyScaleSettings(
            table=table,
            database=database,
            index_type=index_type,
            metric=metric,
            index_params=index_params,
            **kwargs,
        )

    def load_data(
        self,
        query_vector: List[float],
        where_str: Optional[str] = None,
        limit: int = 10,
    ) -> List[Document]:
        """Load data from MyScale.

        Args:
            query_vector (List[float]): Query vector.
            where_str (Optional[str], optional): where condition string. Defaults to None.
            limit (int): Number of results to return.

        Returns:
            List[Document]: A list of documents.
        """

        query_statement = self.config.build_query_statement(
            query_embed=query_vector,
            where_str=where_str,
            limit=limit,
        )

        try:
            return [
                Document(doc_id=r["doc_id"], text=r["text"], extra_info=r["extra_info"])
                for r in self.client.query(query_statement).named_results()
            ]
        except Exception as e:
            raise e
