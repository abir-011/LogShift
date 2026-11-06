from rest_framework import serializers

from .models import LogEvent


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