from collections import OrderedDict
from typing import Type, Tuple, Mapping, Callable

import sqlalchemy
from graphene import Field, InputObjectType, Dynamic, Argument, Mutation, ID
from graphene.relay import Connection, Node
from graphene.types.objecttype import ObjectType, ObjectTypeOptions
from graphene.types.structures import Structure
from graphene.types.utils import yank_fields_from_attrs
from graphene.utils.str_converters import to_snake_case
from graphql import ResolveInfo
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.inspection import inspect as sqlalchemyinspect
from sqlalchemy.orm.exc import NoResultFound

from .converter import (convert_sqlalchemy_column,
                        convert_sqlalchemy_composite,
                        convert_sqlalchemy_hybrid_method,
                        convert_sqlalchemy_relationship)
from .enums import (enum_for_field, sort_argument_for_object_type,
                    sort_enum_for_object_type)
from .fields import SQLAlchemyFilteredConnectionField
from .fields import default_connection_field_factory
from .interfaces import SQLAlchemyInterface
from .registry import Registry, get_global_registry
from .utils import get_query, is_mapped_class, is_mapped_instance
from .utils import pluralize_name


def construct_fields(
        obj_type, model, registry, only_fields, exclude_fields, connection_field_factory
):
    inspected_model = sqlalchemyinspect(model)

    fields = OrderedDict()

    for name, column in inspected_model.columns.items():
        is_not_in_only = only_fields and name not in only_fields
        # is_already_created = name in options.fields
        is_excluded = name in exclude_fields  # or is_already_created
        if is_not_in_only or is_excluded:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields
            continue
        converted_column = convert_sqlalchemy_column(column, registry)
        registry.register_orm_field(obj_type, name, column)
        fields[name] = converted_column

    for name, composite in inspected_model.composites.items():
        is_not_in_only = only_fields and name not in only_fields
        # is_already_created = name in options.fields
        is_excluded = name in exclude_fields  # or is_already_created
        if is_not_in_only or is_excluded:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields
            continue
        converted_composite = convert_sqlalchemy_composite(composite, registry)
        registry.register_orm_field(obj_type, name, composite)
        fields[name] = converted_composite

    for hybrid_item in inspected_model.all_orm_descriptors:

        if type(hybrid_item) == hybrid_property:
            name = hybrid_item.__name__

            is_not_in_only = only_fields and name not in only_fields
            # is_already_created = name in options.fields
            is_excluded = name in exclude_fields  # or is_already_created

            if is_not_in_only or is_excluded:
                # We skip this field if we specify only_fields and is not
                # in there. Or when we exclude this field in exclude_fields
                continue

            converted_hybrid_property = convert_sqlalchemy_hybrid_method(hybrid_item)
            registry.register_orm_field(obj_type, name, hybrid_item)
            fields[name] = converted_hybrid_property

    # Get all the columns for the relationships on the model
    for relationship in inspected_model.relationships:
        is_not_in_only = only_fields and relationship.key not in only_fields
        # is_already_created = relationship.key in options.fields
        is_excluded = relationship.key in exclude_fields  # or is_already_created
        if is_not_in_only or is_excluded:
            # We skip this field if we specify only_fields and is not
            # in there. Or when we exclude this field in exclude_fields
            continue
        converted_relationship = convert_sqlalchemy_relationship(
            relationship, registry, connection_field_factory
        )
        name = relationship.key
        registry.register_orm_field(obj_type, name, relationship)
        fields[name] = converted_relationship

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


class SQLAlchemyInputObjectType(InputObjectType):
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
        autoexclude = []

        # always pull ids out to a separate argument
        for col in sqlalchemy.inspect(model).columns:
            if ((col.primary_key and col.autoincrement) or
                    (isinstance(col.type, sqlalchemy.types.TIMESTAMP) and
                     col.server_default is not None)):
                autoexclude.append(col.name)

        if not registry:
            registry = get_global_registry()
        sqla_fields = yank_fields_from_attrs(
            construct_fields(model, registry, only_fields, exclude_fields + tuple(autoexclude), connection_field_factory),
            _as=Field,
        )
        # create accessor for model to be retrieved for querying
        cls.sqla_model = model
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

        for key, value in sqla_fields.items():
            if not (isinstance(value, Dynamic) or hasattr(cls, key)):
                setattr(cls, key, value)

        super(SQLAlchemyInputObjectType, cls).__init_subclass_with_meta__(**options)


class SQLAlchemyAutoSchemaFactory(ObjectType):

    @staticmethod
    def set_fields_and_attrs(klazz: Type[ObjectType], node_model: Type[SQLAlchemyInterface], field_dict: Mapping[str, Field]):
        _name = to_snake_case(node_model.__name__)
        field_dict[f'all_{(pluralize_name(_name))}'] = SQLAlchemyFilteredConnectionField(node_model)
        field_dict[_name] = node_model.Field()
        setattr(klazz, _name, node_model.Field())
        setattr(klazz, "all_{}".format(pluralize_name(_name)), SQLAlchemyFilteredConnectionField(node_model))

    @classmethod
    def __init_subclass_with_meta__(
            cls,
            interfaces: Tuple[Type[SQLAlchemyInterface]] = (),
            models: Tuple[Type[DeclarativeMeta]] = (),
            excluded_models: Tuple[Type[DeclarativeMeta]] = (),
            node_interface: Type[Node] = Type[Node],
            default_resolver: ResolveInfo = None,
            _meta=None,
            **options
    ):
        if not _meta:
            _meta = ObjectTypeOptions(cls)

        fields = OrderedDict()

        for interface in interfaces:
            if issubclass(interface, SQLAlchemyInterface):
                SQLAlchemyAutoSchemaFactory.set_fields_and_attrs(cls, interface, fields)
        for model in excluded_models:
            if model in models:
                models = models[:models.index(model)] + models[models.index(model) + 1:]
        possible_types = ()
        for model in models:
            model_name = model.__name__
            _model_name = to_snake_case(model.__name__)

            if hasattr(cls, _model_name):
                continue
            if hasattr(cls, "all_{}".format(pluralize_name(_model_name))):
                continue
            for iface in interfaces:
                if issubclass(model, iface._meta.model):
                    model_interface = (iface,)
                    break
            else:
                model_interface = (node_interface,)

            _node_class = type(model_name,
                               (SQLAlchemyObjectType,),
                               {"Meta": {"model": model, "interfaces": model_interface, "only_fields": []}})
            fields["all_{}".format(pluralize_name(_model_name))] = SQLAlchemyFilteredConnectionField(_node_class)
            setattr(cls, "all_{}".format(pluralize_name(_model_name)), SQLAlchemyFilteredConnectionField(_node_class))
            fields[_model_name] = node_interface.Field(_node_class)
            setattr(cls, _model_name, node_interface.Field(_node_class))
            possible_types += (_node_class,)
        if _meta.fields:
            _meta.fields.update(fields)
        else:
            _meta.fields = fields
        _meta.schema_types = possible_types

        super(SQLAlchemyAutoSchemaFactory, cls).__init_subclass_with_meta__(_meta=_meta, default_resolver=default_resolver, **options)

    @classmethod
    def resolve_with_filters(cls, info: ResolveInfo, model: Type[SQLAlchemyObjectType], **kwargs):
        query = model.get_query(info)
        for filter_name, filter_value in kwargs.items():
            model_filter_column = getattr(model._meta.model, filter_name, None)
            if not model_filter_column:
                continue
            if isinstance(filter_value, SQLAlchemyInputObjectType):
                filter_model = filter_value.sqla_model
                q = SQLAlchemyFilteredConnectionField.get_query(filter_model, info, sort=None, **kwargs)
                # noinspection PyArgumentList
                query = query.filter(model_filter_column == q.filter_by(**filter_value))
            else:
                query = query.filter(model_filter_column == filter_value)
        return query


class SQLAlchemyMutationOptions(ObjectTypeOptions):
    model: DeclarativeMeta = None
    create: bool = False
    delete: bool = False
    arguments: Mapping[str, Argument] = None
    output: Type[ObjectType] = None
    resolver: Callable = None


class SQLAlchemyMutation(Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, model=None, create=False,
                                    delete=False, registry=None,
                                    arguments=None, only_fields=(),
                                    structure: Type[Structure] = None,
                                    exclude_fields=(), **options):
        meta = SQLAlchemyMutationOptions(cls)
        meta.create = create
        meta.model = model
        meta.delete = delete

        if arguments is None and not hasattr(cls, "Arguments"):
            arguments = {}
            # don't include id argument on create
            if not meta.create:
                arguments['id'] = ID(required=True)

            # don't include input argument on delete
            if not meta.delete:
                inputMeta = type('Meta', (object,), {
                    'model': model,
                    'exclude_fields': exclude_fields,
                    'only_fields': only_fields
                })
                inputType = type(cls.__name__ + 'Input',
                                 (SQLAlchemyInputObjectType,),
                                 {'Meta': inputMeta})
                arguments = {'input': inputType(required=True)}
        if not registry:
            registry = get_global_registry()
        output_type: ObjectType = registry.get_type_for_model(model)
        if structure:
            output_type = structure(output_type)
        super(SQLAlchemyMutation, cls).__init_subclass_with_meta__(_meta=meta, output=output_type, arguments=arguments, **options)

    @classmethod
    def mutate(cls, info, **kwargs):
        session = get_session(info.context)
        with session.no_autoflush:
            meta = cls._meta

            if meta.create:
                model = meta.model(**kwargs['input'])
                session.add(model)
            else:
                model = session.query(meta.model).filter(meta.model.id ==
                                                         kwargs['id']).first()
            if meta.delete:
                session.delete(model)
            else:
                def setModelAttributes(model, attrs):
                    relationships = model.__mapper__.relationships
                    for key, value in attrs.items():
                        if key in relationships:
                            if getattr(model, key) is None:
                                # instantiate class of the same type as
                                # the relationship target
                                setattr(model, key,
                                        relationships[key].mapper.entity())
                            setModelAttributes(getattr(model, key), value)
                        else:
                            setattr(model, key, value)

                setModelAttributes(model, kwargs['input'])
            session.commit()

            return model

    @classmethod
    def Field(cls, *args, **kwargs):
        return Field(cls._meta.output,
                     args=cls._meta.arguments,
                     resolver=cls._meta.resolver)
