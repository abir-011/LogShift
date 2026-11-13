from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Count, Q
from .models import LogEvent
from django.db.models.functions import TruncHour
from django.utils import timezone
from datetime import timedelta
from .serializers import LogEventSerializer, LogQuerySerializer
from rest_framework.pagination import PageNumberPagination


class LogPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "page_size": self.get_page_size(self.request),
            "results": data,
        })


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

        query_serializer = LogQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        if service_name := params.get("service_name"):
            logs = logs.filter(service_name=service_name)

        if level := params.get("level"):
            logs = logs.filter(level=level)

        if environment := params.get("environment"):
            logs = logs.filter(environment=environment)

        if search := params.get("search"):
            logs = logs.filter(
                Q(message__icontains=search)
                | Q(event_id__icontains=search)
                | Q(service_name__icontains=search)
                | Q(event_type__icontains=search)
                | Q(operation__icontains=search)
                | Q(message_template__icontains=search)
                | Q(correlation__trace_id__icontains=search)
                | Q(correlation__request_id__icontains=search)
                | Q(correlation__span_id__icontains=search)
                | Q(correlation__parent_span_id__icontains=search)
            )

        if start_time := params.get("start_time"):
            logs = logs.filter(timestamp__gte=start_time)

        if end_time := params.get("end_time"):
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
