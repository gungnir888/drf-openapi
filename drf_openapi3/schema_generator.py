import warnings
from collections import OrderedDict
from urllib.parse import urlparse

from django.conf import settings
from rest_framework.schemas.openapi import SchemaGenerator


class SortedPathSchemaGenerator(SchemaGenerator):

    def get_servers(self, request=None):
        """
        Get local server together with servers
        defined in "API_SERVERS" Django settings config
        """
        servers = getattr(settings, "API_SERVERS", [])
        if not request and not servers:
            warnings.warn(
                "{}.get_servers() raised an exception during "
                "schema generation. Please add 'API_SERVER' "
                "configuration in Django settings.".format(self.__class__.__name__)
            )
            return None
        for server in servers:
            if not isinstance(server, dict):
                warnings.warn(
                    "{}.get_servers() raised an exception during "
                    "schema generation. Server '{}' not valid".format(self.__class__.__name__, server)
                )
                servers.remove(server)
        return [
            {"url": s["url"], "description": s["description"]}
            for s in servers if "url" in s and "description" in s
        ]

    def get_schema(self, request=None, public=False):
        """
        Overrides SchemaGenerator.get_schema().
        Generate a OpenAPI schema.
        """
        self._initialise_endpoints()

        paths = self.get_paths(None if public else request)
        if not paths:
            return None

        schema = {
            'openapi': '3.0.2',
            'info': self.get_info(),
            "components": {
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                        "description": "Enter your bearer token in the format **Token &lt;token&gt;**",
                    }
                }
            },
            "security": [{"ApiKeyAuth": []}],
            'paths': dict(OrderedDict(sorted(paths.items(), key=lambda t: t[0]))),
            'servers': self.get_servers(request),
        }
        return schema
