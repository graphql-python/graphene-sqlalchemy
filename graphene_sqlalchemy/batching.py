"""The dataloader uses "select in loading" strategy to load related entities."""
from asyncio import get_event_loop
from typing import Dict

import aiodataloader
import sqlalchemy
from sqlalchemy.orm import Session, strategies
from sqlalchemy.orm.query import QueryContext

from .utils import is_sqlalchemy_version_less_than


class RelationshipLoader(aiodataloader.DataLoader):
    cache = False

    def __init__(self, relationship_prop, selectin_loader):
        super().__init__()
        self.relationship_prop = relationship_prop
        self.selectin_loader = selectin_loader

    async def batch_load_fn(self, parents):
        """
        Batch loads the relationships of all the parents as one SQL statement.

        There is no way to do this out-of-the-box with SQLAlchemy but
        we can piggyback on some internal APIs of the `selectin`
        eager loading strategy. It's a bit hacky but it's preferable
        than re-implementing and maintainnig a big chunk of the `selectin`
        loader logic ourselves.

        The approach here is to build a regular query that
        selects the parent and `selectin` load the relationship.
        But instead of having the query emits 2 `SELECT` statements
        when callling `all()`, we skip the first `SELECT` statement
        and jump right before the `selectin` loader is called.
        To accomplish this, we have to construct objects that are
        normally built in the first part of the query in order
        to call directly `SelectInLoader._load_for_path`.

        TODO Move this logic to a util in the SQLAlchemy repo as per
            SQLAlchemy's main maitainer suggestion.
            See https://git.io/JewQ7
        """
        child_mapper = self.relationship_prop.mapper
        parent_mapper = self.relationship_prop.parent
        session = Session.object_session(parents[0])

        # These issues are very unlikely to happen in practice...
        for parent in parents:
            # assert parent.__mapper__ is parent_mapper
            # All instances must share the same session
            assert session is Session.object_session(parent)
            # The behavior of `selectin` is undefined if the parent is dirty
            assert parent not in session.dirty

        # Should the boolean be set to False? Does it matter for our purposes?
        states = [(sqlalchemy.inspect(parent), True) for parent in parents]

        # For our purposes, the query_context will only used to get the session
        query_context = None
        if is_sqlalchemy_version_less_than('1.4'):
            query_context = QueryContext(session.query(parent_mapper.entity))
        else:
            parent_mapper_query = session.query(parent_mapper.entity)
            query_context = parent_mapper_query._compile_context()

        if is_sqlalchemy_version_less_than('1.4'):
            self.selectin_loader._load_for_path(
                query_context,
                parent_mapper._path_registry,
                states,
                None,
                child_mapper,
            )
        else:
            self.selectin_loader._load_for_path(
                query_context,
                parent_mapper._path_registry,
                states,
                None,
                child_mapper,
                None,
            )
        return [
            getattr(parent, self.relationship_prop.key) for parent in parents
        ]


# Cache this across `batch_load_fn` calls
# This is so SQL string generation is cached under-the-hood via `bakery`
# Caching the relationship loader for each relationship prop.
RELATIONSHIP_LOADERS_CACHE: Dict[
    sqlalchemy.orm.relationships.RelationshipProperty, RelationshipLoader
] = {}


def get_batch_resolver(relationship_prop):
    """Get the resolve function for the given relationship."""

    def _get_loader(relationship_prop):
        """Retrieve the cached loader of the given relationship."""
        loader = RELATIONSHIP_LOADERS_CACHE.get(relationship_prop, None)
        if loader is None or loader.loop != get_event_loop():
            selectin_loader = strategies.SelectInLoader(
                relationship_prop, (('lazy', 'selectin'),)
            )
            loader = RelationshipLoader(
                relationship_prop=relationship_prop,
                selectin_loader=selectin_loader,
            )
            RELATIONSHIP_LOADERS_CACHE[relationship_prop] = loader
        return loader

    loader = _get_loader(relationship_prop)

    async def resolve(root, info, **args):
        return await loader.load(root)

    return resolve
