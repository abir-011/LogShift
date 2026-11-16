from datetime import datetime, time, timedelta, timezone as datetime_timezone

from django.core import signing
from django.db import DatabaseError, connection, transaction
from django.db.models import Count, Max, Min
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LogDeletionAudit, LogEvent
from .permissions import CanManageLogs
from .serializers import LogDeletionFilterSerializer, LogDeletionRequestSerializer


PREVIEW_TOKEN_SALT = "logs.log-deletion-preview"
PREVIEW_TOKEN_MAX_AGE_SECONDS = 300


def normalise_deletion_filters(validated_filters):
    """Produce a JSON-safe, stable representation for a deletion filter set."""

    filters = {}

    if start_time := validated_filters.get("start_time"):
        filters["start_time"] = start_time.isoformat()

    if end_time := validated_filters.get("end_time"):
        filters["end_time"] = end_time.isoformat()

    if service_name := validated_filters.get("service_name"):
        filters["service_name"] = service_name

    if level := validated_filters.get("level"):
        filters["level"] = level

    if environment := validated_filters.get("environment"):
        filters["environment"] = environment

    return filters


def build_log_deletion_queryset(filters, high_water_id=None):
    """Apply the single authoritative filter implementation for preview/delete."""

    logs = LogEvent.objects.all()

    if start_time := filters.get("start_time"):
        logs = logs.filter(timestamp__gte=datetime.fromisoformat(start_time))

    if end_time := filters.get("end_time"):
        logs = logs.filter(timestamp__lt=datetime.fromisoformat(end_time))

    if service_name := filters.get("service_name"):
        logs = logs.filter(service_name=service_name)

    if level := filters.get("level"):
        logs = logs.filter(level=level)

    if environment := filters.get("environment"):
        logs = logs.filter(environment=environment)

    if high_water_id is not None:
        logs = logs.filter(id__lte=high_water_id)

    return logs



def get_database_size_bytes():
    """Return total PostgreSQL database size, or None when unavailable."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            row = cursor.fetchone()

        return row[0] if row else None
    except DatabaseError:
        return None

def get_log_storage_size_bytes():
    """Return total log_events table size, including indexes."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_total_relation_size('log_events'::regclass)"
            )
            row = cursor.fetchone()

        return row[0] if row else None
    except DatabaseError:
        return None

def create_preview_token(user, filters, count, high_water_id):
    payload = {
        "user_id": user.pk,
        "filters": filters,
        "count": count,
        "high_water_id": high_water_id,
    }
    return signing.dumps(payload, salt=PREVIEW_TOKEN_SALT, compress=True)


def load_preview_token(token):
    try:
        payload = signing.loads(
            token,
            salt=PREVIEW_TOKEN_SALT,
            max_age=PREVIEW_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as error:
        raise ValidationError({"preview_token": "Preview token has expired."}) from error
    except signing.BadSignature as error:
        raise ValidationError({"preview_token": "Preview token is invalid."}) from error

    required_fields = {"user_id", "filters", "count", "high_water_id"}

    if not isinstance(payload, dict) or not required_fields.issubset(payload):
        raise ValidationError({"preview_token": "Preview token is invalid."})

    return payload


class AdminLogSummaryView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanManageLogs]

    def get(self, request):
        aggregates = LogEvent.objects.aggregate(
            total_logs=Count("id"),
            oldest_log=Min("timestamp"),
            newest_log=Max("timestamp"),
        )
        database_size_bytes = get_database_size_bytes()
        log_storage_size_bytes = get_log_storage_size_bytes()

        return Response({
            "total_logs": aggregates["total_logs"],
            "oldest_log": aggregates["oldest_log"],
            "newest_log": aggregates["newest_log"],
            "database_size_bytes": database_size_bytes,
            "database_size_available": database_size_bytes is not None,
            "log_storage_size_bytes": log_storage_size_bytes,
            "log_storage_size_available": log_storage_size_bytes is not None,
        })

class LogDeletionPreviewView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanManageLogs]

    def get(self, request):
        serializer = LogDeletionFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = normalise_deletion_filters(serializer.validated_data)
        high_water_id = LogEvent.objects.aggregate(max_id=Max("id"))["max_id"] or 0
        count = build_log_deletion_queryset(filters, high_water_id).count()
        expires_at = timezone.now() + timedelta(seconds=PREVIEW_TOKEN_MAX_AGE_SECONDS)

        return Response({
            "filters": filters,
            "count": count,
            "preview_token": create_preview_token(
                request.user,
                filters,
                count,
                high_water_id,
            ),
            "expires_at": expires_at,
        })


class LogDeletionView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanManageLogs]

    def post(self, request):
        serializer = LogDeletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preview = load_preview_token(serializer.validated_data["preview_token"])

        filters = preview["filters"]
        preview_count = preview["count"]
        high_water_id = preview["high_water_id"]

        if (
            not isinstance(filters, dict)
            or type(preview_count) is not int
            or preview_count < 0
            or type(high_water_id) is not int
            or high_water_id < 0
            or type(preview["user_id"]) is not int
        ):
            raise ValidationError({"preview_token": "Preview token is invalid."})

        filter_serializer = LogDeletionFilterSerializer(data=filters)
        filter_serializer.is_valid(raise_exception=True)

        if normalise_deletion_filters(filter_serializer.validated_data) != filters:
            raise ValidationError({"preview_token": "Preview token is invalid."})

        if preview_count == 0:
            raise ValidationError({
                "preview_token": "No matching logs are available for deletion."
            })

        if preview["user_id"] != request.user.pk:
            raise PermissionDenied(
                "Preview tokens may only be used by the user who created them."
            )

        try:
            with transaction.atomic():
                logs = build_log_deletion_queryset(filters, high_water_id)
                log_ids = list(
                    logs.select_for_update().values_list("id", flat=True)
                )

                if len(log_ids) != preview_count:
                    return Response(
                        {
                            "detail": (
                                "Matching logs changed after preview. "
                                "Create a new preview before deleting."
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                LogEvent.objects.filter(id__in=log_ids).delete()
                audit = LogDeletionAudit.objects.create(
                    actor=request.user,
                    actor_username=request.user.get_username(),
                    filters=filters,
                    preview_count=preview_count,
                    deleted_count=len(log_ids),
                    source=LogDeletionAudit.SOURCE_MANUAL,
                )
        except DatabaseError:
            return Response(
                {"detail": "Log deletion could not be completed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "message": "Logs deleted successfully.",
            "deleted_count": audit.deleted_count,
            "audit_id": audit.pk,
        })


class LogDeletionHistoryView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanManageLogs]

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = 10

            if page < 1:
                raise ValueError

        except (TypeError, ValueError):
            raise ValidationError({"page": "Page must be a positive integer."})

        audits = LogDeletionAudit.objects.all()
        total_count = audits.count()

        start = (page - 1) * page_size
        end = start + page_size

        history = [
            {
                "actor_username": audit.actor_username,
                "performed_at": audit.performed_at,
                "deleted_count": audit.deleted_count,
                "preview_count": audit.preview_count,
                "filters": audit.filters,
                "source": audit.source,
            }
            for audit in audits[start:end]
        ]

        return Response({
            "results": history,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
        })
