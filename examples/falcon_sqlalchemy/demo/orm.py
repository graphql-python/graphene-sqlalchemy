# coding=utf-8

import sqlalchemy.orm

from demo import data
from demo.orm_base import Base, OrmBaseMixin


class Author(Base, OrmBaseMixin):
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


class Book(Base, OrmBaseMixin):
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


class AuthorBook(Base, OrmBaseMixin):
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


if __name__ == "__main__":

    # Create engine to local SQLite database.
    engine = sqlalchemy.create_engine("sqlite:///demo.db", echo=True)

    # Drop and recreate the entire schema
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # Prepare a DB session.
    session_maker = sqlalchemy.orm.sessionmaker(bind=engine)
    session = session_maker()

    # Create `Author` records.
    author_objs = []
    for _author_item in data.authors["data"]:
        author_obj = Author()
        author_obj.author_id = _author_item["author_id"]
        author_obj.name_first = _author_item["name_first"]
        author_obj.name_last = _author_item["name_last"]
        author_objs.append(author_obj)
    session.add_all(author_objs)
    session.commit()

    # Create `Book` authors.
    book_objs = []
    for _book_item in data.books["data"]:
        book_obj = Book()
        book_obj.book_id = _book_item["book_id"]
        book_obj.title = _book_item["title"]
        book_obj.year = _book_item["year"]
        book_obj.cover_artist = _book_item["cover_artist"]
        book_objs.append(book_obj)
    session.add_all(book_objs)
    session.commit()

    # Create `AuthorBook` records.
    author_book_objs = []
    for _author_book_item in data.author_books["data"]:
        author_book_obj = AuthorBook()
        author_book_obj.author_book_id = _author_book_item["author_book_id"]
        author_book_obj.author_id = _author_book_item["author_id"]
        author_book_obj.book_id = _author_book_item["book_id"]
        author_book_objs.append(author_book_obj)
    session.add_all(author_book_objs)
    session.commit()
