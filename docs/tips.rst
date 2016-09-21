====
Tips
====

Tips
====

Querying
--------

For make querying to the database work, there are two alternatives:

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
