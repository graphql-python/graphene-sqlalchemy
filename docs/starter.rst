Getting Started
=================

Welcome to the graphene-sqlalchemy documentation!
Graphene is a powerful Python library for building GraphQL APIs,
and SQLAlchemy is a popular ORM (Object-Relational Mapping)
tool for working with databases. When combined, graphene-sqlalchemy
allows developers to quickly and easily create a GraphQL API that
seamlessly interacts with a SQLAlchemy-managed database.
It is fully compatible with SQLAlchemy 1.4 and 2.0.
This documentation provides detailed instructions on how to get
started with graphene-sqlalchemy, including installation, setup,
and usage examples.

Installation
------------

To install :code:`graphene-sqlalchemy`, just run this command in your shell:

.. code:: bash

   pip install --pre "graphene-sqlalchemy"

Examples
--------

Here is a simple SQLAlchemy model:

.. code:: python

   from sqlalchemy import Column, Integer, String
   from sqlalchemy.ext.declarative import declarative_base

   Base = declarative_base()

   class UserModel(Base):
       __tablename__ = 'user'
       id = Column(Integer, primary_key=True)
       name = Column(String)
       last_name = Column(String)

To create a GraphQL schema for it, you simply have to write the
following:

.. code:: python

   import graphene
   from graphene_sqlalchemy import SQLAlchemyObjectType

   class User(SQLAlchemyObjectType):
       class Meta:
           model = UserModel
           # use `only_fields` to only expose specific fields ie "name"
           # only_fields = ("name",)
           # use `exclude_fields` to exclude specific fields ie "last_name"
           # exclude_fields = ("last_name",)

   class Query(graphene.ObjectType):
       users = graphene.List(User)

       def resolve_users(self, info):
           query = User.get_query(info)  # SQLAlchemy query
           return query.all()

   schema = graphene.Schema(query=Query)

Then you can simply query the schema:

.. code:: python

   query = '''
       query {
         users {
           name,
           lastName
         }
       }
   '''
   result = schema.execute(query, context_value={'session': db_session})


It is important to provide a session for graphene-sqlalchemy to resolve the models.
In this example, it is provided using the GraphQL context. See :doc:`tips` for
other ways to implement this.

You may also subclass SQLAlchemyObjectType by providing
``abstract = True`` in your subclasses Meta:

.. code:: python

   from graphene_sqlalchemy import SQLAlchemyObjectType

   class ActiveSQLAlchemyObjectType(SQLAlchemyObjectType):
       class Meta:
           abstract = True

       @classmethod
       def get_node(cls, info, id):
           return cls.get_query(info).filter(
               and_(cls._meta.model.deleted_at==None,
                    cls._meta.model.id==id)
               ).first()

   class User(ActiveSQLAlchemyObjectType):
       class Meta:
           model = UserModel

   class Query(graphene.ObjectType):
       users = graphene.List(User)

       def resolve_users(self, info):
           query = User.get_query(info)  # SQLAlchemy query
           return query.all()

   schema = graphene.Schema(query=Query)

More complex inhertiance using SQLAlchemy's polymorphic models is also supported.
You can check out :doc:`inheritance` for a guide.
