import pytest

import graphene
from graphene import Connection, relay

from ..fields import SQLAlchemyConnectionField
from ..filters import FloatFilter
from ..types import SQLAlchemyObjectType
from .models import Article, Editor, HairKind, Image, Pet, Reporter, Tag
from .utils import to_std_dicts


def add_test_data(session):
    reporter = Reporter(
        first_name='John', last_name='Doe', favorite_pet_kind='cat')
    session.add(reporter)
    pet = Pet(name='Garfield', pet_kind='cat', hair_kind=HairKind.SHORT)
    pet.reporter = reporter
    session.add(pet)
    pet = Pet(name='Snoopy', pet_kind='dog', hair_kind=HairKind.SHORT)
    pet.reporter = reporter
    session.add(pet)
    reporter = Reporter(
        first_name='John', last_name='Woe', favorite_pet_kind='cat')
    session.add(reporter)
    article = Article(headline='Hi!')
    article.reporter = reporter
    session.add(article)
    article = Article(headline='Hello!')
    article.reporter = reporter
    session.add(article)
    reporter = Reporter(
        first_name='Jane', last_name='Roe', favorite_pet_kind='dog')
    session.add(reporter)
    pet = Pet(name='Lassie', pet_kind='dog', hair_kind=HairKind.LONG)
    pet.reporter = reporter
    session.add(pet)
    editor = Editor(name="Jack")
    session.add(editor)
    session.commit()


def create_schema(session):
    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            name = "Article"
            interfaces = (relay.Node,)
            connection_class = Connection

    class ImageType(SQLAlchemyObjectType):
        class Meta:
            model = Image
            name = "Image"
            interfaces = (relay.Node,)
            connection_class = Connection

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            name = "Pet"
            interfaces = (relay.Node,)
            connection_class = Connection

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            name = "Reporter"
            interfaces = (relay.Node,)
            connection_class = Connection

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        # # TODO how to create filterable singular field?
        # article = graphene.Field(ArticleType)
        articles = SQLAlchemyConnectionField(ArticleType.connection)
        # image = graphene.Field(ImageType)
        images = SQLAlchemyConnectionField(ImageType.connection)
        # reporter = graphene.Field(ReporterType)
        reporters = SQLAlchemyConnectionField(ReporterType.connection)

        # def resolve_article(self, _info):
        #     return session.query(Article).first()

        # def resolve_image(self, _info):
        #     return session.query(Image).first()

        # def resolve_reporter(self, _info):
        #     return session.query(Reporter).first()

    return Query


# Test a simple example of filtering
def test_filter_simple(session):
    add_test_data(session)

    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {lastName: {eq: "Roe"}}) {
            edges {
                node {
                    firstName
                }
            }
          }
        }
    """
    expected = {
        "reporters": {"edges": [{"node": {"firstName": "Jane"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a custom filter type
@pytest.mark.xfail
def test_filter_custom_type(session):
    add_test_data(session)
    Query = create_schema(session)

    class MathFilter(FloatFilter):
        class Meta:
            type = graphene.Float

        @classmethod
        def divisible_by(cls, query, field, val: graphene.Float) -> bool:
            return field % val == 0.

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            name = "Pet"
            interfaces = (relay.Node,)
            connection_class = Connection

    class ExtraQuery:
        pets = SQLAlchemyConnectionField(
            PetType.connection, filter=MathFilter()
        )

    class CustomQuery(Query, ExtraQuery):
        pass

    query = """
        query {
          pets (filter: {
            legs: {divisibleBy: 2}
          }) {
            name
          }
        }
    """
    expected = {
        "pets": [{"name": "Garfield"}, {"name": "Lassie"}],
    }
    schema = graphene.Schema(query=CustomQuery)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a 1:1 relationship
def test_filter_relationship_one_to_one(session):
    article = Article(headline='Hi!')
    image = Image(external_id=1, description="A beautiful image.")
    article.image = image
    session.add(article)
    session.add(image)
    session.commit()

    Query = create_schema(session)

    query = """
        query {
          articles (filter: {
            image: {description: {eq: "A beautiful image."}}
          }) {
            edges {
                node {
                    headline
                }
            }
          }
        }
    """
    expected = {
        "articles": {"edges": [{"node": {"headline": "Hi!"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a 1:n relationship
def test_filter_relationship_one_to_many(session):
    add_test_data(session)
    Query = create_schema(session)

    # test contains
    query = """
        query {
          reporters (filter: {
            articles: {
              contains: [{headline: {eq: "Hi!"}}],
            }
          }) {
            edges {
              node {
                lastName
              }
            }
          }
        }
    """
    expected = {
        "reporters": {"edges": [{"node": {"lastName": "Woe"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test containsExactly
    query = """
        query {
          reporters (filter: {
            articles: {
              containsExactly: [
                {headline: {eq: "Hi!"}}
                {headline: {eq: "Hello!"}}
              ]
            }
          }) {
            edges {
              node {
                firstName
                lastName
              }
            }
          }
        }
    """
    expected = {
        "reporters": {"edges": [{"node": {"firstName": "John", "lastName": "Woe"}}]}
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={'session': session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a n:m relationship
@pytest.mark.xfail
def test_filter_relationship_many_to_many(session):
    article1 = Article(headline='Article! Look!')
    article2 = Article(headline='Woah! Another!')
    tag1 = Tag(name="sensational")
    tag2 = Tag(name="eye-grabbing")
    article1.tags.append(tag1)
    article2.tags.append([tag1, tag2])
    session.add(article1)
    session.add(article2)
    session.add(tag1)
    session.add(tag2)
    session.commit()

    Query = create_schema(session)

    # test contains
    query = """
    query {
      articles (filter: {
        tags: {
          contains: {
            name: { in: ["sensational", "eye-grabbing"] }
          }
        }
      }) {
        headline
      }
    }
    """
    expected = {
        "articles": [
            {"headline": "Woah! Another!"},
            {"headline": "Article! Look!"},
        ],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test containsAllOf
    query = """
        query {
          articles (filter: {
            tags: {
              containsAllOf: [
                { tag: { name: { eq: "eye-grabbing" } } },
                { tag: { name: { eq: "sensational" } } },
              ]
            }
          }) {
            headline
          }
        }
    """
    expected = {
        "articles": [{"headline": "Woah! Another!"}],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test containsExactly
    query = """
        query {
          articles (filter: {
              containsExactly: [
                { tag: { name: { eq: "sensational" } } }
              ]
          }) {
            headline
          }
        }
    """
    expected = {
        "articles": [{"headline": "Article! Look!"}],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "and"
@pytest.mark.xfail
def test_filter_logic_and(session):
    add_test_data(session)

    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            and: [
                {firstName: "John"},
                {favoritePetKind: "cat"},
            ]
        }) {
            lastName
          }
        }
    """
    expected = {
        "reporters": [{"lastName": "Doe"}, {"lastName": "Woe"}],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "or"
@pytest.mark.xfail
def test_filter_logic_or(session):
    add_test_data(session)
    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            or: [
                {lastName: "Woe"},
                {favoritePetKind: "dog"},
            ]
        }) {
            firstName
            lastName
          }
        }
    """
    expected = {
        "reporters": [
            {"firstName": "John", "lastName": "Woe"},
            {"firstName": "Jane", "lastName": "Roe"},
        ],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "and" and "or" together
@pytest.mark.xfail
def test_filter_logic_and_or(session):
    add_test_data(session)
    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            and: [
                {firstName: "John"},
                or : [
                    {lastName: "Doe"},
                    {favoritePetKind: "cat"},
                ]
            ]
        }) {
            firstName
          }
        }
    """
    expected = {
        "reporters": [{"firstName": "John"}, {"firstName": "Jane"}],
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# TODO hybrid property
@pytest.mark.xfail
def test_filter_hybrid_property(session):
    raise NotImplementedError
