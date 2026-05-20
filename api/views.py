from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from api.serializers import MarketInfoSerializer


def health(request):
    return JsonResponse({"status": "ok"})


class MarketInfoView(APIView):
    """Public endpoint — no auth required. Used by marketing site."""
    permission_classes = []

    def get(self, request):
        serializer = MarketInfoSerializer({})
        return Response(serializer.data)
