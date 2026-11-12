from urllib import request

from django.contrib.postgres import search
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError
from django.db import transaction
from rest_framework import serializers
from .models import LogEvent
from django.db.models import Count
from django.db.models.functions import TruncHour
from django.utils import timezone
from datetime import timedelta
from .serializers import LogEventSerializer
from rest_framework.pagination import PageNumberPagination


class LogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class LogIngestView(APIView):

    def post(self, request):
        serializer = LogEventSerializer(data=request.data)

        if serializer.is_valid():
            try:
                log_event = serializer.save()

                return Response(
                    {
                        "message": "Log event ingested successfully.",
                        "event_id": log_event.event_id,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except IntegrityError:
                return Response(
                    {"error": "Duplicate event_id."},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        logs = LogEvent.objects.all()

        service_name = request.query_params.get("service_name")
        level = request.query_params.get("level")
        environment = request.query_params.get("environment")
        search = request.query_params.get("search")
        start_time = request.query_params.get("start_time")
        end_time = request.query_params.get("end_time")

        if service_name:
            logs = logs.filter(service_name=service_name)

        if level:
            logs = logs.filter(level=level.upper())

        if environment:
            logs = logs.filter(environment=environment)

        if search:
            logs = logs.filter(message__icontains=search)

        if start_time:
            logs = logs.filter(timestamp__gte=start_time)

        if end_time:
            logs = logs.filter(timestamp__lte=end_time)

        paginator = LogPagination()
        page = paginator.paginate_queryset(logs, request)

        serializer = LogEventSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class BatchLogIngestView(APIView):

    def post(self, request):
        logs = request.data.get("logs")

        if not isinstance(logs, list) or not logs:
            return Response(
                {"error": "'logs' must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LogEventSerializer(data=logs, many=True)

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                events = serializer.save()

            return Response(
                {
                    "message": "Batch ingested successfully.",
                    "count": len(events),
                    "event_ids": [event.event_id for event in events],
                },
                status=status.HTTP_201_CREATED,
            )

        except IntegrityError:
            return Response(
                {"error": "One or more event IDs already exist."},
                status=status.HTTP_409_CONFLICT,
            )


class LogDetailView(APIView):

    def get(self, request, event_id):
        try:
            log = LogEvent.objects.get(event_id=event_id)

        except LogEvent.DoesNotExist:
            return Response(
                {"error": "Log event not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = LogEventSerializer(log)

        return Response(serializer.data)


class LogStatsView(APIView):

    def get(self, request):
        now = timezone.now()

        time_range = request.query_params.get("time_range", "24h")
        level = request.query_params.get("level")
        service = request.query_params.get("service")
        environment = request.query_params.get("environment")

        time_ranges = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
        }

        if time_range not in time_ranges:
            return Response(
                {"error": "Invalid time_range. Use 1h, 24h, or 7d."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_time = now - time_ranges[time_range]

        logs = LogEvent.objects.filter(
            timestamp__gte=start_time,
            timestamp__lte=now,
        )

        if level:
            logs = logs.filter(level=level.upper())

        if service:
            logs = logs.filter(service_name=service)

        if environment:
            logs = logs.filter(environment=environment)

        logs_over_time = (
            logs
            .annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        hourly_counts = {
            item["hour"].replace(minute=0, second=0, microsecond=0): item["count"]
            for item in logs_over_time
        }

        first_hour = start_time.replace(
            minute=0, second=0, microsecond=0
        )

        logs_over_time = [
            {
                "hour": (first_hour + timedelta(hours=i)).isoformat(),
                "count": hourly_counts.get(
                    first_hour + timedelta(hours=i), 0
                ),
            }
            for i in range(int(time_ranges[time_range].total_seconds() // 3600) + 1)
        ]

        total_logs = logs.count()

        error_count = logs.filter(level="ERROR").count()
        warning_count = logs.filter(level="WARNING").count()

        logs_by_level = (
            logs
            .values("level")
            .annotate(count=Count("id"))
            .order_by("level")
        )

        logs_by_service = (
            logs
            .values("service_name")
            .annotate(count=Count("id"))
            .order_by("service_name")
        )

        return Response({
            "total_logs": total_logs,
            "error_count": error_count,
            "warning_count": warning_count,
            "logs_by_level": list(logs_by_level),
            "logs_by_service": list(logs_by_service),
            "logs_over_time": logs_over_time,
        })


class ServiceListView(APIView):

    def get(self, request):
        services = (
            LogEvent.objects
            .values_list("service_name", flat=True)
            .distinct()
            .order_by("service_name")
        )

        return Response({"services": list(services)})