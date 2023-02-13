=======
Filters
=======

Starting in graphene-sqlalchemy version 3, the SQLAlchemyConnectionField class implements filtering by default. The query utilizes a ``filter`` keyword to specify a filter class that inherits from ``graphene.InputObjectType``.

Migrating from graphene-sqlalchemy-filter
---------------------------------------------

If like many of us, you have been using |graphene-sqlalchemy-filter|_ to implement filters and would like to use the in-built mechanism here, there are a couple key differences to note. Mainly, in an effort to simplify the generated schema, filter keywords are nested under their respective fields instead of concatenated. For example, the filter partial ``{usernameIn: ["moderator", "cool guy"]}`` would be represented as ``{username: {in: ["moderator", "cool guy"]}}``.

.. |graphene-sqlalchemy-filter| replace:: ``graphene-sqlalchemy-filter``
.. _graphene-sqlalchemy-filter: https://github.com/art1415926535/graphene-sqlalchemy-filter

Further, some of the constructs found in libraries like `DGraph's DQL <https://dgraph.io/docs/query-language/>`_ have been implemented, so if you have created custom implementations for these features, you may want to take a look at the examples below.


Example model
-------------

Take as example a Pet model similar to that in the sorting example. We will use variations on this arrangement for the following examples.

.. code::

    class Pet(Base):
        __tablename__ = 'pets'
        id = Column(Integer(), primary_key=True)
        name = Column(String(30))
        age = Column(Integer())


    class PetNode(SQLAlchemyObjectType):
        class Meta:
            model = Pet


    class Query(ObjectType):
        allPets = SQLAlchemyConnectionField(PetNode.connection)


Simple filter example
---------------------

Filters are defined at the object level through the ``BaseTypeFilter`` class. The ``BaseType`` encompasses both Graphene ``ObjectType``\ s and ``Interface``\ s. Each ``BaseTypeFilter`` instance may define fields via ``FieldFilter`` and relationships via ``RelationshipFilter``. Here's a basic example querying a single field on the Pet model:

.. code::

    allPets(filter: {name: {eq: "Fido"}}){
        edges {
            node {
                name
            }
        }
    }

This will return all pets with the name "Fido".


Custom filter types
-------------------

If you'd like to implement custom behavior for filtering a field, you can do so by extending one of the base filter classes in ``graphene_sqlalchemy.filters``. For example, if you'd like to add a ``divisible_by`` keyword to filter the age attribute on the ``Pet`` model, you can do so as follows:

.. code:: python

    class MathFilter(FloatFilter):
        class Meta:
            graphene_type = graphene.Float

        @classmethod
        def divisible_by_filter(cls, query, field, val: int) -> bool:
            return is_(field % val, 0)

    class PetType(SQLAlchemyObjectType):
        ...

        age = ORMField(filter_type=MathFilter)

    class Query(graphene.ObjectType):
        pets = SQLAlchemyConnectionField(PetType.connection)


Filtering over relationships with RelationshipFilter
----------------------------------------------------

When a filter class field refers to another object in a relationship, you may nest filters on relationship object attributes. This happens directly for 1:1 and m:1 relationships and through the ``contains`` and ``containsExactly`` keywords for 1:n and m:n relationships.


:1 relationships
^^^^^^^^^^^^^^^^

When an object or interface defines a singular relationship, relationship object attributes may be filtered directly like so:

Take the following SQLAlchemy model definition as an example:

.. code:: python

    class Pet
        id = Column(Integer(), primary_key=True)
        name = Column(String(30))
        person_id = Column(Integer(), ForeignKey("persons.id"))

    class Person
        id = Column(Integer(), primary_key=True)
        pets = relationship("Pet", backref="person")


Then, this query will return all pets whose person is named "Ada":

.. code::

    allPets(filter: {
        person: {name: {eq: "Ada"}}
    }) {
        ...
    }


:n relationships
^^^^^^^^^^^^^^^^

However, for plural relationships, relationship object attributes must be filtered through either ``contains`` or ``containsExactly``:

Now, using a many-to-many model definition:

.. code:: python

    people_pets_table = sqlalchemy.Table(
        "people_pets",
        Base.metadata,
        Column("person_id", ForeignKey("people.id")),
        Column("pet_id", ForeignKey("pets.id")),
    )

    class Pet
        __tablename__ = "pets"
        id = Column(Integer(), primary_key=True)
        name = Column(String(30))

    class Person
        --tablename__ = "people"
        id = Column(Integer(), primary_key=True)
        pets = relationship("Pet", backref="people")


this query will return all pets which have a person named "Ben" in their ``persons`` list.

.. code::

    allPets(filter: {
        people: {
            contains: [{name: {eq: "Ben"}}],
        }
    }) {
        ...
    }


and this one will return all pets which hvae a person list that contains exactly the people "Ada" and "Ben" and no fewer or people with other names.

.. code::

    allPets(filter: {
        articles: {
            containsExactly: [
                {name: {eq: "Ada"}},
                {name: {eq: "Ben"}},
            ],
        }
    }) {
        ...
    }

And/Or Logic
------------

Filters can also be chained together logically using `and` and `or` keywords nested under `filter`. Clauses are passed directly to `sqlalchemy.and_` and `slqlalchemy.or_`, respectively. To return all pets named "Fido" or "Spot", use:


.. code::

    allPets(filter: {
        or: [
            {name: {eq: "Fido"}},
            {name: {eq: "Spot"}},
        ]
    }) {
        ...
    }

And to return all pets that are named "Fido" or are 5 years old and named "Spot", use:

.. code::

    allPets(filter: {
        or: [
            {name: {eq: "Fido"}},
            { and: [
                {name: {eq: "Spot"}},
                {age: {eq: 5}}
            }
        ]
    }) {
        ...
    }


Hybrid Property support
-----------------------

Filtering over SQLAlchemy `hybrid properties <https://docs.sqlalchemy.org/en/20/orm/extensions/hybrid.html>`_ is fully supported.


Reporting feedback and bugs
---------------------------

Filtering is a new feature to graphene-sqlalchemy, so please `post an issue on Github <https://github.com/graphql-python/graphene-sqlalchemy/issues>`_ if you run into any problems or have ideas on how to improve the implementation.
