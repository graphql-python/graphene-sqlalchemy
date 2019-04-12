from models import Department as DepartmentModel
from models import Employee as EmployeeModel
from models import Role as RoleModel

import graphene
from graphene import relay
from graphene_sqlalchemy import (SQLAlchemyConnectionField,
                                 SQLAlchemyObjectType, utils)


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


SortEnumEmployee = utils.get_sort_enum_for_model(EmployeeModel)


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    # Allow only single column sorting
    all_employees = SQLAlchemyConnectionField(
        Employee,
        sort=graphene.Argument(
            SortEnumEmployee,
            default_value=utils.EnumValue('id_asc', EmployeeModel.id.asc())))
    # Allows sorting over multiple columns, by default over the primary key
    all_roles = SQLAlchemyConnectionField(Role)
    # Disable sorting over this field
    all_departments = SQLAlchemyConnectionField(Department, sort=None)


schema = graphene.Schema(query=Query, types=[Department, Employee, Role])
