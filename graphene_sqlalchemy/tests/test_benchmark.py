import asyncio
import pytest
from sqlalchemy import select

import graphene
from graphene import relay

from ..types import SQLAlchemyObjectType
from ..utils import get_session, is_sqlalchemy_version_less_than
from .models import Article, HairKind, Pet, Reporter
from .utils import eventually_await_session

if not is_sqlalchemy_version_less_than("1.4"):
    from sqlalchemy.ext.asyncio import AsyncSession
if is_sqlalchemy_version_less_than("1.2"):
    pytest.skip("SQL batching only works for SQLAlchemy 1.2+", allow_module_level=True)


def get_async_schema():
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (relay.Node,)

    class Query(graphene.ObjectType):
        articles = graphene.Field(graphene.List(ArticleType))
        reporters = graphene.Field(graphene.List(ReporterType))

        async def resolve_articles(self, info):
            session = get_session(info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (await session.scalars(select(Article))).all()
            return session.query(Article).all()

        async def resolve_reporters(self, info):
            session = get_session(info.context)
            if not is_sqlalchemy_version_less_than("1.4") and isinstance(
                session, AsyncSession
            ):
                return (await session.scalars(select(Reporter))).all()
            return session.query(Reporter).all()

    return graphene.Schema(query=Query)


def get_schema():
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (relay.Node,)

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (relay.Node,)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (relay.Node,)

    class Query(graphene.ObjectType):
        articles = graphene.Field(graphene.List(ArticleType))
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_articles(self, info):
            return info.context.get("session").query(Article).all()

        def resolve_reporters(self, info):
            return info.context.get("session").query(Reporter).all()

    return graphene.Schema(query=Query)


async def benchmark_query(session, benchmark, schema, query):
    import nest_asyncio

    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    result = benchmark(
        lambda: loop.run_until_complete(
            schema.execute_async(query, context_value={"session": session})
        )
    )
    assert not result.errors


@pytest.fixture(params=[get_schema, get_async_schema])
def schema_provider(request, async_session):
    if async_session and request.param == get_schema:
        pytest.skip("Cannot test sync schema with async sessions")
    return request.param


@pytest.mark.asyncio
async def test_one_to_one(session_factory, benchmark, schema_provider):
    session = session_factory()
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

    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    await benchmark_query(
        session,
        benchmark,
        schema,
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
    )


@pytest.mark.asyncio
async def test_many_to_one(session_factory, benchmark, schema_provider):
    session = session_factory()
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
    await eventually_await_session(session, "flush")
    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    await benchmark_query(
        session,
        benchmark,
        schema,
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
    )


@pytest.mark.asyncio
async def test_one_to_many(session_factory, benchmark, schema_provider):
    session = session_factory()
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
    article_2.reporter = reporter_1
    session.add(article_2)

    article_3 = Article(headline="Article_3")
    article_3.reporter = reporter_2
    session.add(article_3)

    article_4 = Article(headline="Article_4")
    article_4.reporter = reporter_2
    session.add(article_4)

    await eventually_await_session(session, "commit")
    await eventually_await_session(session, "close")

    await benchmark_query(
        session,
        benchmark,
        schema,
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
    )


@pytest.mark.asyncio
async def test_many_to_many(session_factory, benchmark, schema_provider):
    session = session_factory()
    schema = schema_provider()
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

    await benchmark_query(
        session,
        benchmark,
        schema,
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
    )
