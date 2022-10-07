import graphene
from graphene import relay
from models import Department as DepartmentModel
from models import Employee as EmployeeModel
from models import Role as RoleModel

from graphene_sqlalchemy import SQLAlchemyConnectionField, SQLAlchemyObjectType


class Department(SQLAlchemyObjectType):
    class Meta:
        model = DepartmentModel
        interfaces = (relay.Node,)


class Employee(SQLAlchemyObjectType):
    class Meta:
        model = EmployeeModel
        interfaces = (relay.Node,)


class Role(SQLAlchemyObjectType):
    class Meta:
        model = RoleModel
        interfaces = (relay.Node,)


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    all_employees = SQLAlchemyConnectionField(Employee.connection)
    all_roles = SQLAlchemyConnectionField(Role.connection)
    role = graphene.Field(Role)


schema = graphene.Schema(query=Query)
