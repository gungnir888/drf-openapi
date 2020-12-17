from rest_framework.views import APIView
from drf_openapi3.schemas.advanced import AdvancedAutoSchema


class AdvanceApiView(APIView):
    schema = AdvancedAutoSchema()
