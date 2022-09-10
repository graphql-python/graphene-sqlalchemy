# coding=utf-8

import os
from os import devnull
import logging
import functools
from collections import OrderedDict
from contextlib import redirect_stdout
import json

import graphene
import falcon


def set_graphql_allow_header(
    req: falcon.Request,
    resp: falcon.Response,
    resource: object,
):
    """Sets the 'Allow' header on responses to GraphQL requests.

    Args:
        req (falcon.Request): The incoming request.
        resp (falcon.Response): The outgoing response.
        resource (object): The falcon resource-class associated with the
            incoming request.
    """

    # Set the `Allow` header to permit given commands.
    resp.set_header('Allow', 'GET, POST, OPTIONS')


@falcon.after(set_graphql_allow_header)
class ResourceGraphQl:
    """Main GraphQL server. Integrates with the predefined Graphene schema."""

    def __init__(
        self,
        schema: graphene.Schema,
    ):

        # Internalize arguments.
        self.schema = schema

        self._respond_invalid_method = functools.partial(
            self._respond_error,
            status=falcon.HTTP_405,
            message="GraphQL only supports GET and POST requests.",
        )

        self._respond_no_query = functools.partial(
            self._respond_error,
            status=falcon.HTTP_400,
            message="Must provide query string.",
        )

        self._respond_invalid_variables = functools.partial(
            self._respond_error,
            status=falcon.HTTP_400,
            message="Variables are invalid JSON.",
        )

        self._respond_invalid_body = functools.partial(
            self._respond_error,
            status=falcon.HTTP_400,
            message="POST body sent invalid JSON.",
        )

    def _execute_query(
        self,
        query,
        variable_values,
        operation_name=None,
    ):

        result = self.schema.execute(
            query,
            variable_values=variable_values,
            operation_name=operation_name
        )

        return result

    @staticmethod
    def _respond_error(
        resp: falcon.Response,
        status: str,
        message: str,
    ):

        resp.status = status
        resp.body = json.dumps(
            {"errors": [{"message": message}]},
            separators=(',', ':')
        )

    def on_options(self, req, resp):
        """Handles OPTIONS requests."""

        resp.status = falcon.HTTP_204
        pass

    def on_head(self, req, resp):
        """Handles HEAD requests. No content."""

        pass

    def on_get(self, req, resp):
        """Handles GraphQL GET requests."""

        if req.params and 'query' in req.params and req.params['query']:
            query = str(req.params['query'])
        else:
            # this means that there aren't any query params in the url
            return self._respond_no_query(resp=resp)

        if 'variables' in req.params and req.params['variables']:
            try:
                variables = json.loads(str(req.params['variables']),
                                       object_pairs_hook=OrderedDict)
            except json.decoder.JSONDecodeError:
                return self._respond_invalid_variables(resp=resp)
        else:
            variables = ""

        if 'operationName' in req.params and req.params['operationName']:
            operation_name = str(req.params['operationName'])
        else:
            operation_name = None

        # redirect stdout of schema.execute to /dev/null
        with open(devnull, 'w') as f:
            with redirect_stdout(f):
                # run the query
                result = self._execute_query(
                    query=query,
                    variable_values=variables,
                    operation_name=operation_name
                )

        # construct the response and return the result
        if result.data:
            data_ret = {'data': result.data}
            resp.status = falcon.HTTP_200
            resp.body = json.dumps(data_ret, separators=(',', ':'))
            return
        elif result.errors:
            # NOTE: these errors don't include the optional 'locations' key
            err_msgs = [{'message': str(i)} for i in result.errors]
            resp.status = falcon.HTTP_400
            resp.body = json.dumps({'errors': err_msgs}, separators=(',', ':'))
            return
        else:
            # responses should always have either data or errors
            raise RuntimeError

    def on_post(self, req, resp):
        """Handles GraphQL POST requests."""

        # parse url parameters in the request first
        if req.params and 'query' in req.params and req.params['query']:
            query = str(req.params['query'])
        else:
            query = None

        if 'variables' in req.params and req.params['variables']:
            try:
                variables = json.loads(str(req.params['variables']),
                                       object_pairs_hook=OrderedDict)
            except json.decoder.JSONDecodeError:
                return self._respond_invalid_variables(resp=resp)
        else:
            variables = None

        if 'operationName' in req.params and req.params['operationName']:
            operation_name = str(req.params['operationName'])
        else:
            operation_name = None

        # Next, handle 'content-type: application/json' requests
        if req.content_type and 'application/json' in req.content_type:
            # error for requests with no content
            if req.content_length in (None, 0):
                return self._respond_invalid_body(resp=resp)

            # read and decode request body
            raw_json = req.stream.read()
            try:
                req.context['post_data'] = json.loads(
                    raw_json.decode('utf-8'),
                    object_pairs_hook=OrderedDict
                )
            except json.decoder.JSONDecodeError:
                return self._respond_invalid_body(resp=resp)

            # build the query string (Graph Query Language string)
            if (
                query is None and req.context['post_data'] and
                'query' in req.context['post_data']
            ):
                query = str(req.context['post_data']['query'])
            elif query is None:
                return self._respond_no_query(resp=resp)

            # build the variables string (JSON string of key/value pairs)
            if (
                variables is None and
                req.context['post_data'] and
                'variables' in req.context['post_data'] and
                req.context['post_data']['variables']
            ):
                try:
                    variables = req.context['post_data']['variables']
                    if not isinstance(variables, OrderedDict):
                        json_str = str(req.context['post_data']['variables'])
                        variables = json.loads(
                            json_str,
                            object_pairs_hook=OrderedDict
                        )
                except json.decoder.JSONDecodeError:
                    logging.exception(variables)
                    return self._respond_invalid_variables(resp=resp)

            elif variables is None:
                variables = ""

            # build the operationName string (matches a query or mutation name)
            if (
                operation_name is None and
                'operationName' in req.context['post_data'] and
                req.context['post_data']['operationName']
            ):
                operation_name = str(req.context['post_data']['operationName'])

        # Alternately, handle 'content-type: application/graphql' requests
        elif req.content_type and 'application/graphql' in req.content_type:
            # read and decode request body
            req.context['post_data'] = req.stream.read().decode('utf-8')

            # build the query string
            if query is None and req.context['post_data']:
                query = str(req.context['post_data'])

            elif query is None:
                return self._respond_no_query(resp=resp)

        # Skip application/x-www-form-urlencoded since they are automatically
        # included by setting req_options.auto_parse_form_urlencoded = True

        elif query is None:
            # this means that the content-type is wrong and there aren't any
            # query params in the url
            return self._respond_no_query(resp=resp)

        # redirect stdout of schema.execute to /dev/null
        with open(devnull, 'w') as f:
            with redirect_stdout(f):
                # run the query
                result = self._execute_query(
                    query=query,
                    variable_values=variables,
                    operation_name=operation_name
                )

        # construct the response and return the result
        if result.data:
            data_ret = {'data': result.data}
            resp.status = falcon.HTTP_200
            resp.body = json.dumps(data_ret, separators=(',', ':'))
            return
        elif result.errors:
            # NOTE: these errors don't include the optional 'locations' key
            err_msgs = [{'message': str(i)} for i in result.errors]
            resp.status = falcon.HTTP_400
            resp.body = json.dumps({'errors': err_msgs}, separators=(',', ':'))
            return
        else:
            # responses should always have either data or errors
            raise RuntimeError

    def on_put(self, req, resp):
        """Handles PUT requests."""

        self._respond_invalid_method(resp=resp)

    def on_patch(self, req, resp):
        """Handles PATCH requests."""

        self._respond_invalid_method(resp=resp)

    def on_delete(self, req, resp):
        """Handles DELETE requests."""

        self._respond_invalid_method(resp=resp)


@falcon.after(set_graphql_allow_header)
class ResourceGraphQlSqlAlchemy(ResourceGraphQl):
    """Main GraphQL server. Integrates with the predefined Graphene schema."""

    def __init__(
        self,
        schema,
        scoped_session,
    ):
        # Internalize arguments.
        self.scoped_session = scoped_session

        super(ResourceGraphQlSqlAlchemy, self).__init__(schema=schema)

    def _execute_query(
        self,
        query,
        variable_values,
        operation_name=None,
    ):
        msg_fmt = "Executing query: {} with variables".format(query)
        logging.debug(msg_fmt)

        result = self.schema.execute(
            query,
            variable_values=variable_values,
            operation_name=operation_name,
            context_value={"session": self.scoped_session}
        )

        return result


class ResourceGraphiQL(object):
    """Serves GraphiQL dashboard. Meant to be used during development only."""

    def __init__(
        self,
        path_graphiql,
    ):

        self.path_graphiql = path_graphiql

    def on_get(self, req, resp, static_file=None):
        """Handles GraphiQL GET requests."""

        if static_file is None:
            static_file = 'graphiql.html'
            resp.content_type = 'text/html; charset=UTF-8'
        elif static_file == 'graphiql.css':
            resp.content_type = 'text/css; charset=UTF-8'
        else:
            resp.content_type = 'application/javascript; charset=UTF-8'

        resp.status = falcon.HTTP_200
        resp.stream = open(os.path.join(self.path_graphiql, static_file), 'rb')
