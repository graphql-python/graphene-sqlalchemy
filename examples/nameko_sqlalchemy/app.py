from database import db_session, init_db
from schema import schema

from graphql_server import (HttpQueryError, default_format_error,
                            encode_execution_results, json_encode,load_json_body, run_http_query)


class App():
  def __init__(self):
    init_db()

  def query(self, request):
      data  = self.parse_body(request)
      execution_results, params = run_http_query(
              schema,
              'post',
              data)
      result, status_code = encode_execution_results(
              execution_results,
              format_error=default_format_error,is_batch=False, encode=json_encode)
      return result
  
  def parse_body(self,request):
      # We use mimetype here since we don't need the other
      # information provided by content_type
      content_type = request.mimetype
      if content_type == 'application/graphql':
          return {'query': request.data.decode('utf8')}

      elif content_type == 'application/json':
          return load_json_body(request.data.decode('utf8'))

      elif content_type in ('application/x-www-form-urlencoded', 'multipart/form-data'):
          return request.form

      return {}
