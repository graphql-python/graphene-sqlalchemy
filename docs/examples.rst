Schema Examples
===========================


Search all Models with Union
-----------------

.. code:: python

    class Book(SQLAlchemyObjectType):
        class Meta:
            model = BookModel
            interfaces = (relay.Node,)
    
    
    class Author(SQLAlchemyObjectType):
        class Meta:
            model = AuthorModel
            interfaces = (relay.Node,)


    class SearchResult(graphene.Union):
        class Meta:
            types = (Book, Author)


    class Query(graphene.ObjectType):
        node = relay.Node.Field()
        search = graphene.List(SearchResult, q=graphene.String())  # List field for search results
        
        # Normal Fields
        all_books = SQLAlchemyConnectionField(Book)
        all_authors = SQLAlchemyConnectionField(Author)

        def resolve_search(self, info, **args):
            q = args.get("q")  # Search query
            
            # Get queries
            bookdata_query = BookData.get_query(info)
            author_query = Author.get_query(info)

            # Query Books
            books = bookdata_query.filter((BookModel.title.contains(q)) |
                                          (BookModel.isbn.contains(q)) |
                                          (BookModel.authors.any(AuthorModel.name.contains(q)))).all()
            
            # Query Authors
            authors = author_query.filter(AuthorModel.name.contains(q)).all()

        return authors + books  # Combine lists

    schema = graphene.Schema(query=Query, types=[Book, Author, SearchResult])
    
Example GraphQL query

.. code:: GraphQL

    book(id: "Qm9vazow") {
        id
        title
    }
    search(q: "Making Games") {
        __typename
        ... on Author {
            fname
            lname
        }
        ... on Book {
            title
            isbn
        }
    }
