import sqlalchemy as sa

from graphene import Enum, List, ObjectType, Schema, String

from ..utils import (create_sort_enum_for_model, get_session,
                     get_sort_argument_for_model, get_sort_enum_for_model,
                     to_enum_value_name, to_type_name)
from .models import Editor, Pet


def test_get_session():
    session = "My SQLAlchemy session"

    class Query(ObjectType):
        x = String()

        def resolve_x(self, info):
            return get_session(info.context)

    query = """
        query ReporterQuery {
            x
        }
    """

    schema = Schema(query=Query)
    result = schema.execute(query, context_value={"session": session})
    assert not result.errors
    assert result.data["x"] == session


def test_to_type_name():
    assert to_type_name("make_camel_case") == "MakeCamelCase"
    assert to_type_name("AlreadyCamelCase") == "AlreadyCamelCase"
    assert to_type_name("A_Snake_and_a_Camel") == "ASnakeAndACamel"


def test_to_enum_value_name():
    assert to_enum_value_name("make_enum_value_name") == "MAKE_ENUM_VALUE_NAME"
    assert to_enum_value_name("makeEnumValueName") == "MAKE_ENUM_VALUE_NAME"
    assert to_enum_value_name("HTTPStatus400Message") == "HTTP_STATUS400_MESSAGE"
    assert to_enum_value_name("ALREADY_ENUM_VALUE_NAME") == "ALREADY_ENUM_VALUE_NAME"


def test_get_sort_enum_for_model():
    enum = get_sort_enum_for_model(Pet)
    assert isinstance(enum, type(Enum))
    assert str(enum) == "PetSortEnum"
    expect_symbols = []
    for name in sa.inspect(Pet).columns.keys():
        name_asc = name.upper() + "_ASC"
        name_desc = name.upper() + "_DESC"
        expect_symbols.extend([name_asc, name_desc])
    # the order of enums is not preserved for Python < 3.6
    assert sorted(enum._meta.enum.__members__) == sorted(expect_symbols)


def test_sort_enum_for_model_custom_naming():
    enum, default = create_sort_enum_for_model(
        Pet, "Foo", lambda n, d: ("a_" if d else "d_") + n
    )
    assert str(enum) == "Foo"
    expect_symbols = []
    expect_default = []
    for col in sa.inspect(Pet).columns.values():
        name = col.name
        name_asc = "a_" + name
        name_desc = "d_" + name
        expect_symbols.extend([name_asc, name_desc])
        if col.primary_key:
            expect_default.append(name_asc)
    # the order of enums is not preserved for Python < 3.6
    assert sorted(enum._meta.enum.__members__) == sorted(expect_symbols)
    assert default == expect_default


def test_enum_cache():
    assert get_sort_enum_for_model(Editor) is get_sort_enum_for_model(Editor)


def test_sort_argument_for_model():
    arg = get_sort_argument_for_model(Pet)

    assert isinstance(arg.type, List)
    assert arg.default_value == [Pet.id.name.upper() + "_ASC"]
    assert arg.type.of_type == get_sort_enum_for_model(Pet)


def test_sort_argument_for_model_no_default():
    arg = get_sort_argument_for_model(Pet, False)

    assert arg.default_value is None


def test_sort_argument_for_model_multiple_pk():
    Base = sa.ext.declarative.declarative_base()

    class MultiplePK(Base):
        foo = sa.Column(sa.Integer, primary_key=True)
        bar = sa.Column(sa.Integer, primary_key=True)
        __tablename__ = "MultiplePK"

    arg = get_sort_argument_for_model(MultiplePK)
    assert set(arg.default_value) == set(
        (MultiplePK.foo.name.upper() + "_ASC", MultiplePK.bar.name.upper() + "_ASC")
    )
