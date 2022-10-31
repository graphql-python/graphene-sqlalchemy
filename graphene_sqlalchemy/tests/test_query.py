import pytest
from sqlalchemy import select

import graphene
from graphene.relay import Node

from ..converter import convert_sqlalchemy_composite
from ..fields import SQLAlchemyConnectionField
from ..types import ORMField, SQLAlchemyObjectType
from ..utils import SQL_VERSION_HIGHER_EQUAL_THAN_1_4, get_session
from .models import Article, CompositeFullName, Editor, HairKind, Pet, Reporter
from .utils import eventually_await_session, to_std_dicts

if SQL_VERSION_HIGHER_EQUAL_THAN_1_4:
    from sqlalchemy.ext.asyncio import AsyncSession


async def add_test_data(session):
    reporter = Reporter(first_name="John", last_name="Doe", favorite_pet_kind="cat")
    session.add(reporter)
    pet = Pet(name="Garfield", pet_kind="cat", hair_kind=HairKind.SHORT)
    session.add(pet)
    pet.reporters.append(reporter)
    article = Article(headline="Hi!")
    article.reporter = reporter
    session.add(article)
    reporter = Reporter(first_name="Jane", last_name="Roe", favorite_pet_kind="dog")
    session.add(reporter)
    pet = Pet(name="Lassie", pet_kind="dog", hair_kind=HairKind.LONG)
    pet.reporters.append(reporter)
    session.add(pet)
    editor = Editor(name="Jack")
    session.add(editor)
    await eventually_await_session(session, "commit")


@pytest.mark.asyncio
async def test_query_fields(session):
    await add_test_data(session)

    @convert_sqlalchemy_composite.register(CompositeFullName)
    def convert_composite_class(composite, registry):
        return graphene.String()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)
        reporters = graphene.List(ReporterType)

        async def resolve_reporter(self, _info):
            session = get_session(_info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).unique().first()
            return session.query(Reporter).first()

        async def resolve_reporters(self, _info):
            session = get_session(_info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).unique().all()
            return session.query(Reporter)

    query = """
        query {
          reporter {
            firstName
            columnProp
            hybridProp
            compositeProp
          }
          reporters {
            firstName
          }
        }
    """
    expected = {
        "reporter": {
            "firstName": "John",
            "hybridProp": "John",
            "columnProp": 2,
            "compositeProp": "John Doe",
        },
        "reporters": [{"firstName": "John"}, {"firstName": "Jane"}],
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_query_node_sync(session):
    await add_test_data(session)

    class ReporterNode(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        @classmethod
        def get_node(cls, info, id):
            return Reporter(id=2, first_name="Cookie Monster")

    class ArticleNode(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        reporter = graphene.Field(ReporterNode)
        all_articles = SQLAlchemyConnectionField(ArticleNode.connection)

        def resolve_reporter(self, _info):
            session = get_session(_info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):

                async def get_result():
                    return (await session.scalars(select(Reporter))).first()

                return get_result()

            return session.query(Reporter).first()

    query = """
        query {
          reporter {
            id
            firstName
            articles {
              edges {
                node {
                  headline
                }
              }
            }
          }
          allArticles {
            edges {
              node {
                headline
              }
            }
          }
          myArticle: node(id:"QXJ0aWNsZU5vZGU6MQ==") {
            id
            ... on ReporterNode {
                firstName
            }
            ... on ArticleNode {
                headline
            }
          }
        }
    """
    expected = {
        "reporter": {
            "id": "UmVwb3J0ZXJOb2RlOjE=",
            "firstName": "John",
            "articles": {"edges": [{"node": {"headline": "Hi!"}}]},
        },
        "allArticles": {"edges": [{"node": {"headline": "Hi!"}}]},
        "myArticle": {"id": "QXJ0aWNsZU5vZGU6MQ==", "headline": "Hi!"},
    }
    schema = graphene.Schema(query=Query)
    if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
        result = schema.execute(query, context_value={"session": session})
        assert result.errors
    else:
        result = schema.execute(query, context_value={"session": session})
        assert not result.errors
        result = to_std_dicts(result.data)
        assert result == expected


@pytest.mark.asyncio
async def test_query_node_async(session):
    await add_test_data(session)

    class ReporterNode(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        @classmethod
        def get_node(cls, info, id):
            return Reporter(id=2, first_name="Cookie Monster")

    class ArticleNode(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        reporter = graphene.Field(ReporterNode)
        all_articles = SQLAlchemyConnectionField(ArticleNode.connection)

        def resolve_reporter(self, _info):
            session = get_session(_info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):

                async def get_result():
                    return (await session.scalars(select(Reporter))).first()

                return get_result()

            return session.query(Reporter).first()

    query = """
        query {
          reporter {
            id
            firstName
            articles {
              edges {
                node {
                  headline
                }
              }
            }
          }
          allArticles {
            edges {
              node {
                headline
              }
            }
          }
          myArticle: node(id:"QXJ0aWNsZU5vZGU6MQ==") {
            id
            ... on ReporterNode {
                firstName
            }
            ... on ArticleNode {
                headline
            }
          }
        }
    """
    expected = {
        "reporter": {
            "id": "UmVwb3J0ZXJOb2RlOjE=",
            "firstName": "John",
            "articles": {"edges": [{"node": {"headline": "Hi!"}}]},
        },
        "allArticles": {"edges": [{"node": {"headline": "Hi!"}}]},
        "myArticle": {"id": "QXJ0aWNsZU5vZGU6MQ==", "headline": "Hi!"},
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_orm_field(session):
    await add_test_data(session)

    @convert_sqlalchemy_composite.register(CompositeFullName)
    def convert_composite_class(composite, registry):
        return graphene.String()

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        first_name_v2 = ORMField(model_attr="first_name")
        hybrid_prop_v2 = ORMField(model_attr="hybrid_prop")
        column_prop_v2 = ORMField(model_attr="column_prop")
        composite_prop = ORMField()
        favorite_article_v2 = ORMField(model_attr="favorite_article")
        articles_v2 = ORMField(model_attr="articles")

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)

        async def resolve_reporter(self, _info):
            session = get_session(_info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).first()
            return session.query(Reporter).first()

    query = """
        query {
          reporter {
            firstNameV2
            hybridPropV2
            columnPropV2
            compositeProp
            favoriteArticleV2 {
              headline
            }
            articlesV2(first: 1) {
              edges {
                node {
                  headline
                }
              }
            }
          }
        }
    """
    expected = {
        "reporter": {
            "firstNameV2": "John",
            "hybridPropV2": "John",
            "columnPropV2": 2,
            "compositeProp": "John Doe",
            "favoriteArticleV2": {"headline": "Hi!"},
            "articlesV2": {"edges": [{"node": {"headline": "Hi!"}}]},
        },
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_custom_identifier(session):
    await add_test_data(session)

    class EditorNode(SQLAlchemyObjectType):
        class Meta:
            model = Editor
            interfaces = (Node,)

    class Query(graphene.ObjectType):
        node = Node.Field()
        all_editors = SQLAlchemyConnectionField(EditorNode.connection)

    query = """
        query {
          allEditors {
            edges {
                node {
                    id
                    name
                }
            }
          },
          node(id: "RWRpdG9yTm9kZTox") {
            ...on EditorNode {
              name
            }
          }
        }
    """
    expected = {
        "allEditors": {"edges": [{"node": {"id": "RWRpdG9yTm9kZTox", "name": "Jack"}}]},
        "node": {"name": "Jack"},
    }

    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


@pytest.mark.asyncio
async def test_mutation(session, session_factory):
    await add_test_data(session)

    class EditorNode(SQLAlchemyObjectType):
        class Meta:
            model = Editor
            interfaces = (Node,)

    class ReporterNode(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        @classmethod
        async def get_node(cls, id, info):
            session = get_session(info.context)
            if SQL_VERSION_HIGHER_EQUAL_THAN_1_4 and isinstance(session, AsyncSession):
                return (await session.scalars(select(Reporter))).unique().first()
            return session.query(Reporter).first()

    class ArticleNode(SQLAlchemyObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)

    class CreateArticle(graphene.Mutation):
        class Arguments:
            headline = graphene.String()
            reporter_id = graphene.ID()

        ok = graphene.Boolean()
        article = graphene.Field(ArticleNode)

        async def mutate(self, info, headline, reporter_id):
            reporter = await ReporterNode.get_node(reporter_id, info)
            new_article = Article(headline=headline, reporter_id=reporter_id)
            reporter.articles = [*reporter.articles, new_article]
            session = get_session(info.context)
            session.add(reporter)

            await eventually_await_session(session, "commit")
            ok = True

            return CreateArticle(article=new_article, ok=ok)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        create_article = CreateArticle.Field()

    query = """
        mutation {
          createArticle(
            headline: "My Article"
            reporterId: "1"
          ) {
            ok
            article {
                headline
                reporter {
                    id
                    firstName
                }
            }
          }
        }
    """
    expected = {
        "createArticle": {
            "ok": True,
            "article": {
                "headline": "My Article",
                "reporter": {"id": "UmVwb3J0ZXJOb2RlOjE=", "firstName": "John"},
            },
        }
    }

    schema = graphene.Schema(query=Query, mutation=Mutation)
    result = await schema.execute_async(
        query, context_value={"session": session_factory()}
    )
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected
