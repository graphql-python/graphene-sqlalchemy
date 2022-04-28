SQLAlchemy + Flask Tutorial
===========================

Graphene comes with builtin support to SQLAlchemy, which makes quite
easy to operate with your current models.

Note: The code in this tutorial is pulled from the `Flask SQLAlchemy
example
app <https://github.com/graphql-python/graphene-sqlalchemy/tree/master/examples/flask_sqlalchemy>`__.

Setup the Project
-----------------

We will setup the project, execute the following:

.. code:: bash

    # Create the project directory
    mkdir flask_sqlalchemy
    cd flask_sqlalchemy

    # Create a virtualenv to isolate our package dependencies locally
    virtualenv env
    source env/bin/activate  # On Windows use `env\Scripts\activate`

    # SQLAlchemy and Graphene with SQLAlchemy support
    pip install SQLAlchemy
    pip install graphene_sqlalchemy

    # Install Flask and GraphQL Flask for exposing the schema through HTTP
    pip install Flask
    pip install Flask-GraphQL

Defining our models
-------------------

Let's get started with these models:

.. code:: python

    # flask_sqlalchemy/models.py
    from sqlalchemy import *
    from sqlalchemy.orm import (scoped_session, sessionmaker, relationship,
                                backref)
    from sqlalchemy.ext.declarative import declarative_base

    engine = create_engine('sqlite:///database.sqlite3', convert_unicode=True)
    db_session = scoped_session(sessionmaker(autocommit=False,
                                             autoflush=False,
                                             bind=engine))

    Base = declarative_base()
    # We will need this for querying
    Base.query = db_session.query_property()


    class Department(Base):
        __tablename__ = 'department'
        id = Column(Integer, primary_key=True)
        name = Column(String)


    class Employee(Base):
        __tablename__ = 'employee'
        id = Column(Integer, primary_key=True)
        name = Column(String)
        hired_on = Column(DateTime, default=func.now())
        department_id = Column(Integer, ForeignKey('department.id'))
        department = relationship(
            Department,
            backref=backref('employees',
                            uselist=True,
                            cascade='delete,all'))

Schema
------

GraphQL presents your objects to the world as a graph structure rather
than a more hierarchical structure to which you may be accustomed. In
order to create this representation, Graphene needs to know about each
*type* of object which will appear in the graph.

This graph also has a *root type* through which all access begins. This
is the ``Query`` class below. In this example, we provide the ability to
list all employees via ``all_employees``, and the ability to obtain a
specific node via ``node``.

Create ``flask_sqlalchemy/schema.py`` and type the following:

.. code:: python

    # flask_sqlalchemy/schema.py
    import graphene
    from graphene import relay
    from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
    from .models import db_session, Department as DepartmentModel, Employee as EmployeeModel


    class Department(SQLAlchemyObjectType):
        class Meta:
            model = DepartmentModel
            interfaces = (relay.Node, )


    class Employee(SQLAlchemyObjectType):
        class Meta:
            model = EmployeeModel
            interfaces = (relay.Node, )


    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        # Allows sorting over multiple columns, by default over the primary key
        all_employees = SQLAlchemyConnectionField(Employee.connection)
        # Disable sorting over this field
        all_departments = SQLAlchemyConnectionField(Department.connection, sort=None)

    schema = graphene.Schema(query=Query)

Creating GraphQL and GraphiQL views in Flask
--------------------------------------------

Unlike a RESTful API, there is only a single URL from which GraphQL is
accessed.

We are going to use Flask to create a server that expose the GraphQL
schema under ``/graphql`` and a interface for querying it easily:
GraphiQL (also under ``/graphql`` when accessed by a browser).

Fortunately for us, the library ``Flask-GraphQL`` that we previously
installed makes this task quite easy.

.. code:: python

    # flask_sqlalchemy/app.py
    from flask import Flask
    from flask_graphql import GraphQLView

    from .models import db_session
    from .schema import schema, Department

    app = Flask(__name__)
    app.debug = True

    app.add_url_rule(
        '/graphql',
        view_func=GraphQLView.as_view(
            'graphql',
            schema=schema,
            graphiql=True # for having the GraphiQL interface
        )
    )

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    if __name__ == '__main__':
        app.run()

Creating some data
------------------

.. code:: bash

    $ python

    >>> from .models import engine, db_session, Base, Department, Employee
    >>> Base.metadata.create_all(bind=engine)

    >>> # Fill the tables with some data
    >>> engineering = Department(name='Engineering')
    >>> db_session.add(engineering)
    >>> hr = Department(name='Human Resources')
    >>> db_session.add(hr)

    >>> peter = Employee(name='Peter', department=engineering)
    >>> db_session.add(peter)
    >>> roy = Employee(name='Roy', department=engineering)
    >>> db_session.add(roy)
    >>> tracy = Employee(name='Tracy', department=hr)
    >>> db_session.add(tracy)
    >>> db_session.commit()

Testing our GraphQL schema
--------------------------

We're now ready to test the API we've built. Let's fire up the server
from the command line.

.. code:: bash

    $ python ./app.py

     * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)

Go to `localhost:5000/graphql <http://localhost:5000/graphql>`__ and
type your first query!

.. code::

    {
      allEmployees {
        edges {
          node {
            id
            name
            department {
              name
            }
          }
        }
      }
    }
