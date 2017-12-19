import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import graphene
from graphene.relay import Node

from ..registry import reset_global_registry
from ..fields import SQLAlchemyConnectionField
from ..types import SQLAlchemyObjectType
from .models import Article, Base, Editor, Pet, Reporter

db = create_engine('sqlite:///test_sqlalchemy.sqlite3')


@pytest.yield_fixture(scope='function')
def session():
    reset_global_registry()
    connection = db.engine.connect()
    transaction = connection.begin()
    Base.metadata.create_all(connection)

    # options = dict(bind=connection, binds={})
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)

    yield session

    # Finalize test here
    transaction.rollback()
    connection.close()
    session.remove()


def setup_fixtures(session):
    pet = Pet(name='Lassie', pet_kind='dog')
    session.add(pet)
    reporter = Reporter(first_name='ABA', last_name='X')
    session.add(reporter)
    reporter2 = Reporter(first_name='ABO', last_name='Y')
    session.add(reporter2)
    article = Article(headline='Hi!')
    article.reporter = reporter
    session.add(article)
    editor = Editor(name="John")
    session.add(editor)
    session.commit()


def test_should_query_well(session):
    setup_fixtures(session)

    class ReporterType(SQLAlchemyObjectType):

        class Meta:
            model = Reporter

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)
        reporters = graphene.List(ReporterType)

        def resolve_reporter(self, *args, **kwargs):
            return session.query(Reporter).first()

        def resolve_reporters(self, *args, **kwargs):
            return session.query(Reporter)

    query = '''
        query ReporterQuery {
          reporter {
            firstName,
            lastName,
            email
          }
          reporters {
            firstName
          }
        }
    '''
    expected = {
        'reporter': {
            'firstName': 'ABA',
            'lastName': 'X',
            'email': None
        },
        'reporters': [{
            'firstName': 'ABA',
        }, {
            'firstName': 'ABO',
        }]
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert result.data == expected


def test_should_query_enums(session):
    setup_fixtures(session)

    class PetType(SQLAlchemyObjectType):

        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(PetType)

        def resolve_pet(self, *args, **kwargs):
            return session.query(Pet).first()

    query = '''
        query PetQuery {
          pet {
            name,
            petKind
          }
        }
    '''
    expected = {
        'pet': {
            'name': 'Lassie',
            'petKind': 'dog'
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    assert result.data == expected, result.data


def test_should_node(session):
    setup_fixtures(session)

    class ReporterNode(SQLAlchemyObjectType):

        class Meta:
            model = Reporter
            interfaces = (Node, )

        @classmethod
        def get_node(cls, id, info):
            return Reporter(id=2, first_name='Cookie Monster')

    class ArticleNode(SQLAlchemyObjectType):

        class Meta:
            model = Article
            interfaces = (Node, )

        # @classmethod
        # def get_node(cls, id, info):
        #     return Article(id=1, headline='Article node')

    class Query(graphene.ObjectType):
        node = Node.Field()
        reporter = graphene.Field(ReporterNode)
        article = graphene.Field(ArticleNode)
        all_articles = SQLAlchemyConnectionField(ArticleNode)

        def resolve_reporter(self, *args, **kwargs):
            return session.query(Reporter).first()

        def resolve_article(self, *args, **kwargs):
            return session.query(Article).first()

    query = '''
        query ReporterQuery {
          reporter {
            id,
            firstName,
            articles {
              edges {
                node {
                  headline
                }
              }
            }
            lastName,
            email
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
    '''
    expected = {
        'reporter': {
            'id': 'UmVwb3J0ZXJOb2RlOjE=',
            'firstName': 'ABA',
            'lastName': 'X',
            'email': None,
            'articles': {
                'edges': [{
                  'node': {
                      'headline': 'Hi!'
                  }
                }]
            },
        },
        'allArticles': {
            'edges': [{
                'node': {
                    'headline': 'Hi!'
                }
            }]
        },
        'myArticle': {
            'id': 'QXJ0aWNsZU5vZGU6MQ==',
            'headline': 'Hi!'
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    assert result.data == expected


def test_should_custom_identifier(session):
    setup_fixtures(session)

    class EditorNode(SQLAlchemyObjectType):

        class Meta:
            model = Editor
            interfaces = (Node, )

    class Query(graphene.ObjectType):
        node = Node.Field()
        all_editors = SQLAlchemyConnectionField(EditorNode)

    query = '''
        query EditorQuery {
          allEditors {
            edges {
                node {
                    id,
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
    '''
    expected = {
        'allEditors': {
            'edges': [{
                'node': {
                    'id': 'RWRpdG9yTm9kZTox',
                    'name': 'John'
                }
            }]
        },
        'node': {
            'name': 'John'
        }
    }

    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    assert result.data == expected


def test_should_mutate_well(session):
    setup_fixtures(session)

    class EditorNode(SQLAlchemyObjectType):

        class Meta:
            model = Editor
            interfaces = (Node, )

    class ReporterNode(SQLAlchemyObjectType):

        class Meta:
            model = Reporter
            interfaces = (Node, )

        @classmethod
        def get_node(cls, id, info):
            return Reporter(id=2, first_name='Cookie Monster')

    class ArticleNode(SQLAlchemyObjectType):

        class Meta:
            model = Article
            interfaces = (Node, )

    class CreateArticle(graphene.Mutation):

        class Arguments:
            headline = graphene.String()
            reporter_id = graphene.ID()

        ok = graphene.Boolean()
        article = graphene.Field(ArticleNode)

        def mutate(self, info, headline, reporter_id):
            new_article = Article(
                headline=headline,
                reporter_id=reporter_id,
            )

            session.add(new_article)
            session.commit()
            ok = True

            return CreateArticle(article=new_article, ok=ok)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        create_article = CreateArticle.Field()

    query = '''
        mutation ArticleCreator {
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
    '''
    expected = {
        'createArticle': {
            'ok': True,
            'article': {
                'headline': 'My Article',
                'reporter': {
                    'id': 'UmVwb3J0ZXJOb2RlOjE=',
                    'firstName': 'ABA'
                }
            }
        },
    }

    schema = graphene.Schema(query=Query, mutation=Mutation)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    assert result.data == expected
