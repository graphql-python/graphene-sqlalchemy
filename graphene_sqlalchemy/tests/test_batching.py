import ast
import contextlib
import logging

import pytest
from sqlalchemy import select

import graphene
from graphene import Connection, relay

from ..fields import BatchSQLAlchemyConnectionField, default_connection_field_factory
from ..types import ORMField, SQLAlchemyObjectType
from ..utils import (
    SQL_VERSION_HIGHER_EQUAL_THAN_1_4,
    get_session,
    is_sqlalchemy_version_less_than,
)
from .models_batching import Article, HairKind, Pet, Reader, Reporter
from .utils import eventually_await_session, remove_cache_miss_stat, to_std_dicts

if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
    from sqlalchemy.ext.asyncio import AsyncSession


class MockLoggingHandler(logging.Handler):
    """Intercept and store log messages in a list."""

    def __init__(self, *args, **kwargs):
        self.messages = []
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages.append(record.getMessage())


@contextlib.contextmanager
def mock_sqlalchemy_logging_handler():
    logging.basicConfig()
    sql_logger = logging.getLogger("sqlalchemy.engine")
    previous_level = sql_logger.level

    sql_logger.setLevel(logging.INFO)
    mock_logging_handler = MockLoggingHandler()
    mock_logging_handler.setLevel(logging.INFO)
    sql_logger.addHandler(mock_logging_handler)

    yield mock_logging_handler

    sql_logger.setLevel(previous_level)


def get_async_schema():
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = True

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)
            batching = True

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (relay.Node,)
            batching = True

    class Query(graphene.ObjectType):
        articles = graphene.Field(graphene.List(ArticleType))
        reporters = graphene.Field(graphene.List(ReporterType))

        async def resolve_articles(self, info):
            session = get_session(info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Article))).all()
            return session.query(Article).all()

        async def resolve_reporters(self, info):
            session = get_session(info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).all()
            return session.query(Reporter).all()

    return graphene.Schema(query=Query)


def get_schema():
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = True

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)
            batching = True

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (relay.Node,)
            batching = True

    class Query(graphene.ObjectType):
        articles = graphene.Field(graphene.List(ArticleType))
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_articles(self, info):
            session = get_session(info.context)
            return session.query(Article).all()

        def resolve_reporters(self, info):
            session = get_session(info.context)
            return session.query(Reporter).all()

    return graphene.Schema(query=Query)


if is_sqlalchemy_version_less_than("1.2"):
    pytest.skip("SQL batching only works for SQLAlchemy 1.2+", allow_module_level=True)


def get_full_relay_schema():
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            name = "Reporter"
            interfaces = (relay.Node,)
            batching = True
            connection_class = Connection

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            name = "Article"
            interfaces = (relay.Node,)
            batching = True
            connection_class = Connection

    class ReaderType(SQLAlchemyObjectType):
        class Meta:
            model = Reader
            name = "Reader"
            interfaces = (relay.Node,)
            batching = True
            connection_class = Connection

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        articles = BatchSQLAlchemyConnectionField(ArticleType.connection)
        reporters = BatchSQLAlchemyConnectionField(ReporterType.connection)
        readers = BatchSQLAlchemyConnectionField(ReaderType.connection)

    return graphene.Schema(query=Query)


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_provider", [get_schema, get_async_schema])
async def test_many_to_one(sync_session_factory, schema_provider):
    session = sync_session_factory()
    schema = schema_provider()
    reporter_1 = Reporter(
        first_name="Reporter_1",
    )
    session.add(reporter_1)
    reporter_2 = Reporter(
        first_name="Reporter_2",
    )
    session.add(reporter_2)

    article_1 = Article(headline="Article_1")
    article_1.reporter = reporter_1
    session.add(article_1)

    article_2 = Article(headline="Article_2")
    article_2.reporter = reporter_2
    session.add(article_2)

    session.commit()
    session.close()

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        result = await schema.execute_async(
            """
              query {
                articles {
                  headline
                  reporter {
                    firstName
                  }
                }
              }
            """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == {
        "articles": [
            {
                "headline": "Article_1",
                "reporter": {
                    "firstName": "Reporter_1",
                },
            },
            {
                "headline": "Article_2",
                "reporter": {
                    "firstName": "Reporter_2",
                },
            },
        ],
    }

    assert len(messages) == 5

    if is_sqlalchemy_version_less_than("1.3"):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        sql_statements = [
            message
            for message in messages
            if "SELECT" in message and "JOIN reporters" in message
        ]
        assert len(sql_statements) == 1
        return

    if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
        messages[2] = remove_cache_miss_stat(messages[2])
        messages[4] = remove_cache_miss_stat(messages[4])

    assert ast.literal_eval(messages[2]) == ()
    assert sorted(ast.literal_eval(messages[4])) == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_provider", [get_schema, get_async_schema])
async def test_one_to_one(sync_session_factory, schema_provider):
    session = sync_session_factory()
    schema = schema_provider()
    reporter_1 = Reporter(
        first_name="Reporter_1",
    )
    session.add(reporter_1)
    reporter_2 = Reporter(
        first_name="Reporter_2",
    )
    session.add(reporter_2)

    article_1 = Article(headline="Article_1")
    article_1.reporter = reporter_1
    session.add(article_1)

    article_2 = Article(headline="Article_2")
    article_2.reporter = reporter_2
    session.add(article_2)

    session.commit()
    session.close()

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level

        session = sync_session_factory()
        result = await schema.execute_async(
            """
          query {
            reporters {
              firstName
              favoriteArticle {
                headline
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == {
        "reporters": [
            {
                "firstName": "Reporter_1",
                "favoriteArticle": {
                    "headline": "Article_1",
                },
            },
            {
                "firstName": "Reporter_2",
                "favoriteArticle": {
                    "headline": "Article_2",
                },
            },
        ],
    }
    assert len(messages) == 5

    if is_sqlalchemy_version_less_than("1.3"):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        sql_statements = [
            message
            for message in messages
            if "SELECT" in message and "JOIN articles" in message
        ]
        assert len(sql_statements) == 1
        return

    if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
        messages[2] = remove_cache_miss_stat(messages[2])
        messages[4] = remove_cache_miss_stat(messages[4])

    assert ast.literal_eval(messages[2]) == ()
    assert sorted(ast.literal_eval(messages[4])) == [1, 2]


@pytest.mark.asyncio
async def test_one_to_many(sync_session_factory):
    session = sync_session_factory()

    reporter_1 = Reporter(
        first_name="Reporter_1",
    )
    session.add(reporter_1)
    reporter_2 = Reporter(
        first_name="Reporter_2",
    )
    session.add(reporter_2)

    article_1 = Article(headline="Article_1")
    article_1.reporter = reporter_1
    session.add(article_1)

    article_2 = Article(headline="Article_2")
    article_2.reporter = reporter_1
    session.add(article_2)

    article_3 = Article(headline="Article_3")
    article_3.reporter = reporter_2
    session.add(article_3)

    article_4 = Article(headline="Article_4")
    article_4.reporter = reporter_2
    session.add(article_4)
    session.commit()
    session.close()

    schema = get_schema()

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level

        session = sync_session_factory()
        result = await schema.execute_async(
            """
            query {
                reporters {
                    firstName
                    articles(first: 2) {
                        edges {
                            node {
                                headline
                            }
                        }
                    }
                }
            }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == {
        "reporters": [
            {
                "firstName": "Reporter_1",
                "articles": {
                    "edges": [
                        {
                            "node": {
                                "headline": "Article_1",
                            },
                        },
                        {
                            "node": {
                                "headline": "Article_2",
                            },
                        },
                    ],
                },
            },
            {
                "firstName": "Reporter_2",
                "articles": {
                    "edges": [
                        {
                            "node": {
                                "headline": "Article_3",
                            },
                        },
                        {
                            "node": {
                                "headline": "Article_4",
                            },
                        },
                    ],
                },
            },
        ],
    }
    assert len(messages) == 5

    if is_sqlalchemy_version_less_than("1.3"):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        sql_statements = [
            message
            for message in messages
            if "SELECT" in message and "JOIN articles" in message
        ]
        assert len(sql_statements) == 1
        return

    if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
        messages[2] = remove_cache_miss_stat(messages[2])
        messages[4] = remove_cache_miss_stat(messages[4])

    assert ast.literal_eval(messages[2]) == ()
    assert sorted(ast.literal_eval(messages[4])) == [1, 2]


@pytest.mark.asyncio
async def test_many_to_many(sync_session_factory):
    session = sync_session_factory()

    reporter_1 = Reporter(
        first_name="Reporter_1",
    )
    session.add(reporter_1)
    reporter_2 = Reporter(
        first_name="Reporter_2",
    )
    session.add(reporter_2)

    pet_1 = Pet(name="Pet_1", pet_kind="cat", hair_kind=HairKind.LONG)
    session.add(pet_1)

    pet_2 = Pet(name="Pet_2", pet_kind="cat", hair_kind=HairKind.LONG)
    session.add(pet_2)

    reporter_1.pets.append(pet_1)
    reporter_1.pets.append(pet_2)

    pet_3 = Pet(name="Pet_3", pet_kind="cat", hair_kind=HairKind.LONG)
    session.add(pet_3)

    pet_4 = Pet(name="Pet_4", pet_kind="cat", hair_kind=HairKind.LONG)
    session.add(pet_4)

    reporter_2.pets.append(pet_3)
    reporter_2.pets.append(pet_4)
    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    schema = get_schema()

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        result = await schema.execute_async(
            """
            query {
                reporters {
                    firstName
                    pets(first: 2) {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
            }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == {
        "reporters": [
            {
                "firstName": "Reporter_1",
                "pets": {
                    "edges": [
                        {
                            "node": {
                                "name": "Pet_1",
                            },
                        },
                        {
                            "node": {
                                "name": "Pet_2",
                            },
                        },
                    ],
                },
            },
            {
                "firstName": "Reporter_2",
                "pets": {
                    "edges": [
                        {
                            "node": {
                                "name": "Pet_3",
                            },
                        },
                        {
                            "node": {
                                "name": "Pet_4",
                            },
                        },
                    ],
                },
            },
        ],
    }

    assert len(messages) == 5

    if is_sqlalchemy_version_less_than("1.3"):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        sql_statements = [
            message
            for message in messages
            if "SELECT" in message and "JOIN pets" in message
        ]
        assert len(sql_statements) == 1
        return

    if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
        messages[2] = remove_cache_miss_stat(messages[2])
        messages[4] = remove_cache_miss_stat(messages[4])

    assert ast.literal_eval(messages[2]) == ()
    assert sorted(ast.literal_eval(messages[4])) == [1, 2]


def test_disable_batching_via_ormfield(sync_session_factory):
    session = sync_session_factory()
    reporter_1 = Reporter(first_name="Reporter_1")
    session.add(reporter_1)
    reporter_2 = Reporter(first_name="Reporter_2")
    session.add(reporter_2)
    session.commit()
    session.close()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = True

        favorite_article = ORMField(batching=False)
        articles = ORMField(batching=False)

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)

    class Query(graphene.ObjectType):
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_reporters(self, info):
            return info.context.get("session").query(Reporter).all()

    schema = graphene.Schema(query=Query)

    # Test one-to-one and many-to-one relationships
    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        schema.execute(
            """
          query {
            reporters {
              favoriteArticle {
                headline
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    select_statements = [
        message
        for message in messages
        if "SELECT" in message and "FROM articles" in message
    ]
    assert len(select_statements) == 2

    # Test one-to-many and many-to-many relationships
    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        schema.execute(
            """
          query {
            reporters {
              articles {
                edges {
                  node {
                    headline
                  }
                }
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    select_statements = [
        message
        for message in messages
        if "SELECT" in message and "FROM articles" in message
    ]
    assert len(select_statements) == 2


def test_batch_sorting_with_custom_ormfield(sync_session_factory):
    session = sync_session_factory()
    reporter_1 = Reporter(first_name="Reporter_1")
    session.add(reporter_1)
    reporter_2 = Reporter(first_name="Reporter_2")
    session.add(reporter_2)
    session.commit()
    session.close()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            name = "Reporter"
            interfaces = (relay.Node,)
            batching = True
            connection_class = Connection

        firstname = ORMField(model_attr="first_name")

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        reporters = BatchSQLAlchemyConnectionField(ReporterType.connection)

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = True

    schema = graphene.Schema(query=Query)

    # Test one-to-one and many-to-one relationships
    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        result = schema.execute(
            """
          query {
            reporters(sort: [FIRSTNAME_DESC]) {
              edges {
                node {
                  firstname
                }
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages
        assert not result.errors
        result = to_std_dicts(result.data)
    assert result == {
        "reporters": {
            "edges": [
                {
                    "node": {
                        "firstname": "Reporter_2",
                    }
                },
                {
                    "node": {
                        "firstname": "Reporter_1",
                    }
                },
            ]
        }
    }
    select_statements = [
        message
        for message in messages
        if "SELECT" in message and "FROM reporters" in message
    ]
    assert len(select_statements) == 2


@pytest.mark.asyncio
async def test_connection_factory_field_overrides_batching_is_false(
    sync_session_factory,
):
    session = sync_session_factory()
    reporter_1 = Reporter(first_name="Reporter_1")
    session.add(reporter_1)
    reporter_2 = Reporter(first_name="Reporter_2")
    session.add(reporter_2)
    session.commit()
    session.close()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = False
            connection_field_factory = BatchSQLAlchemyConnectionField.from_relationship

        articles = ORMField(batching=False)

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)

    class Query(graphene.ObjectType):
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_reporters(self, info):
            return info.context.get("session").query(Reporter).all()

    schema = graphene.Schema(query=Query)

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        await schema.execute_async(
            """
          query {
            reporters {
              articles {
                edges {
                  node {
                    headline
                  }
                }
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    if is_sqlalchemy_version_less_than("1.3"):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        select_statements = [
            message
            for message in messages
            if "SELECT" in message and "JOIN articles" in message
        ]
    else:
        select_statements = [
            message
            for message in messages
            if "SELECT" in message and "FROM articles" in message
        ]
    assert len(select_statements) == 1


def test_connection_factory_field_overrides_batching_is_true(sync_session_factory):
    session = sync_session_factory()
    reporter_1 = Reporter(first_name="Reporter_1")
    session.add(reporter_1)
    reporter_2 = Reporter(first_name="Reporter_2")
    session.add(reporter_2)
    session.commit()
    session.close()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)
            batching = True
            connection_field_factory = default_connection_field_factory

        articles = ORMField(batching=True)

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)

    class Query(graphene.ObjectType):
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_reporters(self, info):
            return info.context.get("session").query(Reporter).all()

    schema = graphene.Schema(query=Query)

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = sync_session_factory()
        schema.execute(
            """
          query {
            reporters {
              articles {
                edges {
                  node {
                    headline
                  }
                }
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    select_statements = [
        message
        for message in messages
        if "SELECT" in message and "FROM articles" in message
    ]
    assert len(select_statements) == 2


@pytest.mark.asyncio
async def test_batching_across_nested_relay_schema(
    session_factory, async_session: bool
):
    session = session_factory()

    for first_name in "fgerbhjikzutzxsdfdqqa":
        reporter = Reporter(
            first_name=first_name,
        )
        session.add(reporter)
        article = Article(headline="Article")
        article.reporter = reporter
        session.add(article)
        reader = Reader(name="Reader")
        reader.articles = [article]
        session.add(reader)

    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    schema = get_full_relay_schema()

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = session_factory()
        result = await schema.execute_async(
            """
          query {
            reporters {
              edges {
                node {
                  firstName
                  articles {
                    edges {
                      node {
                        id
                        readers {
                          edges {
                            node {
                              name
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        """,
            context_value={"session": session},
        )
        messages = sqlalchemy_logging_handler.messages

    result = to_std_dicts(result.data)
    select_statements = [message for message in messages if "SELECT" in message]
    if async_session:
        assert len(select_statements) == 2  # TODO: Figure out why async has less calls
    else:
        assert len(select_statements) == 4
        assert select_statements[-1].startswith("SELECT articles_1.id")
        if is_sqlalchemy_version_less_than("1.3"):
            assert select_statements[-2].startswith("SELECT reporters_1.id")
            assert "WHERE reporters_1.id IN" in select_statements[-2]
        else:
            assert select_statements[-2].startswith("SELECT articles.reporter_id")
            assert "WHERE articles.reporter_id IN" in select_statements[-2]


@pytest.mark.asyncio
async def test_sorting_can_be_used_with_batching_when_using_full_relay(session_factory):
    session = session_factory()

    for first_name, email in zip("cadbbb", "aaabac"):
        reporter_1 = Reporter(first_name=first_name, email=email)
        session.add(reporter_1)
        article_1 = Article(headline="headline")
        article_1.reporter = reporter_1
        session.add(article_1)

    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    schema = get_full_relay_schema()

    session = session_factory()
    result = await schema.execute_async(
        """
      query {
        reporters(sort: [FIRST_NAME_ASC, EMAIL_ASC]) {
          edges {
            node {
              firstName
              email
            }
          }
        }
      }
    """,
        context_value={"session": session},
    )

    result = to_std_dicts(result.data)
    assert [
        r["node"]["firstName"] + r["node"]["email"]
        for r in result["reporters"]["edges"]
    ] == ["aa", "ba", "bb", "bc", "ca", "da"]
