# demo-graphql-sqlalchemy-falcon

## Overview

This is a simple project demonstrating the implementation of a GraphQL server in Python using:

- [SQLAlchemy](https://github.com/zzzeek/sqlalchemy).
- [Falcon](https://github.com/falconry/falcon).
- [Graphene](https://github.com/graphql-python/graphene).
- [Graphene-SQLAlchemy](https://github.com/graphql-python/graphene-sqlalchemy).
- [Gunicorn](https://github.com/benoitc/gunicorn).

The objective is to demonstrate how these different libraries can be integrated.

## Features

The primary feature offered by this demo are:

- [SQLAlchemy](https://github.com/zzzeek/sqlalchemy) ORM against a local SQLite database. The ORM is super simple but showcases a many-to-many relationship between `authors` and `books` via an `author_books` association table.
- [Falcon](https://github.com/falconry/falcon) resources to serve both [GraphQL](https://github.com/facebook/graphql) and [GraphiQL](https://github.com/graphql/graphiql).

> The [Falcon](https://github.com/falconry/falcon) resources are slightly modified versions of the ones under [https://github.com/alecrasmussen/falcon-graphql-server](https://github.com/alecrasmussen/falcon-graphql-server) so all credits to [Alec Rasmussen](https://github.com/alecrasmussen).

- Basic [GraphQL](https://github.com/facebook/graphql) schema automatically derived from the [SQLAlchemy](https://github.com/zzzeek/sqlalchemy) ORM via [Graphene](https://github.com/graphql-python/graphene) and [Graphene-SQLAlchemy](https://github.com/graphql-python/graphene-sqlalchemy).
- API setup via [Falcon](https://github.com/falconry/falcon) with the whole thing served via [Gunicorn](https://github.com/benoitc/gunicorn).

## Usage

All instructions and commands below are meant to be run from the root dir of this repo.

### Prerequisites

You are strongly encouraged to use a virtualenv here but I can be assed writing down the instructions for that.

Install all requirements through:

```
pip install -r requirements.txt
```

### Sample Database

The sample SQLite database has been committed in this repo but can easily be rebuilt through:

```
python -m demo.orm
```

at which point it will create a `demo.db` in the root of this repo.

> The sample data are defined under `data.py` while they're ingested with the code under the `main` sentinel in `orm.py`. Feel free to tinker.

### Running Server

The [Gunicorn](https://github.com/benoitc/gunicorn) is configured via the `gunicorn_config.py` module and binds by default to `localhost:5432/`. You can change all gunicorn configuration options under the aforementioned module.

The server can be run through:

```
gunicorn -c gunicorn_config.py "demo.demo:main()"
```

The server exposes two endpoints:

- `/graphql`: The standard GraphQL endpoint which can receive the queries directly (accessible by default under [http://localhost:5432/graphql](http://localhost:5432/graphql)).
- `/graphiql`: The [GraphiQL](https://github.com/graphql/graphiql) interface (accessible by default under [http://localhost:5432/graphiql](http://localhost:5432/graphiql)).

### Queries

Here's a couple example queries you can either run directly in [GraphiQL](https://github.com/graphql/graphiql) or by performing POST requests against the [GraphQL](https://github.com/facebook/graphql) server.

#### Get an author by ID

Query:

```
query getAuthor{
  author(authorId: 1) {
    nameFirst,
    nameLast
  }
}
```

Response:

```
{
  "data": {
    "author": {
      "nameFirst": "Robert",
      "nameLast": "Jordan"
    }
  }
}
```

#### Get an author by first name

```
query getAuthor{
  author(nameFirst: "Robert") {
    nameFirst,
    nameLast
  }
}
```

Response:

```
{
  "data": {
    "author": {
      "nameFirst": "Robert",
      "nameLast": "Jordan"
    }
  }
}
```

### Get an author and their books

Query:

```
query getAuthor{
  author(nameFirst: "Brandon") {
    nameFirst,
    nameLast,
    books {
      title,
      year
    }
  }
}
```

Response:

```
{
  "data": {
    "author": {
      "nameFirst": "Brandon",
      "nameLast": "Sanderson",
      "books": [
        {
          "title": "The Gathering Storm",
          "year": 2009
        },
        {
          "title": "Towers of Midnight",
          "year": 2010
        },
        {
          "title": "A Memory of Light",
          "year": 2013
        }
      ]
    }
  }
}
```

#### Get books by year

Query:

```
query getBooks{
  books(year: 1990) {
    title,
    year
  }
}
```

Response:

```
{
  "data": {
    "books": [
      {
        "title": "The Eye of the World",
        "year": 1990
      },
      {
        "title": "The Great Hunt",
        "year": 1990
      }
    ]
  }
}
```

#### Get books and their authors by their title

Query:

```
query getBooks{
  books(title: "A Memory of Light") {
    title,
    year,
    authors {
      nameFirst,
      nameLast
    }
  }
}
```

Response:

```
{
  "data": {
    "books": [
      {
        "title": "A Memory of Light",
        "year": 2013,
        "authors": [
          {
            "nameFirst": "Robert",
            "nameLast": "Jordan"
          },
          {
            "nameFirst": "Brandon",
            "nameLast": "Sanderson"
          }
        ]
      }
    ]
  }
}
```

#### Get number of books by cover-artist

Query:

```
query getCountBooksByCoverArtist{
  stats {
    countBooksByCoverArtist {
      coverArtist,
      countBooks
    }
  }
}
```

Response:

```
{
  "data": {
    "stats": {
      "countBooksByCoverArtist": [
        {
          "coverArtist": null,
          "countBooks": 1
        },
        {
          "coverArtist": "Darrell K. Sweet",
          "countBooks": 12
        },
        {
          "coverArtist": "Michael Whelan",
          "countBooks": 1
        }
      ]
    }
  }
}
```

#### Add new author

Query:

```
mutation createAuthor{
  createAuthor(author: {
    nameFirst: "First Name",
    nameLast: "Last Name"
  }) {
    author {
      authorId
      nameFirst
      nameLast
    }
  }
}
```

Response:

```
{
  "data": {
    "createAuthor": {
      "author": {
        "authorId": "3",
        "nameFirst": "First Name",
        "nameLast": "Last Name"
      }
    }
  }
}
```