from rest_framework import serializers

from .models import InfrastructureMetric


class InfrastructureMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = InfrastructureMetric
        fields = [
            "disk_total_bytes",
            "disk_used_bytes",
            "disk_available_bytes",
            "disk_usage_percent",
        ]

    def validate(self, attrs):
        total = attrs["disk_total_bytes"]
        used = attrs["disk_used_bytes"]
        available = attrs["disk_available_bytes"]
        percentage = attrs["disk_usage_percent"]

        if total <= 0:
            raise serializers.ValidationError(
                "Disk total must be greater than zero."
            )

        if used < 0 or available < 0:
            raise serializers.ValidationError(
                "Disk usage values cannot be negative."
            )

        if used + available != total:
            raise serializers.ValidationError(
                "Used and available disk space must equal total space."
            )

        if not 0 <= percentage <= 100:
            raise serializers.ValidationError(
                "Disk usage percentage must be between 0 and 100."
            )

        return attrs