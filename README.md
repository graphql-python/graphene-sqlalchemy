Version 3.0 is in beta stage. Please read https://github.com/graphql-python/graphene-sqlalchemy/issues/348 to learn about progress and changes in upcoming
beta releases.

---

# ![Graphene Logo](http://graphene-python.org/favicon.png) Graphene-SQLAlchemy 
[![Build Status](https://github.com/graphql-python/graphene-sqlalchemy/workflows/Tests/badge.svg)](https://github.com/graphql-python/graphene-sqlalchemy/actions)
[![PyPI version](https://badge.fury.io/py/graphene-sqlalchemy.svg)](https://badge.fury.io/py/graphene-sqlalchemy) 
![GitHub release (latest by date including pre-releases)](https://img.shields.io/github/v/release/graphql-python/graphene-sqlalchemy?color=green&include_prereleases&label=latest)
[![codecov](https://codecov.io/gh/graphql-python/graphene-sqlalchemy/branch/master/graph/badge.svg?token=Zi5S1TikeN)](https://codecov.io/gh/graphql-python/graphene-sqlalchemy)



A [SQLAlchemy](http://www.sqlalchemy.org/) integration for [Graphene](http://graphene-python.org/).

## Installation

For installing Graphene, just run this command in your shell.

```bash
pip install --pre "graphene-sqlalchemy"
```

## Examples

Here is a simple SQLAlchemy model:

```python
from sqlalchemy import Column, Integer, String

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserModel(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    last_name = Column(String)
```

To create a GraphQL schema for it, you simply have to write the following:

```python
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
```

Then you can simply query the schema:

```python
query = '''
    query {
      users {
        name,
        lastName
      }
    }
'''
result = schema.execute(query, context_value={'session': db_session})
```

You may also subclass SQLAlchemyObjectType by providing `abstract = True` in
your subclasses Meta:
```python
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
```

### Full Examples

To learn more check out the following [examples](https://github.com/graphql-python/graphene-sqlalchemy/tree/master/examples/):

- [Flask SQLAlchemy example](https://github.com/graphql-python/graphene-sqlalchemy/tree/master/examples/flask_sqlalchemy)
- [Nameko SQLAlchemy example](https://github.com/graphql-python/graphene-sqlalchemy/tree/master/examples/nameko_sqlalchemy)

## Contributing

See [CONTRIBUTING.md](https://github.com/graphql-python/graphene-sqlalchemy/blob/master/CONTRIBUTING.md)
