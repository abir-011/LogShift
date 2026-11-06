from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


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


def dashboard_home(request):
    return render(request, "dashboard/dashboard.html")