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
        total_logs = LogEvent.objects.count()

        error_count = LogEvent.objects.filter(level="ERROR").count()
        warning_count = LogEvent.objects.filter(level="WARNING").count()

        logs_by_level = (
            LogEvent.objects
            .values("level")
            .annotate(count=Count("id"))
            .order_by("level")
        )

        logs_by_service = (
            LogEvent.objects
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
        })