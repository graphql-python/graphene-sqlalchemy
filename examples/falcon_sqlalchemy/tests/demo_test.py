# coding=utf-8

import unittest

from graphene.test import Client
import sqlalchemy.orm

from demo.schema import schema


class DemoTest(unittest.TestCase):

    def setUp(self):
        # Create engine to local SQLite database.
        engine = sqlalchemy.create_engine("sqlite:///demo.db", echo=True)

        # Prepare a DB session.
        session_maker = sqlalchemy.orm.sessionmaker(bind=engine)
        self.session = session_maker()

        # Prepare a Graphene client.
        self.client = Client(schema)

    def tearDown(self):
        self.session.close()

    def test_query_get_author_by_id(self):
        """Tests the retrieval of a single author by ID."""

        query = """
            query getAuthor{
              author(authorId: 1) {
                nameFirst,
                nameLast
              }
            }
        """

        result_refr = {
            "data": {
                "author": {
                    "nameFirst": "Robert",
                    "nameLast": "Jordan",
                }
            }
        }

        result_eval = self.client.execute(
            query, context_value={"session": self.session}
        )

        self.assertDictEqual(result_refr, result_eval)

    def test_get_author_by_name_include_books(self):
        """Tests the retrieval of a single author and their books by first name
        ."""

        query = """
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
        """

        result_refr = {
            "data": {
                "author": {
                    "nameFirst": "Brandon",
                    "nameLast": "Sanderson",
                    "books": [
                        {
                            "title": "The Gathering Storm",
                            "year": 2009,
                        },
                        {
                            "title": "Towers of Midnight",
                            "year": 2010,
                        },
                        {
                            "title": "A Memory of Light",
                            "year": 2013,
                        },
                    ],
                }
            }
        }

        result_eval = self.client.execute(
            query, context_value={"session": self.session}
        )

        self.assertDictEqual(result_refr, result_eval)

    def test_get_author_by_name_include_books_fragment(self):
        """Tests the retrieval of a single author and their books by first name
        while using query fragments."""

        query = """
            query getAuthor{
              author(nameFirst: "Brandon") {
                ...authorFields
                books {
                  ...bookFields
                }
              }
            }
            
            fragment authorFields on TypeAuthor {
              nameFirst,
              nameLast
            }
            
            fragment bookFields on TypeBook {
              title,
              year
            }
        """

        result_refr = {
            "data": {
                "author": {
                    "nameFirst": "Brandon",
                    "nameLast": "Sanderson",
                    "books": [
                        {
                            "title": "The Gathering Storm",
                            "year": 2009,
                        },
                        {
                            "title": "Towers of Midnight",
                            "year": 2010,
                        },
                        {
                            "title": "A Memory of Light",
                            "year": 2013,
                        },
                    ],
                }
            }
        }

        result_eval = self.client.execute(
            query, context_value={"session": self.session}
        )

        self.assertDictEqual(result_refr, result_eval)
