Inheritance Examples
====================

Create interfaces from inheritance relationships
------------------------------------------------
.. note:: If you're using `AsyncSession`, please check the section `Eager Loading & Using with AsyncSession`_.
SQLAlchemy has excellent support for class inheritance hierarchies.
These hierarchies can be represented in your GraphQL schema by means
of interfaces_.  Much like ObjectTypes, Interfaces in
Graphene-SQLAlchemy are able to infer their fields and relationships
from the attributes of their underlying SQLAlchemy model:

.. _interfaces: https://docs.graphene-python.org/en/latest/types/interfaces/

.. code:: python

    from sqlalchemy import Column, Date, Integer, String
    from sqlalchemy.ext.declarative import declarative_base

    import graphene
    from graphene import relay
    from graphene_sqlalchemy import SQLAlchemyInterface, SQLAlchemyObjectType

    Base = declarative_base()

    class Person(Base):
        id = Column(Integer(), primary_key=True)
        type = Column(String())
        name = Column(String())
        birth_date = Column(Date())

        __tablename__ = "person"
        __mapper_args__ = {
            "polymorphic_on": type,
        }

    class Employee(Person):
        hire_date = Column(Date())

        __mapper_args__ = {
            "polymorphic_identity": "employee",
        }

    class Customer(Person):
        first_purchase_date = Column(Date())

        __mapper_args__ = {
            "polymorphic_identity": "customer",
        }

    class PersonType(SQLAlchemyInterface):
        class Meta:
            model = Person

    class EmployeeType(SQLAlchemyObjectType):
        class Meta:
            model = Employee
            interfaces = (relay.Node, PersonType)

    class CustomerType(SQLAlchemyObjectType):
        class Meta:
            model = Customer
            interfaces = (relay.Node, PersonType)

Keep in mind that `PersonType` is a `SQLAlchemyInterface`. Interfaces must
be linked to an abstract Model that does not specify a `polymorphic_identity`,
because we cannot return instances of interfaces from a GraphQL query.
If Person specified a `polymorphic_identity`, instances of Person could
be inserted into and returned by the database, potentially causing
Persons to be returned to the resolvers.

When querying on the base type, you can refer directly to common fields,
and fields on concrete implementations using the `... on` syntax:


.. code::

    people {
        name
        birthDate
        ... on EmployeeType {
            hireDate
        }
        ... on CustomerType {
            firstPurchaseDate
        }
    }


.. danger::
    When using joined table inheritance, this style of querying may lead to unbatched implicit IO with negative performance implications.
    See the chapter `Eager Loading & Using with AsyncSession`_ for more information on eager loading all possible types of a `SQLAlchemyInterface`.

Please note that by default, the "polymorphic_on" column is *not*
generated as a field on types that use polymorphic inheritance, as
this is considered an implementation detail. The idiomatic way to
retrieve the concrete GraphQL type of an object is to query for the
`__typename` field.
To override this behavior, an `ORMField` needs to be created
for the custom type field on the corresponding  `SQLAlchemyInterface`. This is *not recommended*
as it promotes abiguous schema design

If your SQLAlchemy model only specifies a relationship to the
base type, you will need to explicitly pass your concrete implementation
class to the Schema constructor via the `types=` argument:

.. code:: python

    schema = graphene.Schema(..., types=[PersonType, EmployeeType, CustomerType])


See also: `Graphene Interfaces <https://docs.graphene-python.org/en/latest/types/interfaces/>`_

Eager Loading & Using with AsyncSession
----------------------------------------
When querying the base type in multi-table inheritance or joined table inheritance, you can only directly refer to polymorphic fields when they are loaded eagerly.
This restricting is in place because AsyncSessions don't allow implicit async operations such as the loads of the joined tables.
To load the polymorphic fields eagerly, you can use the `with_polymorphic` attribute of the mapper args in the base model:

.. code:: python

    class Person(Base):
        id = Column(Integer(), primary_key=True)
        type = Column(String())
        name = Column(String())
        birth_date = Column(Date())

        __tablename__ = "person"
        __mapper_args__ = {
            "polymorphic_on": type,
            "with_polymorphic": "*", # needed for eager loading in async session
        }

Alternatively, the specific polymorphic fields can be loaded explicitly in resolvers:

.. code:: python

    class Query(graphene.ObjectType):
        people = graphene.Field(graphene.List(PersonType))

        async def resolve_people(self, _info):
            return (await session.scalars(with_polymorphic(Person, [Engineer, Customer]))).all()

Dynamic batching of the types based on the query to avoid eager is currently not supported, but could be implemented in a future PR.

For more information on loading techniques for polymorphic models, please check out the `SQLAlchemy docs <https://docs.sqlalchemy.org/en/20/orm/queryguide/inheritance.html>`_.
