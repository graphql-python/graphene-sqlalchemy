
from graphene import ObjectType

from ..registry import Registry
from ..types import SQLAlchemyObjectType
from .models import ReflectedEditor

registry = Registry()


class Reflected(SQLAlchemyObjectType):
    class Meta:
        model = ReflectedEditor
        registry = registry


def test_objecttype_registered():
    assert issubclass(Reflected, ObjectType)
    assert Reflected._meta.model == ReflectedEditor
    assert list(Reflected._meta.fields.keys()) == ["editor_id", "name"]
