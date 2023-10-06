import inspect
from collections import defaultdict
from typing import TYPE_CHECKING, List, Type

from sqlalchemy.types import Enum as SQLAlchemyEnumType

import graphene
from graphene import Enum
from graphene.types.base import BaseType

if TYPE_CHECKING:  # pragma: no_cover
    from .filters import BaseTypeFilter, FieldFilter, RelationshipFilter


class Registry(object):
    def __init__(self):
        self._registry = {}
        self._registry_models = {}
        self._registry_orm_fields = defaultdict(dict)
        self._registry_composites = {}
        self._registry_enums = {}
        self._registry_sort_enums = {}
        self._registry_unions = {}
        self._registry_scalar_filters = {}
        self._registry_base_type_filters = {}
        self._registry_relationship_filters = {}

        self._init_base_filters()

    def _init_base_filters(self):
        import graphene_sqlalchemy.filters as gsqa_filters

        from .filters import FieldFilter

        field_filter_classes = [
            filter_cls[1]
            for filter_cls in inspect.getmembers(gsqa_filters, inspect.isclass)
            if (
                filter_cls[1] is not FieldFilter
                and FieldFilter in filter_cls[1].__mro__
                and getattr(filter_cls[1]._meta, "graphene_type", False)
            )
        ]
        for field_filter_class in field_filter_classes:
            self.register_filter_for_scalar_type(
                field_filter_class._meta.graphene_type, field_filter_class
            )

    def register(self, obj_type):
        from .types import SQLAlchemyBase

        if not isinstance(obj_type, type) or not issubclass(obj_type, SQLAlchemyBase):
            raise TypeError("Expected SQLAlchemyBase, but got: {!r}".format(obj_type))
        assert obj_type._meta.registry == self, "Registry for a Model have to match."
        # assert self.get_type_for_model(cls._meta.model) in [None, cls], (
        #     'SQLAlchemy model "{}" already associated with '
        #     'another type "{}".'
        # ).format(cls._meta.model, self._registry[cls._meta.model])
        self._registry[obj_type._meta.model] = obj_type

    def get_type_for_model(self, model):
        return self._registry.get(model)

    def register_orm_field(self, obj_type, field_name, orm_field):
        from .types import SQLAlchemyBase

        if not isinstance(obj_type, type) or not issubclass(obj_type, SQLAlchemyBase):
            raise TypeError("Expected SQLAlchemyBase, but got: {!r}".format(obj_type))
        if not field_name or not isinstance(field_name, str):
            raise TypeError("Expected a field name, but got: {!r}".format(field_name))
        self._registry_orm_fields[obj_type][field_name] = orm_field

    def get_orm_field_for_graphene_field(self, obj_type, field_name):
        return self._registry_orm_fields.get(obj_type, {}).get(field_name)

    def register_composite_converter(self, composite, converter):
        self._registry_composites[composite] = converter

    def get_converter_for_composite(self, composite):
        return self._registry_composites.get(composite)

    def register_enum(self, sa_enum: SQLAlchemyEnumType, graphene_enum: Enum):
        if not isinstance(sa_enum, SQLAlchemyEnumType):
            raise TypeError(
                "Expected SQLAlchemyEnumType, but got: {!r}".format(sa_enum)
            )
        if not isinstance(graphene_enum, type(Enum)):
            raise TypeError(
                "Expected Graphene Enum, but got: {!r}".format(graphene_enum)
            )

        self._registry_enums[sa_enum] = graphene_enum

    def get_graphene_enum_for_sa_enum(self, sa_enum: SQLAlchemyEnumType):
        return self._registry_enums.get(sa_enum)

    def register_sort_enum(self, obj_type, sort_enum: Enum):

        from .types import SQLAlchemyObjectType

        if not isinstance(obj_type, type) or not issubclass(
            obj_type, SQLAlchemyObjectType
        ):
            raise TypeError(
                "Expected SQLAlchemyObjectType, but got: {!r}".format(obj_type)
            )
        if not isinstance(sort_enum, type(Enum)):
            raise TypeError("Expected Graphene Enum, but got: {!r}".format(sort_enum))
        self._registry_sort_enums[obj_type] = sort_enum

    def get_sort_enum_for_object_type(self, obj_type: graphene.ObjectType):
        return self._registry_sort_enums.get(obj_type)

    def register_union_type(
        self, union: Type[graphene.Union], obj_types: List[Type[graphene.ObjectType]]
    ):
        if not issubclass(union, graphene.Union):
            raise TypeError("Expected graphene.Union, but got: {!r}".format(union))

        for obj_type in obj_types:
            if not issubclass(obj_type, graphene.ObjectType):
                raise TypeError(
                    "Expected Graphene ObjectType, but got: {!r}".format(obj_type)
                )

        self._registry_unions[frozenset(obj_types)] = union

    def get_union_for_object_types(self, obj_types: List[Type[graphene.ObjectType]]):
        return self._registry_unions.get(frozenset(obj_types))

    # Filter Scalar Fields of Object Types
    def register_filter_for_scalar_type(
        self, scalar_type: Type[graphene.Scalar], filter_obj: Type["FieldFilter"]
    ):
        from .filters import FieldFilter

        if not isinstance(scalar_type, type(graphene.Scalar)):
            raise TypeError("Expected Scalar, but got: {!r}".format(scalar_type))

        if not issubclass(filter_obj, FieldFilter):
            raise TypeError("Expected ScalarFilter, but got: {!r}".format(filter_obj))
        self._registry_scalar_filters[scalar_type] = filter_obj

    def get_filter_for_sql_enum_type(
        self, enum_type: Type[graphene.Enum]
    ) -> Type["FieldFilter"]:
        from .filters import SQLEnumFilter

        filter_type = self._registry_scalar_filters.get(enum_type)
        if not filter_type:
            filter_type = SQLEnumFilter.create_type(
                f"Default{enum_type.__name__}EnumFilter", graphene_type=enum_type
            )
            self._registry_scalar_filters[enum_type] = filter_type
        return filter_type

    def get_filter_for_py_enum_type(
        self, enum_type: Type[graphene.Enum]
    ) -> Type["FieldFilter"]:
        from .filters import PyEnumFilter

        filter_type = self._registry_scalar_filters.get(enum_type)
        if not filter_type:
            filter_type = PyEnumFilter.create_type(
                f"Default{enum_type.__name__}EnumFilter", graphene_type=enum_type
            )
            self._registry_scalar_filters[enum_type] = filter_type
        return filter_type

    def get_filter_for_scalar_type(
        self, scalar_type: Type[graphene.Scalar]
    ) -> Type["FieldFilter"]:
        from .filters import FieldFilter

        filter_type = self._registry_scalar_filters.get(scalar_type)
        if not filter_type:
            filter_type = FieldFilter.create_type(
                f"Default{scalar_type.__name__}ScalarFilter", graphene_type=scalar_type
            )
            self._registry_scalar_filters[scalar_type] = filter_type

        return filter_type

    # TODO register enums automatically
    def register_filter_for_enum_type(
        self, enum_type: Type[graphene.Enum], filter_obj: Type["FieldFilter"]
    ):
        from .filters import FieldFilter

        if not issubclass(enum_type, graphene.Enum):
            raise TypeError("Expected Enum, but got: {!r}".format(enum_type))

        if not issubclass(filter_obj, FieldFilter):
            raise TypeError("Expected FieldFilter, but got: {!r}".format(filter_obj))
        self._registry_scalar_filters[enum_type] = filter_obj

    # Filter Base Types
    def register_filter_for_base_type(
        self,
        base_type: Type[BaseType],
        filter_obj: Type["BaseTypeFilter"],
    ):
        from .filters import BaseTypeFilter

        if not issubclass(base_type, BaseType):
            raise TypeError("Expected BaseType, but got: {!r}".format(base_type))

        if not issubclass(filter_obj, BaseTypeFilter):
            raise TypeError("Expected BaseTypeFilter, but got: {!r}".format(filter_obj))
        self._registry_base_type_filters[base_type] = filter_obj

    def get_filter_for_base_type(self, base_type: Type[BaseType]):
        return self._registry_base_type_filters.get(base_type)

    # Filter Relationships between base types
    def register_relationship_filter_for_base_type(
        self, base_type: BaseType, filter_obj: Type["RelationshipFilter"]
    ):
        from .filters import RelationshipFilter

        if not isinstance(base_type, type(BaseType)):
            raise TypeError("Expected BaseType, but got: {!r}".format(base_type))

        if not issubclass(filter_obj, RelationshipFilter):
            raise TypeError(
                "Expected RelationshipFilter, but got: {!r}".format(filter_obj)
            )
        self._registry_relationship_filters[base_type] = filter_obj

    def get_relationship_filter_for_base_type(
        self, base_type: Type[BaseType]
    ) -> "RelationshipFilter":
        return self._registry_relationship_filters.get(base_type)


registry = None


def get_global_registry():
    global registry
    if not registry:
        registry = Registry()
    return registry


def reset_global_registry():
    global registry
    registry = None
