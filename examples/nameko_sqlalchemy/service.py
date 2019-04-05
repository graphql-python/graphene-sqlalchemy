#!/usr/bin/env python
from nameko.web.handlers import http

from .app import App


class DepartmentService:
    name = 'department'

    @http('POST', '/graphql')
    def query(self, request):
        return App().query(request)
