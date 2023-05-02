"""Index registry."""

from typing import Dict, Type

from llama_index.data_structs.data_structs import (
    KG,
    EmptyIndex,
    IndexDict,
    IndexGraph,
    IndexList,
    KeywordTable,
    IndexStruct,
)
from llama_index.data_structs.struct_type import IndexStructType
from llama_index.data_structs.table import PandasStructTable, SQLStructTable


INDEX_STRUCT_TYPE_TO_INDEX_STRUCT_CLASS: Dict[IndexStructType, Type[IndexStruct]] = {
    IndexStructType.TREE: IndexGraph,
    IndexStructType.LIST: IndexList,
    IndexStructType.KEYWORD_TABLE: KeywordTable,
    IndexStructType.VECTOR_STORE: IndexDict,
    IndexStructType.SQL: SQLStructTable,
    IndexStructType.PANDAS: PandasStructTable,
    IndexStructType.KG: KG,
    IndexStructType.EMPTY: EmptyIndex,
}
