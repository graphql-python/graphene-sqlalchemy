import graphene


class ObjectTypeFilter(graphene.InputObjectType):
    pass


class RelationshipFilter(graphene.InputObjectType):
    pass


class ScalarFilter(graphene.InputObjectType):
    """Basic Filter for Scalars in Graphene.
    We want this filter to use Dynamic fields so it provides the base
    filtering methods ("eq, nEq") for different types of scalars.
    The Dynamic fields will resolve to Meta.filtered_type"""

    @classmethod
    def __init_subclass_with_meta__(cls, type=None, _meta=None, **options):
        print(type)  # The type from the Meta Class
        super(ScalarFilter, cls).__init_subclass_with_meta__(_meta=_meta, **options)

    # TODO: Make this dynamic based on Meta.Type (see FloatFilter)
    eq = graphene.Dynamic(None)


class StringFilter(ScalarFilter):
    class Meta:
        type = graphene.String


class NumberFilter(ScalarFilter):
    """Intermediate Filter class since all Numbers are in an order relationship (support <, > etc)"""
    pass


class FloatFilter(NumberFilter):
    """Cooncrete Filter Class which specifies a type for all the abstract filter methods defined in the super classes"""

    class Meta:
        type = graphene.Float
