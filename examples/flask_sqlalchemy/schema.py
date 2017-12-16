import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyConnectionField, SQLAlchemyObjectType, utils
from models import Department as DepartmentModel
from models import Employee as EmployeeModel
from models import Role as RoleModel


class Department(SQLAlchemyObjectType):

    class Meta:
        model = DepartmentModel
        interfaces = (relay.Node, )


class Employee(SQLAlchemyObjectType):

    class Meta:
        model = EmployeeModel
        interfaces = (relay.Node, )


class Role(SQLAlchemyObjectType):

    class Meta:
        model = RoleModel
        interfaces = (relay.Node, )


SortEnumEmployee = utils.sort_enum_for_model(
    EmployeeModel, 'SortEnumEmployee',
    lambda c, d: c.upper() + ('_ASC' if d else '_DESC'))


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    all_employees = SQLAlchemyConnectionField(
        Employee, sort=graphene.Argument(SortEnumEmployee, default_value=EmployeeModel.id))
    all_roles = SQLAlchemyConnectionField(Role, sort=utils.sort_argument_for_model(RoleModel))
    all_departments = SQLAlchemyConnectionField(Department)


schema = graphene.Schema(query=Query, types=[Department, Employee, Role])
