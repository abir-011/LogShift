from django.db import models


class InfrastructureMetric(models.Model):
    """
    Stores historical infrastructure resource measurements.
    """

    disk_total_bytes = models.BigIntegerField()
    disk_used_bytes = models.BigIntegerField()
    disk_available_bytes = models.BigIntegerField()
    disk_usage_percent = models.FloatField()

    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "infrastructure_metrics"
        ordering = ["-collected_at"]

    def __str__(self):
        return (
            f"Disk usage: {self.disk_usage_percent}% "
            f"at {self.collected_at}"
        )