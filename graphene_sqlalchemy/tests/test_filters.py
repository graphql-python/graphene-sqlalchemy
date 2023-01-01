import pytest
from sqlalchemy.sql.operators import is_

import graphene
from graphene import Connection, relay

from ..fields import SQLAlchemyConnectionField
from ..filters import FloatFilter
from ..types import ORMField, SQLAlchemyObjectType
from .models import Article, Editor, HairKind, Image, Pet, Reader, Reporter, Tag
from .utils import to_std_dicts

# TODO test that generated schema is correct for all examples with:
# with open('schema.gql', 'w') as fp:
#     fp.write(str(schema))


def add_test_data(session):
    reporter = Reporter(first_name="John", last_name="Doe", favorite_pet_kind="cat")
    session.add(reporter)

    pet = Pet(name="Garfield", pet_kind="cat", hair_kind=HairKind.SHORT)
    pet.reporter = reporter
    session.add(pet)

    pet = Pet(name="Snoopy", pet_kind="dog", hair_kind=HairKind.SHORT, legs=3)
    pet.reporter = reporter
    session.add(pet)

    reporter = Reporter(first_name="John", last_name="Woe", favorite_pet_kind="cat")
    session.add(reporter)

    article = Article(headline="Hi!")
    article.reporter = reporter
    session.add(article)

    article = Article(headline="Hello!")
    article.reporter = reporter
    session.add(article)

    reporter = Reporter(first_name="Jane", last_name="Roe", favorite_pet_kind="dog")
    session.add(reporter)

    pet = Pet(name="Lassie", pet_kind="dog", hair_kind=HairKind.LONG)
    pet.reporter = reporter
    session.add(pet)

    editor = Editor(name="Jack")
    session.add(editor)

    session.commit()


def add_n2m_test_data(session):
    # create objects
    reader1 = Reader(name="Ada")
    reader2 = Reader(name="Bip")
    article1 = Article(headline="Article! Look!")
    article2 = Article(headline="Woah! Another!")
    tag1 = Tag(name="sensational")
    tag2 = Tag(name="eye-grabbing")
    image1 = Image(description="article 1")
    image2 = Image(description="article 2")

    # set relationships
    article1.tags = [tag1]
    article2.tags = [tag1, tag2]
    article1.image = image1
    article2.image = image2
    reader1.articles = [article1]
    reader2.articles = [article1, article2]

    # save
    session.add(image1)
    session.add(image2)
    session.add(tag1)
    session.add(tag2)
    session.add(article1)
    session.add(article2)
    session.add(reader1)
    session.add(reader2)
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

    class ReaderType(SQLAlchemyObjectType):
        class Meta:
            model = Reader
            name = "Reader"
            interfaces = (relay.Node,)
            connection_class = Connection

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            name = "Reporter"
            interfaces = (relay.Node,)
            connection_class = Connection

    class TagType(SQLAlchemyObjectType):
        class Meta:
            model = Tag
            name = "Tag"
            interfaces = (relay.Node,)
            connection_class = Connection

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        # # TODO how to create filterable singular field?
        # article = graphene.Field(ArticleType)
        articles = SQLAlchemyConnectionField(ArticleType.connection)
        # image = graphene.Field(ImageType)
        images = SQLAlchemyConnectionField(ImageType.connection)
        readers = SQLAlchemyConnectionField(ReaderType.connection)
        # reporter = graphene.Field(ReporterType)
        reporters = SQLAlchemyConnectionField(ReporterType.connection)
        tags = SQLAlchemyConnectionField(TagType.connection)

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
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a custom filter type
def test_filter_custom_type(session):
    add_test_data(session)

    class MathFilter(FloatFilter):
        class Meta:
            graphene_type = graphene.Float

        @classmethod
        def divisible_by_filter(cls, query, field, val: int) -> bool:
            return is_(field % val, 0)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            name = "Pet"
            interfaces = (relay.Node,)
            connection_class = Connection

        legs = ORMField(filter_type=MathFilter)

    class Query(graphene.ObjectType):
        pets = SQLAlchemyConnectionField(PetType.connection)

    query = """
        query {
          pets (filter: {
            legs: {divisibleBy: 2}
          }) {
            edges {
                node {
                    name
                }
            }
          }
        }
    """
    expected = {
        "pets": {
            "edges": [{"node": {"name": "Garfield"}}, {"node": {"name": "Lassie"}}]
        },
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test a 1:1 relationship
def test_filter_relationship_one_to_one(session):
    article = Article(headline="Hi!")
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
    result = schema.execute(query, context_value={"session": session})
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
    result = schema.execute(query, context_value={"session": session})
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
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test n:m relationship contains
def test_filter_relationship_many_to_many_contains(session):
    add_n2m_test_data(session)
    Query = create_schema(session)

    # test contains 1
    query = """
        query {
          articles (filter: {
            tags: {
              contains: [
                { name: { in: ["sensational", "eye-grabbing"] } },
              ]
            }
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
        "articles": {
            "edges": [
                {"node": {"headline": "Article! Look!"}},
                {"node": {"headline": "Woah! Another!"}},
            ],
        },
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test contains 2
    query = """
        query {
          articles (filter: {
            tags: {
              contains: [
                { name: { eq: "eye-grabbing" } },
              ]
            }
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
        "articles": {
            "edges": [
                {"node": {"headline": "Woah! Another!"}},
            ],
        },
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test reverse
    query = """
        query {
          tags (filter: {
            articles: {
              contains: [
                { headline: { eq: "Article! Look!" } },
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "tags": {
            "edges": [
                {"node": {"name": "sensational"}},
            ],
        },
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test n:m relationship containsExactly
def test_filter_relationship_many_to_many_contains_exactly(session):
    add_n2m_test_data(session)
    Query = create_schema(session)

    # test containsExactly 1
    query = """
        query {
          articles (filter: {
            tags: {
              containsExactly: [
                { name: { eq: "eye-grabbing" } },
                { name: { eq: "sensational" } },
              ]
            }
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
        "articles": {"edges": [{"node": {"headline": "Woah! Another!"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test containsExactly 2
    query = """
        query {
          articles (filter: {
            tags: {
              containsExactly: [
                { name: { eq: "sensational" } }
              ]
            }
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
        "articles": {"edges": [{"node": {"headline": "Article! Look!"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test reverse
    query = """
        query {
          tags (filter: {
            articles: {
              containsExactly: [
                { headline: { eq: "Article! Look!" } },
                { headline: { eq: "Woah! Another!" } },
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "tags": {"edges": [{"node": {"name": "eye-grabbing"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test n:m relationship both contains and containsExactly
def test_filter_relationship_many_to_many_contains_and_contains_exactly(session):
    add_n2m_test_data(session)
    Query = create_schema(session)

    query = """
        query {
          articles (filter: {
            tags: {
              contains: [
                { name: { eq: "eye-grabbing" } },
              ]
              containsExactly: [
                { name: { eq: "eye-grabbing" } },
                { name: { eq: "sensational" } },
              ]
            }
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
        "articles": {"edges": [{"node": {"headline": "Woah! Another!"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test n:m nested relationship
# TODO add containsExactly
def test_filter_relationship_many_to_many_nested(session):
    add_n2m_test_data(session)
    Query = create_schema(session)

    # test readers->articles relationship
    query = """
        query {
          readers (filter: {
            articles: {
              contains: [
                { headline: { eq: "Woah! Another!" } },
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "readers": {"edges": [{"node": {"name": "Bip"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test nested readers->articles->tags
    query = """
        query {
          readers (filter: {
            articles: {
              contains: [
                {
                  tags: {
                    contains: [
                      { name: { eq: "eye-grabbing" } },
                    ]
                  }
                }
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "readers": {"edges": [{"node": {"name": "Bip"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test nested reverse
    query = """
        query {
          tags (filter: {
            articles: {
              contains: [
                {
                  readers: {
                    contains: [
                      { name: { eq: "Ada" } },
                    ]
                  }
                }
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "tags": {"edges": [{"node": {"name": "sensational"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    # test filter on both levels of nesting
    query = """
        query {
          readers (filter: {
            articles: {
              contains: [
                { headline: { eq: "Woah! Another!" } },
                {
                  tags: {
                    contains: [
                      { name: { eq: "eye-grabbing" } },
                    ]
                  }
                }
              ]
            }
          }) {
            edges {
              node {
                name
              }
            }
          }
        }
    """
    expected = {
        "readers": {"edges": [{"node": {"name": "Bip"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "and"
def test_filter_logic_and(session):
    add_test_data(session)

    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            and: [
                { firstName: { eq: "John" } },
                # TODO get enums working for filters
                # { favoritePetKind: { eq: "cat" } },
            ]
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
        "reporters": {
            "edges": [{"node": {"lastName": "Doe"}}, {"node": {"lastName": "Woe"}}]
        },
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "or"
def test_filter_logic_or(session):
    add_test_data(session)
    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            or: [
                { lastName: { eq: "Woe" } },
                # TODO get enums working for filters
                #{ favoritePetKind: { eq: "dog" } },
            ]
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
        "reporters": {
            "edges": [
                {"node": {"firstName": "John", "lastName": "Woe"}},
                # TODO get enums working for filters
                # {"node": {"firstName": "Jane", "lastName": "Roe"}},
            ]
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# Test connecting filters with "and" and "or" together
def test_filter_logic_and_or(session):
    add_test_data(session)
    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {
            and: [
                { firstName: { eq: "John" } },
                {
                    or: [
                        { lastName: { eq: "Doe" } },
                        # TODO get enums working for filters
                        # { favoritePetKind: { eq: "cat" } },
                    ]
                }
            ]
        }) {
            edges {
                node {
                    firstName
                }
            }
          }
        }
    """
    expected = {
        "reporters": {
            "edges": [
                {"node": {"firstName": "John"}},
                # {"node": {"firstName": "Jane"}},
            ],
        }
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


# TODO hybrid property
@pytest.mark.xfail
def test_filter_hybrid_property(session):
    raise NotImplementedError
