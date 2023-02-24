====
Tips
====

Querying
--------
.. _querying:
In order to make querying against the database work, there are two alternatives:

-  Set the db session when you do the execution:

.. code:: python

    schema = graphene.Schema()
    schema.execute(context_value={'session': session})

-  Create a query for the models.

.. code:: python

    Base = declarative_base()
    Base.query = db_session.query_property()

    class MyModel(Base):
        # ...

If you don't specify any, the following error will be displayed:

``A query in the model Base or a session in the schema is required for querying.``

Sorting
-------

By default the SQLAlchemyConnectionField sorts the result elements over the primary key(s).
The query has a `sort` argument which allows to sort over a different column(s)

Given the model

.. code:: python

    class Pet(Base):
        __tablename__ = 'pets'
        id = Column(Integer(), primary_key=True)
        name = Column(String(30))
        pet_kind = Column(Enum('cat', 'dog', name='pet_kind'), nullable=False)


    class PetNode(SQLAlchemyObjectType):
        class Meta:
            model = Pet


    class Query(ObjectType):
        allPets = SQLAlchemyConnectionField(PetNode.connection)

some of the allowed queries are

-  Sort in ascending order over the `name` column

.. code::

    allPets(sort: name_asc){
        edges {
            node {
                name
            }
        }
    }

-  Sort in descending order over the `per_kind` column and in ascending order over the `name` column

.. code::

    allPets(sort: [pet_kind_desc, name_asc]) {
        edges {
            node {
                name
                petKind
            }
        }
    }

