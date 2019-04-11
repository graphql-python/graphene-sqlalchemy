
from collections import OrderedDict

from sqlalchemy.types import Enum as SQLAlchemyEnumType

from graphene import Enum

from .utils import to_enum_value_name, to_type_name


class Registry(object):
    def __init__(self):
        self._registry = {}
        self._registry_models = {}
        self._registry_composites = {}
        self._registry_enums = {}

    def register(self, cls):
        from .types import SQLAlchemyObjectType

        assert issubclass(cls, SQLAlchemyObjectType), (
            "Only classes of type SQLAlchemyObjectType can be registered, "
            'received "{}"'
        ).format(cls.__name__)
        assert cls._meta.registry == self, "Registry for a Model have to match."
        # assert self.get_type_for_model(cls._meta.model) in [None, cls], (
        #     'SQLAlchemy model "{}" already associated with '
        #     'another type "{}".'
        # ).format(cls._meta.model, self._registry[cls._meta.model])
        self._registry[cls._meta.model] = cls

    def get_type_for_model(self, model):
        return self._registry.get(model)

    def register_composite_converter(self, composite, converter):
        self._registry_composites[composite] = converter

    def get_converter_for_composite(self, composite):
        return self._registry_composites.get(composite)

    def get_type_for_enum(self, sql_type):
        if not isinstance(sql_type, SQLAlchemyEnumType):
            raise TypeError(
                'Only sqlalchemy.Enum objects can be registered as enum, '
                'received "{}"'.format(sql_type))
        enum_class = sql_type.enum_class
        if enum_class:
            name = enum_class.__name__
            members = OrderedDict(
                (to_enum_value_name(key), value.value)
                for key, value in enum_class.__members__.items())
        else:
            name = sql_type.name
            name = to_type_name(name) if name else 'Enum{}'.format(
                len(self._registry_enums) + 1)
            members = OrderedDict(
                (to_enum_value_name(key), key) for key in sql_type.enums)
        graphene_type = self._registry_enums.get(name)
        if graphene_type:
            existing_members = {
                key: value.value for key, value
                in graphene_type._meta.enum.__members__.items()}
            if members != existing_members:
                raise TypeError(
                    'Different enums with the same name "{}":'
                    ' tried to register {}, but {} existed already.'.format(
                        name, members, existing_members))
        else:
            graphene_type = Enum(name, members)
            self._registry_enums[name] = graphene_type
        return graphene_type


registry = None


def get_global_registry():
    global registry
    if not registry:
        registry = Registry()
    return registry


def reset_global_registry():
    global registry
    registry = None
