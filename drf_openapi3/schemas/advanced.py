import warnings
from typing import Dict

import yaml
from django.conf import settings
from django.utils.encoding import smart_str
from django.utils.html import strip_tags
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.utils import formatting
from yaml.scanner import ScannerError

from drf_openapi3.schemas.openapi import AutoSchema, SchemaGenerator
from drf_openapi3.schemas.utils import is_list_view
from drf_openapi3.settings import (
    STATUS_CODES_RESPONSES,
    DEFAULT_ERROR_SCHEMA,
    METHOD_STATUS_CODES
)


class AdvancedSchemaGenerator(SchemaGenerator):

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
        schema = super(AdvancedSchemaGenerator, self).get_schema(
            request=request, public=public
        )
        schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Enter your bearer token in the format **Token &lt;token&gt;**",
            }
        }
        schema["security"] = [{"ApiKeyAuth": []}]
        schema["servers"] = self.get_servers(request=request)
        return schema


class AdvancedAutoSchema(AutoSchema):

    def __init__(self, index=9999, tags=None, operation_id_base=None, component_name=None,
                 handles_many_objects=False, deprecated=False):
        super(AdvancedAutoSchema, self).__init__(
            tags=tags, operation_id_base=operation_id_base,
            component_name=component_name
        )
        self.index = index
        self.handles_many_objects = handles_many_objects
        self.deprecated = deprecated

    @staticmethod
    def _yaml_safe_clean(data: str) -> str:
        """
        Clean before YAML parsing.
        """
        return ''.join(
            c for c in data if c.isprintable
        ).replace("\t", "    ")

    def add_tag(self, tag):
        self._tags.append(tag)

    def remove_tag(self, tag):
        try:
            self._tags.remove(tag)
        except ValueError:
            pass

    def set_tags(self, tags):
        self._tags = tags

    def get_operation(self, path: str, method: str) -> dict:
        """
        Overrides AutoSchema.get_operation()
        Add Tags, Deprecation and YAML docstring to operation dict
        """
        operation = super().get_operation(path, method)
        # Deprecated, add attr <deprecated = True> to ApiView
        if self.deprecated:
            operation["deprecated"] = True
        # Info from Docstring
        info = self.get_docstring(method)
        error_codes = []
        for i in info:
            # It's an int reserved for status codes
            if isinstance(i["key"], int):
                error_codes.append(i)
            # It's a key to be overridden/updated with Docstring key
            elif not i["append"]:
                operation[i["key"]] = i["value"]
            elif isinstance(operation[i["key"]], dict):
                operation[i["key"]].update(i["value"])
            elif isinstance(operation[i["key"]], list):
                operation[i["key"]].append(i["value"])
            else:
                raise NotImplementedError
        # Update responses with error codes from Docstring
        for s in error_codes:
            description = s["value"]["description"] \
                if s["value"].get("description") \
                else STATUS_CODES_RESPONSES[s]['description']
            schema = s["value"]["schema"] if s["value"].get("schema") else DEFAULT_ERROR_SCHEMA
            operation["responses"][str(s["key"])] = self._get_status_code_dict(
                s["key"], schema,
                description
            )[s["key"]]
        return operation

    def get_docstring(self, method: str) -> list:
        """
        Get docstring from method or view class.
        Set <property=True> to append data instead of overwriting it
        """
        method_name = getattr(self.view, "action", method.lower())
        method_docstring = getattr(self.view, method_name, None).__doc__
        if method_docstring:
            # An explicit docstring on the method or action.
            return self._get_yaml_docstring(
                method.lower(), smart_str(method_docstring),
                tags=True,
                responses=True
            )
        else:
            # ... the class docstring.
            class_docstring = self.view.get_view_description()
            # ... empty docstring, let's try in parent class.
            if not class_docstring:
                super_class = self.view.__class__.__bases__[0]()
                class_docstring = strip_tags(super_class.get_view_description(self.view))
            return self._get_yaml_docstring(
                method.lower(),
                class_docstring,
                tags=True,
                responses=True
            )

    def _get_yaml_docstring(self, method: str, docstring: str, **many: Dict[str, bool]) -> list:
        """
        Parse Docstring formatted in YAML notation
        :param method: View method
        :param docstring: The Docstring from method or from class
        :param many: Pass <property=True> to append/update existing data, else overwrite
        :return: List of properties from YAML-formatted Docstring
        """
        method = "get" if method == "list" else method
        # Invalid properties will be ignored
        valid_properties = (
            "summary", "description", "tags", "responses",
            200, 201, 202, 204, 400, 401, 403, 404, 500, 502, 503
        )
        # Create valid properties many dict (False: overwrite, True: append/update)
        for valid_property in valid_properties:
            many.setdefault(valid_property, False)
        # Same checks got from .get_descriptions()
        coerce_method_names = api_settings.SCHEMA_COERCE_METHOD_NAMES
        if method in coerce_method_names:
            method = coerce_method_names[method]
        docstring_for_yaml = self._yaml_safe_clean(docstring)
        try:
            # Load YAML
            yml = yaml.load(docstring_for_yaml, Loader=yaml.SafeLoader)
        except ScannerError:
            # Invalid YAML, let's store the string in description key
            return [{
                "key": "description",
                "value": "" + "\n".join(
                    line.strip() for line in formatting.dedent(docstring).splitlines()
                ),
                "append": many["description"]
            }]
        result = yml
        # None YAML, let's return and empty description
        if yml is None:
            return [{"key": "description", "value": "", "append": many["description"]}]
        # Method doesn't exist in yml
        if method not in yml:
            result = {method: yml}
        # Method property value is str
        if isinstance(result[method], str):
            result = {method: {"description": result[method]}}
        # Return valid property
        return [
            {"key": k, "value": v.strip() if isinstance(v, str) else v, "append": many[k]}
            for k, v in result[method].items()
            if k in valid_properties
        ]

    def _get_status_code_dict(self, status_code: int, schema: dict, description: str) -> dict:
        """
        Creates the response
        :param status_code: Status code
        :param schema: Schema
        :param description: status_code description
        :return:
        """
        content = self._get_media_types_content(schema)
        return {
            status_code: {
                "content": content,
                "description": description
            }
        }

    def get_responses(self, path: str, method: str) -> dict:
        """
        Overrides AutoSchema._get_responses()
        :param path: Endpoint path
        :param method: Request method
        :return: OpenApi responses dict
        """
        self.response_media_types = self.map_renderers(path, method)

        item_schema = {}
        serializer = self._get_serializer(path, method)

        if isinstance(serializer, serializers.Serializer):
            item_schema = self._map_serializer(serializer)
            # No write_only fields for response.
            for name, schema in item_schema['properties'].copy().items():
                if 'writeOnly' in schema:
                    del item_schema['properties'][name]
                    if 'required' in item_schema:
                        item_schema['required'] = [f for f in item_schema['required'] if f != name]

        if self.handles_many_objects:
            response_schema = {
                'type': 'array',
                'items': item_schema,
            }
            if is_list_view(path, method, self.view):
                paginator = self._get_paginator()
                if paginator:
                    response_schema = paginator.get_paginated_response_schema(response_schema)
        else:
            response_schema = item_schema
        if getattr(settings, 'STATIC_ERROR_CODES', False) is False:
            return {
                '200': {
                    'content': {
                        ct: {'schema': response_schema}
                        for ct in self.response_media_types
                    },
                    # description is a mandatory property,
                    # https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md#responseObject
                    # TODO: put something meaningful into it
                    'description': ""
                }
            }
        allowed_reponses = self._get_allowed_responses(method, response_schema)
        return allowed_reponses

    def _get_allowed_responses(self, method: str, schema: dict) -> dict:
        """
        Returns the OpenApi responses based on settings
        :param method: Request method
        :param schema: Schema for successful requests, else default error schema is used
        :return: OpenApi responses dict based on settings
        """
        allowed_responses = {}
        obj_num = 'one'
        if self.handles_many_objects:
            obj_num = 'many'
        if getattr(self.view, 'allowed_status_codes', None):
            allowed_status_codes = [
                x for x in METHOD_STATUS_CODES[method][obj_num]["status_codes"] if x in self.view.allowed_status_codes
            ]
            allowed_error_codes = [
                x for x in METHOD_STATUS_CODES[method][obj_num]["error_codes"] if x in self.view.allowed_status_codes
            ]
        else:
            allowed_status_codes = METHOD_STATUS_CODES[method][obj_num]["status_codes"]
            allowed_error_codes = METHOD_STATUS_CODES[method][obj_num]["error_codes"]
        for s in allowed_status_codes:
            allowed_responses[str(s)] = self._get_status_code_dict(
                s, schema, STATUS_CODES_RESPONSES[s]['description']
            )[s]
        for s in allowed_error_codes:
            allowed_responses[str(s)] = self._get_status_code_dict(
                s, DEFAULT_ERROR_SCHEMA, STATUS_CODES_RESPONSES[s]['description']
            )[s]
        return allowed_responses

    def _get_media_types_content(self, schema: dict) -> dict:
        """
        Replicates schema for each supported content-type
        :param schema: Schema to replicate
        :return: OpenApi responses content
        """
        return {
            ct: {'schema': schema if schema.get("properties") != {} else {}}
            for ct in self.response_media_types
        }