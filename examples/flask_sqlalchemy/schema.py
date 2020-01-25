from models import Department as DepartmentModel
from models import Employee as EmployeeModel
from models import Role as RoleModel

import graphene
from graphql_relay.node.node import from_global_id
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyConnectionField, SQLAlchemyObjectType


# Just a util function 

def input_to_dictionary(input):
    """Method to convert Graphene inputs into dictionary"""
    dictionary = {}
    for key in input:
        # Convert GraphQL global id to database id
        if key[-2:] == 'id':
            input[key] = from_global_id(input[key])[1]
        dictionary[key] = input[key]
    return dictionary



# Queries Part :
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

class Query(graphene.ObjectType):
    node = relay.Node.Field()
    # Allow only single column sorting
    all_employees = SQLAlchemyConnectionField(
        Employee, sort=Employee.sort_argument())
    # Allows sorting over multiple columns, by default over the primary key
    all_roles = SQLAlchemyConnectionField(Role)
    # Disable sorting over this field
    all_departments = SQLAlchemyConnectionField(Department, sort=None)

# Mutation Part :
# only one exemple : employee.
class CreateEmployeeInput(SQLAlchemyInputObjectType):
    class Meta:
        # You have to exclude those fields to avoid conflict
        exclude_fields = ('id','uuid')
        model = EmployeeModel
        
class CreateEmployee(graphene.Mutation):
    class Arguments:
        input = CreateEmployeeInput(required=True)
        
    def mutate(self,info,input):
        data = utils.input_to_dictionary(input)
        employee = EmployeeModel(**data)

        return CreateEmployee(employee=employee)

class Mutation(graphene.ObjectType):
    createEmplyee = CreateEmployee.Field()  
    
schema = graphene.Schema(query=Query,mutation=Mutation types=[Department, Employee, Role])
