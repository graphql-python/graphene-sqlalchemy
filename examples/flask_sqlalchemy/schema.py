from models import Department as DepartmentModel
from models import Employee as EmployeeModel
from models import Role as RoleModel

import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyConnectionField, SQLAlchemyObjectType


class CountableConnection(relay.Connection):
    """
    Extend the pagination from https://relay.dev/graphql/connections.htm with
    ``totalCount``, as suggested on https://graphql.org/learn/pagination
    """

    class Meta:
        abstract = True

    total_count = graphene.Int(description='Total number of (paginated) results.')

    @staticmethod
    def resolve_total_count(connection, info, *args, **kwargs):
        return connection.length


class Department(SQLAlchemyObjectType):
    class Meta:
        model = DepartmentModel
        description = 'A department with `Employee`s.'
        connection_class = CountableConnection
        interfaces = (relay.Node, )


class Employee(SQLAlchemyObjectType):
    class Meta:
        model = EmployeeModel
        description = 'An employee with a specific `Role` in a `Department`.'
        connection_class = CountableConnection
        interfaces = (relay.Node, )


class Role(SQLAlchemyObjectType):
    class Meta:
        model = RoleModel
        description = 'A role for `Employee`s.'
        connection_class = CountableConnection
        interfaces = (relay.Node, )


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    # Allow sorting over one or multiple columns, by default over the primary
    # key, e.g. `all_employees(sort: [HIRED_ON_ASC, NAME_ASC, ID_ASC])`; not
    # specifying `sort` is the same as using `sort=Employee.sort_argument()`
    all_employees = SQLAlchemyConnectionField(Employee.connection)

    # Allow sorting on a single column only, e.g. `all_roles(sort: NAME_ASC)`
    # or `all_roles(sort: ID_ASC)` but not a combination
    all_roles_sort = Role.sort_enum()
    all_roles = SQLAlchemyConnectionField(
        Role.connection,
        sort=graphene.Argument(all_roles_sort, all_roles_sort.default))

    # Disable sorting over this field
    all_departments = SQLAlchemyConnectionField(Department.connection, sort=None)


schema = graphene.Schema(query=Query)
