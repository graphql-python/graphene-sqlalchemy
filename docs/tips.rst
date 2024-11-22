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


Aggregating
-----------

By default the `sqlalchemy.orm.Query` object that is retrieved through the `SQLAlchemyObjectType.get_query` method auto-selects the underlying SQLAlchemy ORM class. In order to change fields under the `SELECT` statement, e.g., when performing an aggregation, one can retrieve the `sqlalchemy.orm.Session` object from the provided `info` argument and create a new query as such:

.. code::

    session = info.context.get("session")  # type: sqlalchemy.orm.Session
    query = session.query(SomeOtherModel, some_aggregation_function)

Consider the following SQLAlchemy ORM models:

.. code::

    class Author(Base):
        __tablename__ = "authors"

        author_id = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            primary_key=True,
        )

        name_first = sqlalchemy.Column(
            sqlalchemy.types.Unicode(length=80),
            nullable=False,
        )

        name_last = sqlalchemy.Column(
            sqlalchemy.types.Unicode(length=80),
            nullable=False,
        )

        books = sqlalchemy.orm.relationship(
            argument="Book",
            secondary="author_books",
            back_populates="authors",
        )


    class Book(Base):
        __tablename__ = "books"

        book_id = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            primary_key=True,
        )

        title = sqlalchemy.Column(
            sqlalchemy.types.Unicode(length=80),
            nullable=False,
        )

        year = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            nullable=False,
        )

        cover_artist = sqlalchemy.Column(
            sqlalchemy.types.Unicode(length=80),
            nullable=True,
        )

        authors = sqlalchemy.orm.relationship(
            argument="Author",
            secondary="author_books",
            back_populates="books",
        )


    class AuthorBook(Base):
        __tablename__ = "author_books"

        author_book_id = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            primary_key=True,
        )

        author_id = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            sqlalchemy.ForeignKey("authors.author_id"),
            index=True,
        )

        book_id = sqlalchemy.Column(
            sqlalchemy.types.Integer(),
            sqlalchemy.ForeignKey("books.book_id"),
            index=True,
        )

exposed to the GraphQL schema through the following types:

.. code::

    class TypeAuthor(SQLAlchemyObjectType):
        class Meta:
            model = Author


    class TypeBook(SQLAlchemyObjectType):
        class Meta:
            model = Book


    class TypeAuthorBook(SQLAlchemyObjectType):
        class Meta:
            model = AuthorBook

If we wanted to perform an aggregation, e.g., count the number of books by cover-artist, we'd first define such a custom type:

.. code::

    class TypeCountBooksCoverArtist(graphene.ObjectType):
        cover_artist = graphene.String()
        count_books = graphene.Int()

which we can then expose through a class deriving `graphene.ObjectType` as follows:

.. code::

    class TypeStats(graphene.ObjectType):

        count_books_by_cover_artist = graphene.List(
            of_type=TypeCountBooksCoverArtist
        )

        @staticmethod
        def resolve_count_books_by_cover_artist(
            args: Dict,
            info: graphql.execution.base.ResolveInfo,
        ) -> List[TypeCountBooksCoverArtist]:
            # Retrieve the session out of the context as the `get_query` method
            # automatically selects the model.
            session = info.context.get("session")  # type: sqlalchemy.orm.Session

            # Define the `COUNT(books.book_id)` function.
            func_count_books = sqlalchemy_func.count(Book.book_id)

            # Query out the count of books by cover-artist
            query = session.query(Book.cover_artist, func_count_books)
            query = query.group_by(Book.cover_artist)
            results = query.all()

            # Wrap the results of the aggregation in `TypeCountBooksCoverArtist`
            # objects.
            objs = [
                TypeCountBooksCoverArtist(
                    cover_artist=result[0],
                    count_books=result[1]
                ) for result in results
            ]

            return objs

As can be seen, the `sqlalchemy.orm.Session` object is retrieved from the `info.context` and a new query specifying the desired field and aggregation function is defined. The results of the aggregation do not directly correspond to an ORM class so they're wrapped in the `TypeCountBooksCoverArtist` class and returned.

The `TypeStats` class can then be exposed under the `Query` class as such:

.. code::

    class Query(graphene.ObjectType):

        stats = graphene.Field(type=TypeStats)

        @staticmethod
        def resolve_stats(
            args: Dict,
            info: graphql.execution.base.ResolveInfo,
        ):
            return TypeStats

thus allowing for the following query:

.. code::

    query getCountBooksByCoverArtist{
      stats {
        countBooksByCoverArtist {
          coverArtist,
          countBooks
        }
      }
    }
