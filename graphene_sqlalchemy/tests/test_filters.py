import pytest
from sqlalchemy.sql.operators import is_

import graphene
from graphene import Connection, relay

from ..fields import SQLAlchemyConnectionField
from ..filters import FloatFilter
from ..types import ORMField, SQLAlchemyObjectType
from .models import (
    Article,
    Editor,
    HairKind,
    Image,
    Pet,
    Reader,
    Reporter,
    ShoppingCart,
    ShoppingCartItem,
    Tag,
)
from .utils import eventually_await_session, to_std_dicts

# TODO test that generated schema is correct for all examples with:
# with open('schema.gql', 'w') as fp:
#     fp.write(str(schema))


def assert_and_raise_result(result, expected):
    if result.errors:
        for error in result.errors:
            raise error
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


async def add_test_data(session):
    reporter = Reporter(first_name="John", last_name="Doe", favorite_pet_kind="cat")
    session.add(reporter)

    pet = Pet(name="Garfield", pet_kind="cat", hair_kind=HairKind.SHORT, legs=4)
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

    await eventually_await_session(session, "commit")


def create_schema(session):
    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            name = "Article"
            interfaces = (relay.Node,)

    class ImageType(SQLAlchemyObjectType):
        class Meta:
            model = Image
            name = "Image"
            interfaces = (relay.Node,)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            name = "Pet"
            interfaces = (relay.Node,)

    class ReaderType(SQLAlchemyObjectType):
        class Meta:
            model = Reader
            name = "Reader"
            interfaces = (relay.Node,)

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            name = "Reporter"
            interfaces = (relay.Node,)

    class TagType(SQLAlchemyObjectType):
        class Meta:
            model = Tag
            name = "Tag"
            interfaces = (relay.Node,)

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
        pets = SQLAlchemyConnectionField(PetType.connection)
        tags = SQLAlchemyConnectionField(TagType.connection)

        # def resolve_article(self, _info):
        #     return session.query(Article).first()

        # def resolve_image(self, _info):
        #     return session.query(Image).first()

        # def resolve_reporter(self, _info):
        #     return session.query(Reporter).first()

    return Query


# Test a simple example of filtering
@pytest.mark.asyncio
async def test_filter_simple(session):
    await add_test_data(session)

    Query = create_schema(session)

    query = """
        query {
          reporters (filter: {lastName: {eq: "Roe", like: "%oe"}}) {
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test a custom filter type
@pytest.mark.asyncio
async def test_filter_custom_type(session):
    await add_test_data(session)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test a 1:1 relationship
@pytest.mark.asyncio
async def test_filter_relationship_one_to_one(session):
    article = Article(headline="Hi!")
    image = Image(external_id=1, description="A beautiful image.")
    article.image = image
    session.add(article)
    session.add(image)
    await eventually_await_session(session, "commit")

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test a 1:n relationship
@pytest.mark.asyncio
async def test_filter_relationship_one_to_many(session):
    await add_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

    # TODO test containsExactly
    # # test containsExactly
    # query = """
    #     query {
    #       reporters (filter: {
    #         articles: {
    #           containsExactly: [
    #             {headline: {eq: "Hi!"}}
    #             {headline: {eq: "Hello!"}}
    #           ]
    #         }
    #       }) {
    #         edges {
    #           node {
    #             firstName
    #             lastName
    #           }
    #         }
    #       }
    #     }
    # """
    # expected = {
    #     "reporters": {"edges": [{"node": {"firstName": "John", "lastName": "Woe"}}]}
    # }
    # schema = graphene.Schema(query=Query)
    # result = await schema.execute_async(query, context_value={"session": session})
    # assert_and_raise_result(result, expected)


async def add_n2m_test_data(session):
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
    await eventually_await_session(session, "commit")


# Test n:m relationship contains
@pytest.mark.asyncio
async def test_filter_relationship_many_to_many_contains(session):
    await add_n2m_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


@pytest.mark.asyncio
async def test_filter_relationship_many_to_many_contains_with_and(session):
    """
    This test is necessary to ensure we don't accidentally turn and-contains filter
    into or-contains filters due to incorrect aliasing of the joined table.
    """
    await add_n2m_test_data(session)
    Query = create_schema(session)

    # test contains 1
    query = """
        query {
          articles (filter: {
            tags: {
              contains: [{
                and: [
                    { name: { in: ["sensational", "eye-grabbing"] } },
                    { name: { eq: "eye-grabbing" } },
                ]
            
              }
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test n:m relationship containsExactly
@pytest.mark.xfail
@pytest.mark.asyncio
async def test_filter_relationship_many_to_many_contains_exactly(session):
    raise NotImplementedError
    await add_n2m_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test n:m relationship both contains and containsExactly
@pytest.mark.xfail
@pytest.mark.asyncio
async def test_filter_relationship_many_to_many_contains_and_contains_exactly(session):
    raise NotImplementedError
    await add_n2m_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test n:m nested relationship
# TODO add containsExactly
@pytest.mark.asyncio
async def test_filter_relationship_many_to_many_nested(session):
    await add_n2m_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test connecting filters with "and"
@pytest.mark.asyncio
async def test_filter_logic_and(session):
    await add_test_data(session)

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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test connecting filters with "or"
@pytest.mark.asyncio
async def test_filter_logic_or(session):
    await add_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


# Test connecting filters with "and" and "or" together
@pytest.mark.asyncio
async def test_filter_logic_and_or(session):
    await add_test_data(session)
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)


async def add_hybrid_prop_test_data(session):
    cart = ShoppingCart()
    session.add(cart)
    await eventually_await_session(session, "commit")


def create_hybrid_prop_schema(session):
    class ShoppingCartItemType(SQLAlchemyObjectType):
        class Meta:
            model = ShoppingCartItem
            name = "ShoppingCartItem"
            interfaces = (relay.Node,)
            connection_class = Connection

    class ShoppingCartType(SQLAlchemyObjectType):
        class Meta:
            model = ShoppingCart
            name = "ShoppingCart"
            interfaces = (relay.Node,)
            connection_class = Connection

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        items = SQLAlchemyConnectionField(ShoppingCartItemType.connection)
        carts = SQLAlchemyConnectionField(ShoppingCartType.connection)

    return Query


# Test filtering over and returning hybrid_property
@pytest.mark.asyncio
async def test_filter_hybrid_property(session):
    await add_hybrid_prop_test_data(session)
    Query = create_hybrid_prop_schema(session)

    # test hybrid_prop_int
    query = """
        query {
          carts (filter: {hybridPropInt: {eq: 42}}) {
            edges {
                node {
                    hybridPropInt
                }
            }
          }
        }
    """
    expected = {
        "carts": {
            "edges": [
                {"node": {"hybridPropInt": 42}},
            ]
        },
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

    # test hybrid_prop_float
    query = """
        query {
          carts (filter: {hybridPropFloat: {gt: 42}}) {
            edges {
                node {
                    hybridPropFloat
                }
            }
          }
        }
    """
    expected = {
        "carts": {
            "edges": [
                {"node": {"hybridPropFloat": 42.3}},
            ]
        },
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

    # test hybrid_prop different model without expression
    query = """
        query {
          carts {
            edges {
              node {
                hybridPropFirstShoppingCartItem {
                  id
                }
              }
            }
          }
        }
    """
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert len(result["carts"]["edges"]) == 1

    # test hybrid_prop different model with expression
    query = """
        query {
          carts {
            edges {
              node {
                hybridPropFirstShoppingCartItemExpression {
                  id
                }
              }
            }
          }
        }
    """

    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert len(result["carts"]["edges"]) == 1

    # test hybrid_prop list of models
    query = """
        query {
          carts {
            edges {
              node {
                hybridPropShoppingCartItemList {
                  id
                }
              }
            }
          }
        }
    """
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert len(result["carts"]["edges"]) == 1
    assert (
        len(result["carts"]["edges"][0]["node"]["hybridPropShoppingCartItemList"]) == 2
    )


# Test edge cases to improve test coverage
@pytest.mark.asyncio
async def test_filter_edge_cases(session):
    await add_test_data(session)

    # test disabling filtering
    class ArticleType(SQLAlchemyObjectType):
        class Meta:
            model = Article
            name = "Article"
            interfaces = (relay.Node,)
            connection_class = Connection

    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        articles = SQLAlchemyConnectionField(ArticleType.connection, filter=None)

    schema = graphene.Schema(query=Query)
    assert not hasattr(schema, "ArticleTypeFilter")


# Test additional filter types to improve test coverage
@pytest.mark.asyncio
async def test_additional_filters(session):
    await add_test_data(session)
    Query = create_schema(session)

    # test n_eq and not_in filters
    query = """
        query {
          reporters (filter: {firstName: {nEq: "Jane"}, lastName: {notIn: "Doe"}}) {
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
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)

    # test gt, lt, gte, and lte filters
    query = """
        query {
          pets (filter: {legs: {gt: 2, lt: 4, gte: 3, lte: 3}}) {
            edges {
                node {
                    name
                }
            }
          }
        }
    """
    expected = {
        "pets": {"edges": [{"node": {"name": "Snoopy"}}]},
    }
    schema = graphene.Schema(query=Query)
    result = await schema.execute_async(query, context_value={"session": session})
    assert_and_raise_result(result, expected)
