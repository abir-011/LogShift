from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from logs.authentication import MonitoringAPIKeyAuthentication
from .serializers import InfrastructureMetricSerializer

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        return JsonResponse({
            "status": "healthy",
            "database": "connected",
        })

    except Exception:
        return JsonResponse(
            {
                "status": "unhealthy",
                "database": "disconnected",
            },
            status=503,
        )


@login_required
def dashboard_home(request):
    return render(request, "dashboard/dashboard.html")

class InfrastructureMetricIngestView(APIView):
    authentication_classes = [MonitoringAPIKeyAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = InfrastructureMetricSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        metric = serializer.save()

        return Response(
            {
                "message": "Infrastructure metric recorded successfully.",
                "collected_at": metric.collected_at,
            },
            status=status.HTTP_201_CREATED,
        )