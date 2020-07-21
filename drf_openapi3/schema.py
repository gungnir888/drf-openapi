from typing import Optional, Dict

import yaml
from django.utils.encoding import smart_str
from django.utils.html import strip_tags
from rest_framework import serializers
from rest_framework.schemas.openapi import AutoSchema
from rest_framework.schemas.utils import is_list_view
from rest_framework.settings import api_settings
from rest_framework.utils import formatting
from yaml.scanner import ScannerError

from .settings import METHOD_STATUS_CODES, STATUS_CODES_RESPONSES, DEFAULT_ERROR_SCHEMA


class AdvanceAutoSchema(AutoSchema):

    @staticmethod
    def _yaml_safe_clean(data: str) -> str:
        """
        Clean before YAML parsing.
        """
        return ''.join(
            c for c in data if c.isprintable
        ).replace("\t", "    ")

    @property
    def tags(self) -> list:
        """
        Get the tags in view.
        """
        return getattr(self.view, 'tags', ['default'])

    @property
    def first_tag(self) -> Optional[str]:
        """
        Get the first tag in view.
        """
        return next((x for x in self.tags), None)

    @property
    def deprecated(self) -> bool:
        """
        Get deprecated in view.
        """
        return getattr(self.view, 'deprecated', False)

    @property
    def handles_many_objects(self) -> bool:
        """
        Handles multiple objects (list and massive post, put, delete)
        """
        return getattr(self.view, "many", False)

    def get_operation(self, path: str, method: str) -> dict:
        """
        Overrides AutoSchema.get_operation()
        Add Tags, Deprecation and YAML docstring to operation dict
        """
        operation = super().get_operation(path, method)
        # Tags, just add attr <tags = ["tag1", "tag2"]> to ApiView
        operation["tags"] = self.tags
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
        if not self.handles_many_objects and method == "DELETE":
            del operation["requestBody"]
        return operation

    def _get_operation_id(self, path: str, method: str) -> str:
        """
        Overrides AutoSchema._get_operation_id()
        Fix same operationId issue for "single" and "list" methods
        """
        method_name = getattr(self.view, 'action', method.lower())
        many = False
        action = self.first_tag
        if is_list_view(path, method, self.view):
            action += 'List'
            many = True
        elif self.handles_many_objects:
            action += f'List{method.title()}'
            many = True
        elif method_name not in self.method_mapping:
            action += method_name.title()
        else:
            action += self.method_mapping[method.lower()].title()
        model = getattr(getattr(self.view, 'queryset', None), 'model', None)
        if getattr(self.view, "operation", None):
            name = self.view.operation
        elif model is not None:
            name = model.__name__
        elif hasattr(self.view, 'get_serializer_class'):
            name = self.view.get_serializer_class().__name__
            if name.endswith('Serializer'):
                name = name[:-10]
        else:
            name = self.view.__class__.__name__
            if name.endswith('APIView'):
                name = name[:-7]
            elif name.endswith('View'):
                name = name[:-4]
            if name.endswith(action.title()):
                name = name[:-len(action)]

        if many is True and not name.endswith('s'):
            name += 's'
        return action + name

    def _map_field(self, field) -> dict:
        """
        Overrides AutoSchema._map_fields()
        Fix on type check on ChoiceField
        :param field: Serializer field
        :return: Field map
        """
        field_map = super()._map_field(field)

        if isinstance(field, serializers.ChoiceField):
            types_map = {
                'str': 'string',
                'bool': 'boolean',
                'int': 'integer',
                'float': 'number',
            }
            types = {types_map[type(x).__name__] for x in field.choices if type(x).__name__ in types_map}
            if len(types) == 1:
                t = {"type": next(iter(types), "string")}
            else:
                t = {"anyOf": [{"type": t} for t in types]}
            t['enum'] = list(field.choices)
            return t
        return field_map

    def _get_request_body(self, path: str, method: str) -> dict:
        """
        Overrides AutoSchema._get_request_body()
        Fixes schema on bulk POST, PUT, DELETE
        :param path: Endpoint path
        :param method: Request method
        :return: OpenApi RequestBody dict
        """
        if method not in ('PUT', 'PATCH', 'POST', 'DELETE'):
            return {}

        self.request_media_types = self.map_parsers(path, method)

        serializer = self._get_serializer(path, method)

        if not isinstance(serializer, serializers.Serializer):
            return {}

        content = self._map_serializer(serializer)
        # No required fields for PATCH
        if method == 'PATCH':
            content.pop('required', None)
        # No read_only fields for request.
        for name, schema in content['properties'].copy().items():
            if 'readOnly' in schema:
                del content['properties'][name]
        # Add "many" check to default is_list_view() check
        if is_list_view(path, method, self.view) or self.handles_many_objects:
            properties = content.pop("properties", None)
            content['type'] = 'array'
            if properties:
                content["items"] = {}
                content['items']['properties'] = properties
        return {
            'content': {
                ct: {'schema': content} if content.get("properties") != {} else {}
                for ct in self.request_media_types
            }
        }

    def _get_responses(self, path: str, method: str) -> dict:
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
                    response_schema = {
                        **paginator.get_paginated_response_schema(response_schema),
                        **response_schema
                    }
        else:
            response_schema = item_schema
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

    def _allows_filters(self, path: str, method: str) -> bool:
        """
        Overrides AutoSchema._allows_filters()
        Exclude filters if "list" methods
        """
        filters_allowed = super()._allows_filters(path, method)
        if method.lower() == "get" or not self.handles_many_objects:
            return filters_allowed
        return False

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
