from collections import OrderedDict

from sqlalchemy.types import Enum as SQLAlchemyEnumType

from graphene import Enum

from .utils import to_enum_value_name, to_type_name


class Registry(object):
    def __init__(self, check_duplicate_registration=False):
        self.check_duplicate_registration = check_duplicate_registration
        self._registry = {}
        self._registry_models = {}
        self._registry_composites = {}
        self._registry_enums = {}
        self._registry_sort_params = {}

    def register(self, cls):
        from .types import SQLAlchemyObjectType

        if not issubclass(cls, SQLAlchemyObjectType):
            raise TypeError(
                "Only classes of type SQLAlchemyObjectType can be registered, "
                'received "{}"'.format(cls.__name__)
            )
        if cls._meta.registry != self:
            raise TypeError("Registry for a Model have to match.")

        registered_cls = (
            self._registry.get(cls._meta.model)
            if self.check_duplicate_registration
            else None
        )
        if registered_cls:
            if cls != registered_cls:
                raise TypeError(
                    "Different object types registered for the same model {}:"
                    " tried to register {}, but {} existed already.".format(
                        cls._meta.model, cls, registered_cls
                    )
                )
        else:
            self._registry[cls._meta.model] = cls

    def register_enum(self, name, members):
        graphene_enum = self._registry_enums.get(name)
        if graphene_enum:
            registered_members = {
                key: value.value
                for key, value in graphene_enum._meta.enum.__members__.items()
            }
            if members != registered_members:
                raise TypeError(
                    'Different enums with the same name "{}":'
                    " tried to register {}, but {} existed already.".format(
                        name, members, registered_members
                    )
                )
        else:
            graphene_enum = Enum(name, members)
            self._registry_enums[name] = graphene_enum
        return graphene_enum

    def register_sort_params(self, cls, sort_params):
        registered_sort_params = (
            self._registry_sort_params.get(cls)
            if self.check_duplicate_registration
            else None
        )
        if registered_sort_params:
            if registered_sort_params != sort_params:
                raise TypeError(
                    "Different sort args for the same model {}:"
                    " tried to register {}, but {} existed already.".format(
                        cls, sort_params, registered_sort_params
                    )
                )
        else:
            self._registry_sort_params[cls] = sort_params

    def get_type_for_model(self, model):
        return self._registry.get(model)

    def register_composite_converter(self, composite, converter):
        self._registry_composites[composite] = converter

    def get_converter_for_composite(self, composite):
        return self._registry_composites.get(composite)

    def get_type_for_enum(self, sql_type):
        if not isinstance(sql_type, SQLAlchemyEnumType):
            raise TypeError(
                "Only sqlalchemy.Enum objects can be registered as enum, "
                'received "{}"'.format(sql_type)
            )
        enum_class = sql_type.enum_class
        if enum_class:
            name = enum_class.__name__
            members = OrderedDict(
                (to_enum_value_name(key), value.value)
                for key, value in enum_class.__members__.items()
            )
        else:
            name = sql_type.name
            name = (
                to_type_name(name)
                if name
                else "Enum{}".format(len(self._registry_enums) + 1)
            )
            members = OrderedDict(
                (to_enum_value_name(key), key) for key in sql_type.enums
            )
        return self.register_enum(name, members)

    def get_sort_params_for_model(self, model):
        return self._registry_sort_params.get(model)


registry = None


def get_global_registry():
    global registry
    if not registry:
        registry = Registry()
    return registry


def reset_global_registry():
    global registry
    registry = None
