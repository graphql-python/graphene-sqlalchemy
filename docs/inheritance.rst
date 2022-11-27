Inheritance Examples
====================

Create interfaces from inheritance relationships
------------------------------------------------

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
            "polymorphic_identity": "person",
        }

    class Employee(Person):
        hire_date = Column(Date())

        __mapper_args__ = {
            "polymorphic_identity": "employee",
        }

    class PersonType(SQLAlchemyInterface):
        class Meta:
            model = Person

    class EmployeeType(SQLAlchemyObjectType):
        class Meta:
            model = Employee
            interfaces = (relay.Node, PersonType)


When querying on the base type, you can refer directly to common fields,
and fields on concrete implementations using the `... on` syntax:

.. code::

    people {
        name
        birthDate
        ... on EmployeeType {
            hireDate
        }
    }

Note that if your SQLAlchemy model only specifies a relationship to the
base type, you will need to explicitly pass your concrete implementation
class to the Schema constructor via the `types=` argument:

.. code:: python

    schema = graphene.Schema(..., types=[PersonType, EmployeeType])
