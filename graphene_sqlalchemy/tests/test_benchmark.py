import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import graphene
from graphene import relay

from ..types import SQLAlchemyObjectType
from ..utils import get_session, is_sqlalchemy_version_less_than
from .models import Article, HairKind, Pet, Reporter
from .utils import eventually_await_session

if is_sqlalchemy_version_less_than("1.2"):
    pytest.skip("SQL batching only works for SQLAlchemy 1.2+", allow_module_level=True)


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

        async def resolve_articles(self, info):
            session = get_session(info.context)
            if isinstance(session, AsyncSession):
                return (await session.scalars(select(Article))).all()
            return session.query(Article).all()

        async def resolve_reporters(self, info):
            session = get_session(info.context)
            if isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).all()
            return session.query(Reporter).all()

    return graphene.Schema(query=Query)


async def benchmark_query(session_factory, benchmark, query):
    schema = get_schema()

    @benchmark
    async def execute_query():
        result = await schema.execute_async(
            query,
            context_value={"session": session_factory()},
        )
        assert not result.errors


@pytest.mark.asyncio
async def test_one_to_one(session_factory, benchmark):
    session = session_factory()

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
        session_factory,
        benchmark,
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


def test_many_to_one(session_factory, benchmark):
    session = session_factory()

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

    benchmark_query(
        session_factory,
        benchmark,
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


def test_one_to_many(session_factory, benchmark):
    session = session_factory()

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

    benchmark_query(
        session_factory,
        benchmark,
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


def test_many_to_many(session_factory, benchmark):
    session = session_factory()

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

    session.commit()
    session.close()

    benchmark_query(
        session_factory,
        benchmark,
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
