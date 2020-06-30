from rest_framework.views import APIView
from ..schema import AdvanceAutoSchema


class AdvanceApiView(APIView):
    schema = AdvanceAutoSchema()
