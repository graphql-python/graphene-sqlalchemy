import pytest
import sqlalchemy as sa

from graphene import Argument, Enum, List, ObjectType, Schema
from graphene.relay import Connection, Node

from ..fields import SQLAlchemyConnectionField
from ..types import SQLAlchemyObjectType
from ..utils import to_type_name
from .models import Base, HairKind, Pet
from .test_query import to_std_dicts


def add_pets(session):
    pets = [
        Pet(id=1, name="Lassie", pet_kind="dog", hair_kind=HairKind.LONG),
        Pet(id=2, name="Barf", pet_kind="dog", hair_kind=HairKind.LONG),
        Pet(id=3, name="Alf", pet_kind="cat", hair_kind=HairKind.LONG),
    ]
    session.add_all(pets)
    session.commit()


def test_sort_enum():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    sort_enum = PetType.sort_enum()
    assert isinstance(sort_enum, type(Enum))
    assert sort_enum._meta.name == "PetTypeSortEnum"
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "NAME_ASC",
        "NAME_DESC",
        "PET_KIND_ASC",
        "PET_KIND_DESC",
        "HAIR_KIND_ASC",
        "HAIR_KIND_DESC",
        "REPORTER_ID_ASC",
        "REPORTER_ID_DESC",
    ]
    assert str(sort_enum.ID_ASC.value.value) == "pets.id ASC"
    assert str(sort_enum.ID_DESC.value.value) == "pets.id DESC"
    assert str(sort_enum.HAIR_KIND_ASC.value.value) == "pets.hair_kind ASC"
    assert str(sort_enum.HAIR_KIND_DESC.value.value) == "pets.hair_kind DESC"


def test_sort_enum_with_custom_name():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    sort_enum = PetType.sort_enum(name="CustomSortName")
    assert isinstance(sort_enum, type(Enum))
    assert sort_enum._meta.name == "CustomSortName"


def test_sort_enum_cache():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    sort_enum = PetType.sort_enum()
    sort_enum_2 = PetType.sort_enum()
    assert sort_enum_2 is sort_enum
    sort_enum_2 = PetType.sort_enum(name="PetTypeSortEnum")
    assert sort_enum_2 is sort_enum
    err_msg = "Sort enum for PetType has already been customized"
    with pytest.raises(ValueError, match=err_msg):
        PetType.sort_enum(name="CustomSortName")
    with pytest.raises(ValueError, match=err_msg):
        PetType.sort_enum(only_fields=["id"])
    with pytest.raises(ValueError, match=err_msg):
        PetType.sort_enum(only_indexed=True)
    with pytest.raises(ValueError, match=err_msg):
        PetType.sort_enum(get_symbol_name=lambda: "foo")


def test_sort_enum_with_excluded_field_in_object_type():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            exclude_fields = ["reporter_id"]

    sort_enum = PetType.sort_enum()
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "NAME_ASC",
        "NAME_DESC",
        "PET_KIND_ASC",
        "PET_KIND_DESC",
        "HAIR_KIND_ASC",
        "HAIR_KIND_DESC",
    ]


def test_sort_enum_only_fields():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    sort_enum = PetType.sort_enum(only_fields=["id", "name"])
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "NAME_ASC",
        "NAME_DESC",
    ]


def test_sort_argument():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    sort_arg = PetType.sort_argument()
    assert isinstance(sort_arg, Argument)

    assert isinstance(sort_arg.type, List)
    sort_enum = sort_arg.type._of_type
    assert isinstance(sort_enum, type(Enum))
    assert sort_enum._meta.name == "PetTypeSortEnum"
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "NAME_ASC",
        "NAME_DESC",
        "PET_KIND_ASC",
        "PET_KIND_DESC",
        "HAIR_KIND_ASC",
        "HAIR_KIND_DESC",
        "REPORTER_ID_ASC",
        "REPORTER_ID_DESC",
    ]
    assert str(sort_enum.ID_ASC.value.value) == "pets.id ASC"
    assert str(sort_enum.ID_DESC.value.value) == "pets.id DESC"
    assert str(sort_enum.HAIR_KIND_ASC.value.value) == "pets.hair_kind ASC"
    assert str(sort_enum.HAIR_KIND_DESC.value.value) == "pets.hair_kind DESC"

    assert sort_arg.default_value == ["ID_ASC"]
    assert str(sort_enum.ID_ASC.value.value) == "pets.id ASC"


def test_sort_argument_with_excluded_fields_in_object_type():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            exclude_fields = ["hair_kind", "reporter_id"]

    sort_arg = PetType.sort_argument()
    sort_enum = sort_arg.type._of_type
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "NAME_ASC",
        "NAME_DESC",
        "PET_KIND_ASC",
        "PET_KIND_DESC",
    ]
    assert sort_arg.default_value == ["ID_ASC"]


def test_sort_argument_only_fields():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            only_fields = ["id", "pet_kind"]

    sort_arg = PetType.sort_argument()
    sort_enum = sort_arg.type._of_type
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "PET_KIND_ASC",
        "PET_KIND_DESC",
    ]
    assert sort_arg.default_value == ["ID_ASC"]


def test_sort_argument_for_multi_column_pk():
    class MultiPkTestModel(Base):
        __tablename__ = "multi_pk_test_table"
        foo = sa.Column(sa.Integer, primary_key=True)
        bar = sa.Column(sa.Integer, primary_key=True)

    class MultiPkTestType(SQLAlchemyObjectType):
        class Meta:
            model = MultiPkTestModel

    sort_arg = MultiPkTestType.sort_argument()
    assert sort_arg.default_value == ["FOO_ASC", "BAR_ASC"]


def test_sort_argument_only_indexed():
    class IndexedTestModel(Base):
        __tablename__ = "indexed_test_table"
        id = sa.Column(sa.Integer, primary_key=True)
        foo = sa.Column(sa.Integer, index=False)
        bar = sa.Column(sa.Integer, index=True)

    class IndexedTestType(SQLAlchemyObjectType):
        class Meta:
            model = IndexedTestModel

    sort_arg = IndexedTestType.sort_argument(only_indexed=True)
    sort_enum = sort_arg.type._of_type
    assert list(sort_enum._meta.enum.__members__) == [
        "ID_ASC",
        "ID_DESC",
        "BAR_ASC",
        "BAR_DESC",
    ]
    assert sort_arg.default_value == ["ID_ASC"]


def test_sort_argument_with_custom_symbol_names():
    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet

    def get_symbol_name(column_name, sort_asc=True):
        return to_type_name(column_name) + ("Up" if sort_asc else "Down")

    sort_arg = PetType.sort_argument(get_symbol_name=get_symbol_name)
    sort_enum = sort_arg.type._of_type
    assert list(sort_enum._meta.enum.__members__) == [
        "IdUp",
        "IdDown",
        "NameUp",
        "NameDown",
        "PetKindUp",
        "PetKindDown",
        "HairKindUp",
        "HairKindDown",
        "ReporterIdUp",
        "ReporterIdDown",
    ]
    assert sort_arg.default_value == ["IdUp"]


def test_sort_query(session):
    add_pets(session)

    class PetNode(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces = (Node,)

    class PetConnection(Connection):
        class Meta:
            node = PetNode

    class Query(ObjectType):
        defaultSort = SQLAlchemyConnectionField(PetConnection)
        nameSort = SQLAlchemyConnectionField(PetConnection)
        multipleSort = SQLAlchemyConnectionField(PetConnection)
        descSort = SQLAlchemyConnectionField(PetConnection)
        singleColumnSort = SQLAlchemyConnectionField(
            PetConnection, sort=Argument(PetNode.sort_enum())
        )
        noDefaultSort = SQLAlchemyConnectionField(
            PetConnection, sort=PetNode.sort_argument(has_default=False)
        )
        noSort = SQLAlchemyConnectionField(PetConnection, sort=None)

    query = """
        query sortTest {
            defaultSort {
                edges {
                    node {
                        name
                    }
                }
            }
            nameSort(sort: NAME_ASC) {
                edges {
                    node {
                        name
                    }
                }
            }
            multipleSort(sort: [PET_KIND_ASC, NAME_DESC]) {
                edges {
                    node {
                        name
                        petKind
                    }
                }
            }
            descSort(sort: [NAME_DESC]) {
                edges {
                    node {
                        name
                    }
                }
            }
            singleColumnSort(sort: NAME_DESC) {
                edges {
                    node {
                        name
                    }
                }
            }
            noDefaultSort(sort: NAME_ASC) {
                edges {
                    node {
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
            [{"name": "Lassie"}, {"name": "Barf"}, {"name": "Alf"}]
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

    schema = Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    result = to_std_dicts(result.data)
    assert result == expected

    queryError = """
        query sortTest {
            singleColumnSort(sort: [PET_KIND_ASC, NAME_DESC]) {
                edges {
                    node {
                        name
                    }
                }
            }
        }
    """
    result = schema.execute(queryError, context_value={"session": session})
    assert result.errors is not None
    assert '"sort" has invalid value' in result.errors[0].message

    queryNoSort = """
        query sortTest {
            noDefaultSort {
                edges {
                    node {
                        name
                    }
                }
            }
            noSort {
                edges {
                    node {
                        name
                    }
                }
            }
        }
    """

    result = schema.execute(queryNoSort, context_value={"session": session})
    assert not result.errors
    # TODO: SQLite usually returns the results ordered by primary key,
    # so we cannot test this way whether sorting actually happens or not.
    # Also, no sort order is guaranteed by SQLite if "no order" by is used.
    assert [node["node"]["name"] for node in result.data["noSort"]["edges"]] == [
        node["node"]["name"] for node in result.data["noDefaultSort"]["edges"]
    ]
