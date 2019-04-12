import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import graphene
from graphene.relay import Connection, Node

from ..fields import SQLAlchemyConnectionField
from ..registry import reset_global_registry
from ..types import SQLAlchemyObjectType
from ..utils import get_sort_argument_for_model, get_sort_enum_for_model
from .models import Article, Base, Editor, HairKind, Pet, Reporter

db = create_engine("sqlite://")  # use in-memory database


@pytest.yield_fixture(scope="function")
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
    reporter = Reporter(
        first_name='John', last_name='Doe', favorite_pet_kind='cat')
    session.add(reporter)
    pet = Pet(name='Garfield', pet_kind='cat', hair_kind=HairKind.SHORT)
    session.add(pet)
    pet.reporters.append(reporter)
    article = Article(headline='Hi!')
    article.reporter = reporter
    session.add(article)
    reporter = Reporter(
        first_name='Jane', last_name='Roe', favorite_pet_kind='dog')
    session.add(reporter)
    pet = Pet(name='Lassie', pet_kind='dog', hair_kind=HairKind.LONG)
    pet.reporters.append(reporter)
    session.add(pet)
    editor = Editor(name="Jack")
    session.add(editor)
    session.commit()


def test_should_query_well(session):
    setup_fixtures(session)

    class PetType(SQLAlchemyObjectType):

        class Meta:
            model = Pet

    class ReporterType(SQLAlchemyObjectType):
        class Meta:
            model = Reporter

    class Query(graphene.ObjectType):
        reporter = graphene.Field(ReporterType)
        reporters = graphene.List(ReporterType)
        pets = graphene.List(PetType, kind=graphene.Argument(
            PetType._meta.fields['pet_kind'].type))

        def resolve_reporter(self, _info):
            return session.query(Reporter).first()

        def resolve_reporters(self, _info):
            return session.query(Reporter)

        def resolve_pets(self, _info, kind):
            query = session.query(Pet)
            if kind:
                query = query.filter_by(pet_kind=kind)
            return query

    query = """
        query ReporterQuery {
          reporter {
            firstName,
            lastName,
            email,
            favoritePetKind,
            pets {
              name
              petKind
            }
          }
          reporters {
            firstName
          }
          pets(kind: DOG) {
            name
            petKind
          }
        }
    """
    expected = {
        'reporter': {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': None,
            'favoritePetKind': 'CAT',
            'pets': [{
                'name': 'Garfield',
                'petKind': 'CAT'
            }]
        },
        'reporters': [{
            'firstName': 'John',
        }, {
            'firstName': 'Jane',
        }],
        'pets': [{
            'name': 'Lassie',
            'petKind': 'DOG'
        }]
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


def test_should_query_enums(session):
    setup_fixtures(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(PetType)

        def resolve_pet(self, _info):
            return session.query(Pet).first()

    query = """
        query PetQuery {
          pet {
            name,
            petKind
            hairKind
          }
        }
    """
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    schema = graphene.Schema(query=Query)
    result = schema.execute(query)
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


def test_enum_parameter(session):
    setup_fixtures(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(
            PetType,
            kind=graphene.Argument(PetType._meta.fields['pet_kind'].type.of_type))

        def resolve_pet(self, info, kind=None):
            query = session.query(Pet)
            if kind:
                query = query.filter(Pet.pet_kind == kind)
            return query.first()

    query = """
        query PetQuery($kind: PetKind) {
          pet(kind: $kind) {
            name,
            petKind
            hairKind
          }
        }
    """
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, variables={"kind": "CAT"})
    assert not result.errors
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    assert result.data == expected
    result = schema.execute(query, variables={"kind": "DOG"})
    assert not result.errors
    expected = {"pet": {"name": "Lassie", "petKind": "DOG", "hairKind": "LONG"}}
    assert result.data == expected


def test_py_enum_parameter(session):
    setup_fixtures(session)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    class Query(graphene.ObjectType):
        pet = graphene.Field(PetType, kind=graphene.Argument(PetType._meta.fields['hair_kind'].type.of_type))

        def resolve_pet(self, _info, kind=None):
            query = session.query(Pet)
            if kind:
                # XXX Why kind passed in as a str instead of a Hairkind instance?
                query = query.filter(Pet.hair_kind == HairKind(kind))
            return query.first()

    query = """
        query PetQuery($kind: HairKind) {
          pet(kind: $kind) {
            name,
            petKind
            hairKind
          }
        }
    """
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, variables={"kind": "SHORT"})
    assert not result.errors
    expected = {"pet": {"name": "Garfield", "petKind": "CAT", "hairKind": "SHORT"}}
    assert result.data == expected
    result = schema.execute(query, variables={"kind": "LONG"})
    assert not result.errors
    expected = {"pet": {"name": "Lassie", "petKind": "DOG", "hairKind": "LONG"}}
    assert result.data == expected


def test_should_node(session):
    setup_fixtures(session)

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

        # @classmethod
        # def get_node(cls, id, info):
        #     return Article(id=1, headline='Article node')

    class ArticleConnection(Connection):
        class Meta:
            node = ArticleNode

    class Query(graphene.ObjectType):
        node = Node.Field()
        reporter = graphene.Field(ReporterNode)
        article = graphene.Field(ArticleNode)
        all_articles = SQLAlchemyConnectionField(ArticleConnection)

        def resolve_reporter(self, _info):
            return session.query(Reporter).first()

        def resolve_article(self, _info):
            return session.query(Article).first()

    query = """
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
    """
    expected = {
        "reporter": {
            "id": "UmVwb3J0ZXJOb2RlOjE=",
            "firstName": "John",
            "lastName": "Doe",
            "email": None,
            "articles": {"edges": [{"node": {"headline": "Hi!"}}]},
        },
        "allArticles": {"edges": [{"node": {"headline": "Hi!"}}]},
        "myArticle": {"id": "QXJ0aWNsZU5vZGU6MQ==", "headline": "Hi!"},
    }
    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


def test_should_custom_identifier(session):
    setup_fixtures(session)

    class EditorNode(SQLAlchemyObjectType):
        class Meta:
            model = Editor
            interfaces = (Node,)

    class EditorConnection(Connection):
        class Meta:
            node = EditorNode

    class Query(graphene.ObjectType):
        node = Node.Field()
        all_editors = SQLAlchemyConnectionField(EditorConnection)

    query = """
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
    """
    expected = {
        "allEditors": {"edges": [{"node": {"id": "RWRpdG9yTm9kZTox", "name": "Jack"}}]},
        "node": {"name": "Jack"},
    }

    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


def test_should_mutate_well(session):
    setup_fixtures(session)

    class EditorNode(SQLAlchemyObjectType):
        class Meta:
            model = Editor
            interfaces = (Node,)

    class ReporterNode(SQLAlchemyObjectType):
        class Meta:
            model = Reporter
            interfaces = (Node,)

        @classmethod
        def get_node(cls, id, info):
            return Reporter(id=2, first_name="Cookie Monster")

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

        def mutate(self, info, headline, reporter_id):
            new_article = Article(headline=headline, reporter_id=reporter_id)

            session.add(new_article)
            session.commit()
            ok = True

            return CreateArticle(article=new_article, ok=ok)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        create_article = CreateArticle.Field()

    query = """
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
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected


def sort_setup(session):
    pets = [
        Pet(id=2, name="Lassie", pet_kind="dog", hair_kind=HairKind.LONG),
        Pet(id=22, name="Alf", pet_kind="cat", hair_kind=HairKind.LONG),
        Pet(id=3, name="Barf", pet_kind="dog", hair_kind=HairKind.LONG),
    ]
    session.add_all(pets)
    session.commit()


def test_sort(session):
    sort_setup(session)

    class PetNode(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (Node,)

    class PetConnection(Connection):
        class Meta:
            node = PetNode

    class Query(graphene.ObjectType):
        defaultSort = SQLAlchemyConnectionField(PetConnection)
        nameSort = SQLAlchemyConnectionField(PetConnection)
        multipleSort = SQLAlchemyConnectionField(PetConnection)
        descSort = SQLAlchemyConnectionField(PetConnection)
        singleColumnSort = SQLAlchemyConnectionField(
            PetConnection, sort=graphene.Argument(get_sort_enum_for_model(Pet))
        )
        noDefaultSort = SQLAlchemyConnectionField(
            PetConnection, sort=get_sort_argument_for_model(Pet, False)
        )
        noSort = SQLAlchemyConnectionField(PetConnection, sort=None)

    query = """
        query sortTest {
            defaultSort{
                edges{
                    node{
                        id
                    }
                }
            }
            nameSort(sort: NAME_ASC){
                edges{
                    node{
                        name
                    }
                }
            }
            multipleSort(sort: [PET_KIND_ASC, NAME_DESC]){
                edges{
                    node{
                        name
                        petKind
                    }
                }
            }
            descSort(sort: [NAME_DESC]){
                edges{
                    node{
                        name
                    }
                }
            }
            singleColumnSort(sort: NAME_DESC){
                edges{
                    node{
                        name
                    }
                }
            }
            noDefaultSort(sort: NAME_ASC){
                edges{
                    node{
                        name
                    }
                }
            }
        }
    """

    def makeNodes(nodeList):
        nodes = [{"node": item} for item in nodeList]
        return {"edges": nodes}

    expected = {
        "defaultSort": makeNodes(
            [{"id": "UGV0Tm9kZToy"}, {"id": "UGV0Tm9kZToz"}, {"id": "UGV0Tm9kZToyMg=="}]
        ),
        "nameSort": makeNodes([{"name": "Alf"}, {"name": "Barf"}, {"name": "Lassie"}]),
        "noDefaultSort": makeNodes(
            [{"name": "Alf"}, {"name": "Barf"}, {"name": "Lassie"}]
        ),
        "multipleSort": makeNodes(
            [
                {"name": "Alf", "petKind": "CAT"},
                {"name": "Lassie", "petKind": "DOG"},
                {"name": "Barf", "petKind": "DOG"},
            ]
        ),
        "descSort": makeNodes([{"name": "Lassie"}, {"name": "Barf"}, {"name": "Alf"}]),
        "singleColumnSort": makeNodes(
            [{"name": "Lassie"}, {"name": "Barf"}, {"name": "Alf"}]
        ),
    }  # yapf: disable

    schema = graphene.Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    queryError = """
        query sortTest {
            singleColumnSort(sort: [pet_kind_asc, name_desc]){
                edges{
                    node{
                        name
                    }
                }
            }
        }
    """
    result = schema.execute(queryError, context_value={"session": session})
    assert result.errors is not None

    queryNoSort = """
        query sortTest {
            noDefaultSort{
                edges{
                    node{
                        name
                    }
                }
            }
            noSort{
                edges{
                    node{
                        name
                    }
                }
            }
        }
    """

    expectedNoSort = {
        "noDefaultSort": makeNodes(
            [{"name": "Alf"}, {"name": "Barf"}, {"name": "Lassie"}]
        ),
        "noSort": makeNodes([{"name": "Alf"}, {"name": "Barf"}, {"name": "Lassie"}]),
    }  # yapf: disable

    result = schema.execute(queryNoSort, context_value={"session": session})
    assert not result.errors
    for key, value in result.data.items():
        assert set(node["node"]["name"] for node in value["edges"]) == set(
            node["node"]["name"] for node in expectedNoSort[key]["edges"]
        )


def to_std_dicts(value):
    """Convert nested ordered dicts to normal dicts for better comparison."""
    if isinstance(value, dict):
        return {k: to_std_dicts(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_std_dicts(v) for v in value]
    else:
        return value
