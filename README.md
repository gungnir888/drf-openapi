# DRF OpenApi 3
## OpenApi 3 utility for Django REST Framework

Enhances DRF AutoSchema and SchemaGenerator to help generating a better OpenApi 3 documentation.

Supports servers, deprecated, tags and summary in schema generation, 
now you can tag ApiViews, mark them as deprecated and display the summary besides the description.
If you want your ApiView to display custom content in the documentation, 
you can add it by writing comments to the view/view method in YAML format. 
Fixed request body and responses for views that handle multiple objects, 
such as bulk insert, bulk update and bulk delete. Now they are displayed as array.

### Installation

1. Install the package using `pip install drf_openapi3`
2. Add `drf_openapi3.apps.OpenApi3Config` to Django `INSTALLED_APPS`

### Configuration

1. OpenApi documentation View

Extend `drf_openapi3.views.OpenApiTemplateView`. You can define a title and template name, otherwise default values will be used.

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from drf_openapi3.views import OpenApiTemplateView


class MyOpenApiTemplateView(LoginRequiredMixin, OpenApiTemplateView):
    title = 'My OpenAPI'
    template_name = 'path/to/mytemplate.html'
```

2. Add schema to urlpatterns using `drf_openapi3.SortedPathSchemaGenerator` as generator class

```python
from django.contrib.auth.decorators import login_required
from django.urls import path
from drf_openapi3.schema_generator import SortedPathSchemaGenerator
from rest_framework.schemas import get_schema_view


urlpatterns = [
    # Use the `get_schema_view()` helper to add a `SchemaView` to project URLs.
    #   * `title` and `description` parameters are passed to `SchemaGenerator`.
    #   * Provide view name for use with `reverse()`.
    path('my-schema/', login_required(
        get_schema_view(
            title='My API',
            description='My API description',
            version='1.0.0',
            generator_class=SortedPathSchemaGenerator,
            public=True,
        ),
        login_url='/accounts/login/',
    ), name='my_schema_name'),
    # ...
    # ...
]
```

3. Start documenting your ApiViews.

Your views must extend `drf_openapi3.views.AdvanceApiView`.

```python
from drf_openapi3.views import AdvanceApiView
from rest_framework.generics import ListAPIView


class MyAPIListView(ListAPIView, AdvanceApiView):
    allowed_methods = ['get']

    def get(self, request, *args, **kwargs):
        return super(MyAPIListView, self).list(request, *args, **kwargs)
```

### How to use

Let's see step by step what you can do.

#### Define multiple servers

Useful for instance if you provide a test sandbox together with a production server.
In Django settings you can define url and description in `API_SERVERS`:

```python
API_SERVERS = [
    {
        "url": "https://test.example.com/",
        "description": "Sandbox server (uses test data)",
    },
    {
        "url": "https://example.com/",
        "description": "Production server (uses live data)",
    },
]
```

If you don't define anything, Django `BASE_URL` will be used to build your server block.
So if you are developing in local environment, the server `url` will be `http://localhost:8000`.
If it's production environment, the server `url` will be `https://example.com`.
Keep in mind that defining multiple servers in `API_SERVERS` will allow users to switch server urls in the dropdown on the documentation before testing your endpoints.

#### Apply tags to your ApiView

If you want to tag your view, just add the attribute `tags` to it.
You can decide your own, it can come in handy to add the endpoint version:

```python
from drf_openapi3.views import AdvanceApiView
from rest_framework.generics import ListAPIView


class MyAPIListView(ListAPIView, AdvanceApiView):
    # ...
    # ...
    allowed_methods = ['get']
    tags = ["v2"]

    def get(self, request, *args, **kwargs):
        return super(MyAPIListView, self).list(request, *args, **kwargs)
```

#### Apply deprecated to your old ApiView

If you want to mark your view as deprecated, just add the attribute `deprecated = True` to it:

```python
from drf_openapi3.views import AdvanceApiView
from rest_framework.generics import ListAPIView


class MyAPIListView(ListAPIView, AdvanceApiView):
    # ...
    # ...
    allowed_methods = ['get']
    tags = ["v0"]
    deprecated = True

    def get(self, request, *args, **kwargs):
        return super(MyAPIListView, self).list(request, *args, **kwargs)
```

#### Views that handle multiple objects with methods besides GET

When you write a view that performs bulk create, update or delete operations you face some issues on the documentation:

both the `requestBody` and the `responses` field schema types are `object`, but they should be `array`.

By adding `many = True` attribute to your view, you tell the schema that `requestBody` and `responses` must be arrays.

```python
from rest_framework.generics import ListCreateAPIView
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK
from drf_openapi3 import AdvanceApiView


class MyListPostView(ListCreateAPIView, AdvanceApiView):
    # ...
    # ...
    allowed_methods = ['get', 'post']
    many = True

    def post(self, request, *args, **kwargs) -> Response:
        serialized = self.get_serializer(data=request.data, many=True)
        if serialized.is_valid():
            serialized.save()
            return Response(serialized.data, status=HTTP_200_OK)
        return Response(serialized.errors, status=HTTP_400_BAD_REQUEST)
```

#### Display custom content in the documentation

DRF AutoSchema already reads your view/view method Docstring:

if you want to display the endpoint `description` in your documentation, 
you can write some text in the view/view method Docstring. 

That wasn't enough for me though.

Let's start with the simplest one, the same one that's already implemented from DRF AutoSchema that it has been kept to have backwards compatibility:

we add a plain description in the view Docstring. If we do it on both view and method view, only method view Docstring will be taken into account:

```python
from rest_framework.generics import ListCreateAPIView
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_200_OK
from drf_openapi3 import AdvanceApiView


class MyListPostView(ListCreateAPIView, AdvanceApiView):
    """
    This is my endpoint description and it will be reported 
    for each allowed method.
    """
    # ...
    # ...
    allowed_methods = ['get', 'post']
    many = True

    def post(self, request, *args, **kwargs) -> Response:
        """
        ... and that's my method description
        Since both the descriptions are defined you'll see only this one.
        You won't see "This is my endpoint description", 
        unless you delete the text here above.
        """
        serialized = self.get_serializer(data=request.data, many=True)
        if serialized.is_valid():
            serialized.save()
            return Response(serialized.data, status=HTTP_200_OK)
        return Response(serialized.errors, status=HTTP_400_BAD_REQUEST)
```

If you want to manage custom changes to your schema, just add them to the Docstring in YAML format.
You'll notice that it'll be easier for you to read your code too.

By default DRF AutoSchema displays only status code 200 as example response.
Since 400, 401, 403, 404 status codes return a JSON `{"detail": <error detail>}`, 
in Django settings you can define `STATIC_ERROR_CODES = True` to display more responses in your documentation.
If you have to perform further changes on responses in your view, you can put them in YAML view/view method Docstring.

If you want to limit the allowed response codes that you're going to see on the documentation, 
just list the allowed status codes in your view (`allowed_status_codes`); this is useful when you had enabled 
`STATIC_ERROR_CODES` and you want to prevent some responses to be displayed.

We're getting creative here, let's add a complete example:

```python
class MyCommentedView(ListAPIView, CreateAPIView, UpdateAPIView, DestroyAPIView, AdvanceApiView):
    """
        get:
            summary: Summary for get method
            description: Description for get method
        post:
            summary: Summary for post method
            description: Description for post method
            400:
                description: Invalid object, that's a custom description of 400 response code for post method
        put:
            summary: Summary for put method
            description: Description for put method
        delete:
            summary: Summary for delete method
            description: Description for delete method
            200:
                description: Corsa objects deleted, that's a custom description of 200 response code for delete method
                schema:
                    type: array
                    items:
                        properties:
                            field:
                                type: boolean
                                description: Deleted flag, here we define a different schema for bulk delete
    """
    allowed_methods = ("GET", "POST", "PUT", "DELETE")
    allowed_status_codes = (200, 400, 401, 403)

    tags = ["v0"]
    many = True

# ...
# ...
```

If you've overridden the view methods already (`.get()`, `.post()`, `.put()`, `.delete()`) you can write there your comments.
Please be advised that if you do so you must not use the notation `method: properties`:

```python
# ...
# ...

    def delete(self, request, *args, **kwargs) -> Response:
        """
        summary: Summary for delete method
        description: Description for delete method
        200:
            description: Corsa objects deleted, that's a custom description of 200 response code for delete method
            schema:
                type: array
                items:
                    properties:
                        field:
                            type: boolean
                            description: Deleted flag, here we define a different schema for bulk delete
        """
        output = []
        for data in request.data:
        # ...
        # ...
        return Response(output, status=HTTP_200_OK)
```