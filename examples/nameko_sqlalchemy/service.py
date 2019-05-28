#!/usr/bin/env python
from app import App
from nameko.web.handlers import http


class DepartmentService:
    name = 'department'

    @http('POST', '/graphql')
    def query(self, request):
        return App().query(request)
