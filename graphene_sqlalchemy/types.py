from collections import OrderedDict

import sqlalchemy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect as sqlalchemyinspect
from sqlalchemy.orm import (ColumnProperty, CompositeProperty,
                            RelationshipProperty)
from sqlalchemy.orm.exc import NoResultFound

from graphene import Field
from graphene.relay import Connection, Node
from graphene.types.objecttype import ObjectType, ObjectTypeOptions
from graphene.types.utils import yank_fields_from_attrs
from graphene.utils.orderedtype import OrderedType

from .converter import (convert_sqlalchemy_column,
                        convert_sqlalchemy_composite,
                        convert_sqlalchemy_hybrid_method,
                        convert_sqlalchemy_relationship)
from .enums import (enum_for_field, sort_argument_for_object_type,
                    sort_enum_for_object_type)
from .fields import default_connection_field_factory
from .registry import Registry, get_global_registry
from .utils import get_query, is_mapped_class, is_mapped_instance


class ORMField(OrderedType):
    def __init__(
        self,
        type=None,
        prop_name=None,
        description=None,
        deprecation_reason=None,
        required=None,
        _creation_counter=None,
        **field_kwargs
    ):
        super(ORMField, self).__init__(_creation_counter=_creation_counter)
        # The is only useful for documentation and auto-completion
        common_kwargs = {
           'type': type,
           'prop_name': prop_name,
           'description': description,
           'deprecation_reason': deprecation_reason,
           'required': required,
        }
        common_kwargs = {kwarg: value for kwarg, value in common_kwargs.items() if value is not None}
        self.kwargs = field_kwargs
        self.kwargs.update(common_kwargs)


def construct_fields(
    obj_type, model, registry, only_fields, exclude_fields, connection_field_factory
):
    inspected_model = sqlalchemyinspect(model)
    all_model_props = OrderedDict(
        inspected_model.column_attrs.items() +
        inspected_model.composites.items() +
        [(name, item) for name, item in inspected_model.all_orm_descriptors.items()
            if isinstance(item, hybrid_property)] +
        inspected_model.relationships.items()
    )

    auto_orm_field_names = []
    for prop_name, prop in all_model_props.items():
        if (only_fields and prop_name not in only_fields) or (prop_name in exclude_fields):
            continue
        auto_orm_field_names.append(prop_name)

    # TODO Get ORMField fields defined on parent classes
    custom_orm_fields_items = []
    for attname, value in list(obj_type.__dict__.items()):
        if isinstance(value, ORMField):
            custom_orm_fields_items.append((attname, value))
    custom_orm_fields_items = sorted(custom_orm_fields_items, key=lambda item: item[1])

    for orm_field_name, orm_field in custom_orm_fields_items:
        prop_name = orm_field.kwargs.get('prop_name', orm_field_name)
        if prop_name not in all_model_props:
            raise Exception('Cannot map ORMField "{}" to SQLAlchemy model property'.format(orm_field_name))
        orm_field.kwargs['prop_name'] = prop_name

    orm_fields = OrderedDict(custom_orm_fields_items)
    for orm_field_name in auto_orm_field_names:
        if orm_field_name in orm_fields:
            continue
        orm_fields[orm_field_name] = ORMField(prop_name=orm_field_name)

    fields = OrderedDict()
    for orm_field_name, orm_field in orm_fields.items():
        prop_name = orm_field.kwargs.pop('prop_name')
        prop = all_model_props[prop_name]

        if isinstance(prop, ColumnProperty):
            field = convert_sqlalchemy_column(prop, registry, **orm_field.kwargs)
        elif isinstance(prop, RelationshipProperty):
            field = convert_sqlalchemy_relationship(prop, registry, connection_field_factory, **orm_field.kwargs)
        elif isinstance(prop, CompositeProperty):
            if prop_name != orm_field_name or orm_field.kwargs:
                # TODO Add a way to override composite property fields
                raise ValueError(
                    "ORMField kwargs for composite fields must be empty. "
                    "Field: {}.{}".format(obj_type.__name__, orm_field_name))
            field = convert_sqlalchemy_composite(prop, registry)
        elif isinstance(prop, hybrid_property):
            field = convert_sqlalchemy_hybrid_method(prop, prop_name, **orm_field.kwargs)
        else:
            raise Exception('Property type is not supported')  # Should never happen

        registry.register_orm_field(obj_type, orm_field_name, prop)
        fields[orm_field_name] = field

    return fields


class SQLAlchemyObjectTypeOptions(ObjectTypeOptions):
    model = None  # type: sqlalchemy.Model
    registry = None  # type: sqlalchemy.Registry
    connection = None  # type: sqlalchemy.Type[sqlalchemy.Connection]
    id = None  # type: str


class SQLAlchemyObjectType(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        model=None,
        registry=None,
        skip_registry=False,
        only_fields=(),
        exclude_fields=(),
        connection=None,
        connection_class=None,
        use_connection=None,
        interfaces=(),
        id=None,
        connection_field_factory=default_connection_field_factory,
        _meta=None,
        **options
    ):
        assert is_mapped_class(model), (
            "You need to pass a valid SQLAlchemy Model in " '{}.Meta, received "{}".'
        ).format(cls.__name__, model)

        if not registry:
            registry = get_global_registry()

        assert isinstance(registry, Registry), (
            "The attribute registry in {} needs to be an instance of "
            'Registry, received "{}".'
        ).format(cls.__name__, registry)

        if only_fields and exclude_fields:
            raise ValueError("The options 'only_fields' and 'exclude_fields' cannot be both set on the same type.")

        sqla_fields = yank_fields_from_attrs(
            construct_fields(
                obj_type=cls,
                model=model,
                registry=registry,
                only_fields=only_fields,
                exclude_fields=exclude_fields,
                connection_field_factory=connection_field_factory,
            ),
            _as=Field,
            sort=False,
        )

        if use_connection is None and interfaces:
            use_connection = any(
                (issubclass(interface, Node) for interface in interfaces)
            )

        if use_connection and not connection:
            # We create the connection automatically
            if not connection_class:
                connection_class = Connection

            connection = connection_class.create_type(
                "{}Connection".format(cls.__name__), node=cls
            )

        if connection is not None:
            assert issubclass(connection, Connection), (
                "The connection must be a Connection. Received {}"
            ).format(connection.__name__)

        if not _meta:
            _meta = SQLAlchemyObjectTypeOptions(cls)

        _meta.model = model
        _meta.registry = registry

        if _meta.fields:
            _meta.fields.update(sqla_fields)
        else:
            _meta.fields = sqla_fields

        _meta.connection = connection
        _meta.id = id or "id"

        super(SQLAlchemyObjectType, cls).__init_subclass_with_meta__(
            _meta=_meta, interfaces=interfaces, **options
        )

        if not skip_registry:
            registry.register(cls)

    @classmethod
    def is_type_of(cls, root, info):
        if isinstance(root, cls):
            return True
        if not is_mapped_instance(root):
            raise Exception(('Received incompatible instance "{}".').format(root))
        return isinstance(root, cls._meta.model)

    @classmethod
    def get_query(cls, info):
        model = cls._meta.model
        return get_query(model, info.context)

    @classmethod
    def get_node(cls, info, id):
        try:
            return cls.get_query(info).get(id)
        except NoResultFound:
            return None

    def resolve_id(self, info):
        # graphene_type = info.parent_type.graphene_type
        keys = self.__mapper__.primary_key_from_instance(self)
        return tuple(keys) if len(keys) > 1 else keys[0]

    @classmethod
    def enum_for_field(cls, field_name):
        return enum_for_field(cls, field_name)

    sort_enum = classmethod(sort_enum_for_object_type)

    sort_argument = classmethod(sort_argument_for_object_type)
