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


class DepartmentConnection(relay.Connection):
    class Meta:
        node = Department


class Employee(SQLAlchemyObjectType):
    class Meta:
        model = EmployeeModel
        interfaces = (relay.Node, )


class EmployeeConnection(relay.Connection):
    class Meta:
        node = Employee


class Role(SQLAlchemyObjectType):
    class Meta:
        model = RoleModel
        interfaces = (relay.Node, )


class RoleConnection(relay.Connection):
    class Meta:
        node = Role


SortEnumEmployee = utils.sort_enum_for_model(EmployeeModel, 'SortEnumEmployee',
    lambda c, d: c.upper() + ('_ASC' if d else '_DESC'))


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    # Allow only single column sorting
    all_employees = SQLAlchemyConnectionField(
        EmployeeConnection,
        sort=graphene.Argument(
            SortEnumEmployee,
            default_value=utils.EnumValue('id_asc', EmployeeModel.id.asc())))
    # Allows sorting over multiple columns, by default over the primary key
    all_roles = SQLAlchemyConnectionField(RoleConnection)
    # Disable sorting over this field
    all_departments = SQLAlchemyConnectionField(DepartmentConnection, sort=None)


schema = graphene.Schema(query=Query, types=[Department, Employee, Role])
