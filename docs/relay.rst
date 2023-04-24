Relay
==========

:code:`graphene-sqlalchemy` comes with pre-defined
connection fields to quickly create a functioning relay API.
Using the :code:`SQLAlchemyConnectionField`, you have access to relay pagination,
sorting and filtering (filtering is coming soon!).

To be used in a relay connection, your :code:`SQLAlchemyObjectType` must implement
the :code:`Node` interface from :code:`graphene.relay`. This handles the creation of
the :code:`Connection` and :code:`Edge` types automatically.

The following example creates a relay-paginated connection:



.. code:: python

    class Pet(Base):
        __tablename__ = 'pets'
        id = Column(Integer(), primary_key=True)
        name = Column(String(30))
        pet_kind = Column(Enum('cat', 'dog', name='pet_kind'), nullable=False)


    class PetNode(SQLAlchemyObjectType):
        class Meta:
            model = Pet
            interfaces=(Node,)


    class Query(ObjectType):
        all_pets = SQLAlchemyConnectionField(PetNode.connection)

To disable sorting on the connection, you can set :code:`sort` to :code:`None` the
:code:`SQLAlchemyConnectionField`:


.. code:: python

    class Query(ObjectType):
        all_pets = SQLAlchemyConnectionField(PetNode.connection, sort=None)

