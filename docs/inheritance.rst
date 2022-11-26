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

    from sqlalchemy import Column, DateTime, Integer, String
    from sqlalchemy.ext.declarative import declarative_base

    import graphene
    from graphene import relay
    from graphene_sqlalchemy import SQLAlchemyInterface, SQLAlchemyObjectType

    Base = declarative_base()

    class PersonModel(Base):
        id = Column(Integer, primary_key=True)
        type = Column(String, nullable=False)
        name = Column(String, nullable=False)
        birth_date = Column(DateTime, nullable=False)

        __tablename__ = "person"
        __mapper_args__ = {
            "polymorphic_on": type,
            "polymorphic_identity": "person",
        }

    class EmployeeModel(PersonModel):
        hire_date = Column(DateTime, nullable=False)

        __mapper_args__ = {
            "polymorphic_identity": "employee",
        }

    class Person(SQLAlchemyInterface):
        class Meta:
            model = PersonModel

    class Employee(SQLAlchemyObjectType):
        class Meta:
            model = EmployeeModel
            interfaces = (relay.Node, Person)


When querying on the base type, you can refer directly to common fields,
and fields on concrete implementations using the `... on` syntax:

.. code::

    people {
        name
        birthDate
        ... on Employee {
            hireDate
        }
    }

Note that if your SQLAlchemy model only specifies a relationship to the
base type, you will need to explicitly pass your concrete implementation
class to the Schema constructor via the `types=` argument:

.. code:: python

    schema = graphene.Schema(..., types=[Person, Employee])
