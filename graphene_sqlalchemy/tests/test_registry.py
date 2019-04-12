from enum import Enum as PyEnum

import pytest
from sqlalchemy import Enum as SQLAlchemyEnum

from ..registry import Registry
from ..types import SQLAlchemyObjectType
from .models import Pet


def test_register_incorrect_objecttype():
    reg = Registry()

    class Spam:
        pass

    with pytest.raises(TypeError) as exc_info:
        reg.register(Spam)

    assert "Only classes of type SQLAlchemyObjectType can be registered" in str(
        exc_info.value
    )


def test_register_objecttype_twice():
    reg = Registry()

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            registry = reg

    try:
        reg.register(PetType)

        class PetType2(SQLAlchemyObjectType):
            class Meta:
                model = Pet
                registry = reg

        reg.register(PetType2)
    except TypeError:
        pytest.fail("check not enabled, expected no TypeError")

    assert reg.get_type_for_model(Pet) is PetType2


def test_register_objecttype_twice_with_check():
    reg = Registry(check_duplicate_registration=True)

    class PetType(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            registry = reg

    try:
        reg.register(PetType)
    except TypeError:
        pytest.fail("same object type, expected no TypeError")

    assert reg.get_type_for_model(Pet) is PetType

    with pytest.raises(TypeError) as exc_info:

        # noinspection PyUnusedLocal
        class PetType2(SQLAlchemyObjectType):
            class Meta:
                model = Pet
                registry = reg

    assert "Different object types registered for the same model" in str(exc_info.value)


def test_register_composite_converter():
    reg = Registry()
    composite = object()
    converter = len
    reg.register_composite_converter(composite, converter)
    reg.get_converter_for_composite(composite) is converter


def test_get_type_for_enum_from_list():
    reg = Registry()
    sa_enum = SQLAlchemyEnum('red', 'blue', name='color_enum')
    graphene_enum = reg.get_type_for_enum(sa_enum)
    assert graphene_enum._meta.name == 'ColorEnum'
    assert graphene_enum._meta.enum.__members__['RED'].value == 'red'
    assert graphene_enum._meta.enum.__members__['BLUE'].value == 'blue'
    try:
        assert reg.get_type_for_enum(sa_enum) == graphene_enum
    except TypeError:
        pytest.fail("same enum, expected no TypeError")
    sa_enum = SQLAlchemyEnum('red', 'green', name='color_enum')
    with pytest.raises(TypeError) as exc_info:  # different keys
        reg.get_type_for_enum(sa_enum)
    assert 'Different enums with the same name "ColorEnum"' in str(exc_info.value)


def test_get_type_for_enum_from_py_enum():
    reg = Registry()
    py_enum = PyEnum('ColorEnum', 'red blue')
    sa_enum = SQLAlchemyEnum(py_enum)
    graphene_enum = reg.get_type_for_enum(sa_enum)
    assert graphene_enum._meta.name == 'ColorEnum'
    assert graphene_enum._meta.enum.__members__['RED'].value == 1
    assert graphene_enum._meta.enum.__members__['BLUE'].value == 2
    sa_enum = SQLAlchemyEnum('red', 'blue', name='color_enum')
    with pytest.raises(TypeError) as exc_info:  # different values
        reg.get_type_for_enum(sa_enum)
    assert 'Different enums with the same name "ColorEnum"' in str(exc_info.value)


def test_sort_params_for_model():
    reg = Registry()
    model = object
    sort_params = object()
    reg.register_sort_params(model, sort_params)
    assert reg.get_sort_params_for_model(model) is sort_params
