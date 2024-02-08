import asyncio
from typing import Any, Dict, Tuple

import pytest
from llama_index.legacy.legacy.indices.struct_store.base import default_output_parser
from llama_index.legacy.legacy.indices.struct_store.sql import SQLStructStoreIndex
from llama_index.legacy.legacy.indices.struct_store.sql_query import (
    NLSQLTableQueryEngine,
    NLStructStoreQueryEngine,
    SQLStructStoreQueryEngine,
)
from llama_index.legacy.legacy.schema import Document
from llama_index.legacy.legacy.service_context import ServiceContext
from llama_index.legacy.legacy.utilities.sql_wrapper import SQLDatabase
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import OperationalError


def test_sql_index_query(
    mock_service_context: ServiceContext,
    struct_kwargs: Tuple[Dict, Dict],
) -> None:
    """Test SQLStructStoreIndex."""
    index_kwargs, query_kwargs = struct_kwargs
    docs = [Document(text="user_id:2,foo:bar"), Document(text="user_id:8,foo:hello")]
    engine = create_engine("sqlite:///:memory:")
    metadata_obj = MetaData()
    table_name = "test_table"
    # NOTE: table is created by tying to metadata_obj
    Table(
        table_name,
        metadata_obj,
        Column("user_id", Integer, primary_key=True),
        Column("foo", String(16), nullable=False),
    )
    metadata_obj.create_all(engine)
    sql_database = SQLDatabase(engine)
    # NOTE: we can use the default output parser for this
    index = SQLStructStoreIndex.from_documents(
        docs,
        sql_database=sql_database,
        table_name=table_name,
        service_context=mock_service_context,
        **index_kwargs
    )

    # query the index with SQL
    sql_to_test = "SELECT user_id, foo FROM test_table"
    sql_query_engine = SQLStructStoreQueryEngine(index, **query_kwargs)
    response = sql_query_engine.query(sql_to_test)
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    # query the index with natural language
    nl_query_engine = NLStructStoreQueryEngine(index, **query_kwargs)
    response = nl_query_engine.query("test_table:user_id,foo")
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    nl_table_engine = NLSQLTableQueryEngine(index.sql_database)
    response = nl_table_engine.query("test_table:user_id,foo")
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    with pytest.raises(NotImplementedError, match="invalid SQL") as exc_info:
        sql_query_engine.query("LLM didn't provide SQL at all")
    assert isinstance(exc_info.value.__cause__, OperationalError)

    ## sql_only=True tests
    # query the index with SQL
    sql_query_engine = SQLStructStoreQueryEngine(index, sql_only=True, **query_kwargs)
    response = sql_query_engine.query(sql_to_test)
    assert str(response) == sql_to_test

    # query the index with natural language
    nl_query_engine = NLStructStoreQueryEngine(index, sql_only=True, **query_kwargs)
    response = nl_query_engine.query("test_table:user_id,foo")
    assert str(response) == sql_to_test

    nl_table_engine = NLSQLTableQueryEngine(index.sql_database, sql_only=True)
    response = nl_table_engine.query("test_table:user_id,foo")
    assert str(response) == sql_to_test


def test_sql_index_async_query(
    allow_networking: Any,
    mock_service_context: ServiceContext,
    struct_kwargs: Tuple[Dict, Dict],
) -> None:
    """Test SQLStructStoreIndex."""
    index_kwargs, query_kwargs = struct_kwargs
    docs = [Document(text="user_id:2,foo:bar"), Document(text="user_id:8,foo:hello")]
    engine = create_engine("sqlite:///:memory:")
    metadata_obj = MetaData()
    table_name = "test_table"
    # NOTE: table is created by tying to metadata_obj
    Table(
        table_name,
        metadata_obj,
        Column("user_id", Integer, primary_key=True),
        Column("foo", String(16), nullable=False),
    )
    metadata_obj.create_all(engine)
    sql_database = SQLDatabase(engine)
    # NOTE: we can use the default output parser for this
    index = SQLStructStoreIndex.from_documents(
        docs,
        sql_database=sql_database,
        table_name=table_name,
        service_context=mock_service_context,
        **index_kwargs
    )

    sql_to_test = "SELECT user_id, foo FROM test_table"
    # query the index with SQL
    sql_query_engine = SQLStructStoreQueryEngine(index, **query_kwargs)
    task = sql_query_engine.aquery(sql_to_test)
    response = asyncio.run(task)
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    # query the index with natural language
    nl_query_engine = NLStructStoreQueryEngine(index, **query_kwargs)
    task = nl_query_engine.aquery("test_table:user_id,foo")
    response = asyncio.run(task)
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    nl_table_engine = NLSQLTableQueryEngine(index.sql_database)
    task = nl_table_engine.aquery("test_table:user_id,foo")
    response = asyncio.run(task)
    assert str(response) == "[(2, 'bar'), (8, 'hello')]"

    ## sql_only = True  ###
    # query the index with SQL
    sql_query_engine = SQLStructStoreQueryEngine(index, sql_only=True, **query_kwargs)
    task = sql_query_engine.aquery(sql_to_test)
    response = asyncio.run(task)
    assert str(response) == sql_to_test

    # query the index with natural language
    nl_query_engine = NLStructStoreQueryEngine(index, sql_only=True, **query_kwargs)
    task = nl_query_engine.aquery("test_table:user_id,foo")
    response = asyncio.run(task)
    assert str(response) == sql_to_test

    nl_table_engine = NLSQLTableQueryEngine(index.sql_database, sql_only=True)
    task = nl_table_engine.aquery("test_table:user_id,foo")
    response = asyncio.run(task)
    assert str(response) == sql_to_test


def test_default_output_parser() -> None:
    """Test default output parser."""
    test_str = "user_id:2\n" "foo:bar\n" ",,testing:testing2..\n" "number:123,456,789\n"
    fields = default_output_parser(test_str)
    assert fields == {
        "user_id": "2",
        "foo": "bar",
        "testing": "testing2",
        "number": "123456789",
    }
