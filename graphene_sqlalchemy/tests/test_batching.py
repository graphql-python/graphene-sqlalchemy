import contextlib
import logging

import pkg_resources
import pytest

import graphene

from ..types import SQLAlchemyObjectType
from .models import Article, Reporter
from .utils import to_std_dicts


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
    sql_logger = logging.getLogger('sqlalchemy.engine')
    previous_level = sql_logger.level

    sql_logger.setLevel(logging.INFO)
    mock_logging_handler = MockLoggingHandler()
    mock_logging_handler.setLevel(logging.INFO)
    sql_logger.addHandler(mock_logging_handler)

    yield mock_logging_handler

    sql_logger.setLevel(previous_level)


def make_fixture(session):
    reporter_1 = Reporter(
      first_name='Reporter_1',
    )
    session.add(reporter_1)
    reporter_2 = Reporter(
      first_name='Reporter_2',
    )
    session.add(reporter_2)

    article_1 = Article(headline='Article_1')
    article_1.reporter = reporter_1
    session.add(article_1)

    article_2 = Article(headline='Article_2')
    article_2.reporter = reporter_2
    session.add(article_2)

    session.commit()
    session.close()


def get_schema(session):
    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter

    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article

    class Query(graphene.ObjectType):
        articles = graphene.Field(graphene.List(ArticleType))
        reporters = graphene.Field(graphene.List(ReporterType))

        def resolve_articles(self, _info):
            return session.query(Article).all()

        def resolve_reporters(self, _info):
            return session.query(Reporter).all()

    return graphene.Schema(query=Query)


def is_sqlalchemy_version_less_than(version_string):
    return pkg_resources.get_distribution('SQLAlchemy').parsed_version < pkg_resources.parse_version(version_string)


if is_sqlalchemy_version_less_than('1.2'):
    pytest.skip('SQL batching only works for SQLAlchemy 1.2+', allow_module_level=True)


def test_many_to_one(session_factory):
    session = session_factory()
    make_fixture(session)
    schema = get_schema(session)

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = session_factory()
        result = schema.execute("""
          query {
            articles {
              headline
              reporter {
                firstName
              }
            }
          }
        """, context_value={"session": session})
        messages = sqlalchemy_logging_handler.messages

    assert len(messages) == 5

    if is_sqlalchemy_version_less_than('1.3'):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        return

    assert messages == [
      'BEGIN (implicit)',

      'SELECT articles.id AS articles_id, '
      'articles.headline AS articles_headline, '
      'articles.pub_date AS articles_pub_date, '
      'articles.reporter_id AS articles_reporter_id \n'
      'FROM articles',
      '()',

      'SELECT reporters.id AS reporters_id, '
      '(SELECT CAST(count(reporters.id) AS INTEGER) AS anon_2 \nFROM reporters) AS anon_1, '
      'reporters.first_name AS reporters_first_name, '
      'reporters.last_name AS reporters_last_name, '
      'reporters.email AS reporters_email, '
      'reporters.favorite_pet_kind AS reporters_favorite_pet_kind \n'
      'FROM reporters \n'
      'WHERE reporters.id IN (?, ?)',
      '(1, 2)',
    ]

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


def test_one_to_one(session_factory):
    session = session_factory()
    make_fixture(session)
    schema = get_schema(session)

    with mock_sqlalchemy_logging_handler() as sqlalchemy_logging_handler:
        # Starts new session to fully reset the engine / connection logging level
        session = session_factory()
        result = schema.execute("""
          query {
            reporters {
              firstName
              favoriteArticle {
                headline
              }
            }
          }
        """, context_value={"session": session})
        messages = sqlalchemy_logging_handler.messages

    assert len(messages) == 5

    if is_sqlalchemy_version_less_than('1.3'):
        # The batched SQL statement generated is different in 1.2.x
        # SQLAlchemy 1.3+ optimizes out a JOIN statement in `selectin`
        # See https://git.io/JewQu
        return

    assert messages == [
      'BEGIN (implicit)',

      'SELECT (SELECT CAST(count(reporters.id) AS INTEGER) AS anon_2 \nFROM reporters) AS anon_1, '
      'reporters.id AS reporters_id, '
      'reporters.first_name AS reporters_first_name, '
      'reporters.last_name AS reporters_last_name, '
      'reporters.email AS reporters_email, '
      'reporters.favorite_pet_kind AS reporters_favorite_pet_kind \n'
      'FROM reporters',
      '()',

      'SELECT articles.reporter_id AS articles_reporter_id, '
      'articles.id AS articles_id, '
      'articles.headline AS articles_headline, '
      'articles.pub_date AS articles_pub_date \n'
      'FROM articles \n'
      'WHERE articles.reporter_id IN (?, ?) '
      'ORDER BY articles.reporter_id',
      '(1, 2)'
    ]

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
