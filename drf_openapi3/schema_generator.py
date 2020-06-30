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
        local_url = "{uri.scheme}://{uri.netloc}/".format(uri=urlparse(request.build_absolute_uri()))
        url_already_set = bool(next((s for s in servers if s["url"] == local_url), None))
        if not url_already_set:
            servers = [*[{"url": local_url, "description": "Local server"}], *servers]
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
                    }
                }
            },
            "security": [{"ApiKeyAuth": []}],
            'paths': dict(OrderedDict(sorted(paths.items(), key=lambda t: t[0]))),
            'servers': self.get_servers(request),
        }
        return schema
