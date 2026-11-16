from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from logs.authentication import MonitoringAPIKeyAuthentication
from logs.permissions import can_manage_logs
from .serializers import InfrastructureMetricSerializer
from .models import InfrastructureMetric
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

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

@login_required
def infrastructure_home(request):
    return render(request, "dashboard/infrastructure.html")


@login_required
def log_management_home(request):
    if not can_manage_logs(request.user):
        raise PermissionDenied

    return render(request, "dashboard/log_management.html")

class InfrastructureMetricIngestView(APIView):
    permission_classes = [AllowAny]

    def get_authenticators(self):
        if self.request.method == "POST":
            return [MonitoringAPIKeyAuthentication()]

        return [SessionAuthentication()]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]

        return [AllowAny()]

    def get(self, request):
        metrics = InfrastructureMetric.objects.order_by(
            "-collected_at"
        )[:100]

        history = list(
            metrics.values(
                "disk_total_bytes",
                "disk_used_bytes",
                "disk_available_bytes",
                "disk_usage_percent",
                "collected_at",
            )
        )

        latest = history[0] if history else None

        return Response({
            "latest": latest,
            "history": history,
        })

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
