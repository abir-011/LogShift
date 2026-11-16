from rest_framework import serializers
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from .models import LogEvent, Service


class TimezoneAwareDateTimeField(serializers.DateTimeField):
    default_error_messages = {
        "timezone": "Timestamp must include a timezone offset or Z suffix.",
    }

    def to_internal_value(self, value):
        if isinstance(value, str):
            parsed_value = parse_datetime(value)

            if parsed_value is not None and timezone.is_naive(parsed_value):
                self.fail("timezone")

        return super().to_internal_value(value)


class LogQuerySerializer(serializers.Serializer):
    service_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        trim_whitespace=True,
    )
    level = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        trim_whitespace=True,
    )
    environment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
        trim_whitespace=True,
    )
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
    )
    start_time = TimezoneAwareDateTimeField(required=False)
    end_time = TimezoneAwareDateTimeField(required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100)

    def validate_level(self, value):
        if not value:
            return value

        level = value.upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

        if level not in allowed_levels:
            raise serializers.ValidationError(
                "Allowed values are DEBUG, INFO, WARNING, ERROR and CRITICAL."
            )

        return level

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if start_time and end_time and start_time > end_time:
            raise serializers.ValidationError(
                "start_time must be earlier than or equal to end_time."
            )

        return attrs


class LogDeletionFilterSerializer(serializers.Serializer):
    start_time = TimezoneAwareDateTimeField(required=False)
    end_time = TimezoneAwareDateTimeField(required=False)

    service_name = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=150,
        trim_whitespace=True,
    )
    level = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=20,
        trim_whitespace=True,
    )
    environment = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=50,
        trim_whitespace=True,
    )

    def to_internal_value(self, data):
        unknown_fields = set(data.keys()) - set(self.fields)

        if unknown_fields:
            raise ValidationError({
                field: "Unknown filter." for field in sorted(unknown_fields)
            })

        return super().to_internal_value(data)

    def validate_level(self, value):
        level = value.upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

        if level not in allowed_levels:
            raise serializers.ValidationError(
                "Allowed values are DEBUG, INFO, WARNING, ERROR and CRITICAL."
            )

        return level

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                "start_time must be earlier than end_time."
            )

        if not attrs:
            raise serializers.ValidationError(
                "At least one deletion filter is required."
            )

        return attrs



class LogDeletionRequestSerializer(serializers.Serializer):
    preview_token = serializers.CharField(allow_blank=False)
    confirmation = serializers.BooleanField()

    def to_internal_value(self, data):
        unknown_fields = set(data.keys()) - set(self.fields)

        if unknown_fields:
            raise ValidationError({
                field: "Unknown field." for field in sorted(unknown_fields)
            })

        return super().to_internal_value(data)

    def validate_confirmation(self, value):
        if not value:
            raise serializers.ValidationError(
                "Explicit confirmation is required before deleting logs."
            )

        return value


class LogEventSerializer(serializers.ModelSerializer):

    event_id = serializers.CharField(max_length=64)

    class Meta:
        model = LogEvent
        fields = "__all__"
        read_only_fields = ("id", "observed_timestamp")

    def validate_event_id(self, value):
        queryset = LogEvent.objects.filter(event_id=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A log event with this event_id already exists."
            )

        return value

    def validate_level(self, value):
        allowed_levels = [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]

        value = value.upper()

        if value not in allowed_levels:
            raise serializers.ValidationError(
                f"Invalid log level. Allowed values: {', '.join(allowed_levels)}"
            )

        return value

    def create(self, validated_data):
        log_event = super().create(validated_data)

        Service.objects.filter(
            service_name=log_event.service_name,
            environment=log_event.environment,
        ).update(
            last_activity=timezone.now()
        )

        return log_event


class HeartbeatSerializer(serializers.Serializer):

    service_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )

    environment = serializers.CharField(
        max_length=50,
        trim_whitespace=True,
    )

    service_version = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
