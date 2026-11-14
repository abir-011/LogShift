import uuid

from django.db import models
from django.utils import timezone

def generate_event_id():
    return f"evt-{uuid.uuid4().hex[:12]}"

class LogEvent(models.Model):

    event_id = models.CharField(
        max_length=64,
        default=generate_event_id,
        unique=True,
        editable=False
    )

    timestamp = models.DateTimeField()
    observed_timestamp = models.DateTimeField(auto_now_add=True)

    service_name = models.CharField(max_length=150)
    service_version = models.CharField(max_length=50, blank=True)
    environment = models.CharField(max_length=50)

    level = models.CharField(max_length=20)
    event_type = models.CharField(max_length=100, blank=True)
    operation = models.CharField(max_length=150, blank=True)

    message = models.TextField()
    message_template = models.TextField(blank=True)

    cloud = models.JSONField(default=dict, blank=True)
    log_source = models.JSONField(default=dict, blank=True)
    performance = models.JSONField(default=dict, blank=True)
    correlation = models.JSONField(default=dict, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    exception = models.JSONField(default=dict, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "log_events"
        ordering = ["-timestamp"]

        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["service_name"]),
            models.Index(fields=["level"]),
            models.Index(fields=["environment"]),
        ]

    def __str__(self):
        return f"{self.service_name} | {self.level} | {self.message[:50]}"

class Service(models.Model):

    service_name = models.CharField(max_length=150)
    environment = models.CharField(max_length=50)
    service_version = models.CharField(max_length=50, blank=True)

    last_heartbeat = models.DateTimeField()
    last_activity = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "services"
        ordering = ["service_name", "environment"]

        constraints = [
            models.UniqueConstraint(
                fields=["service_name", "environment"],
                name="unique_service_environment",
            )
        ]

    def __str__(self):
        return f"{self.service_name} ({self.environment})"

    @property
    def status(self):
        heartbeat_age = (
            timezone.now() - self.last_heartbeat
        ).total_seconds()

        if heartbeat_age <= 60:
            return "Healthy"

        elif heartbeat_age <= 120:
            return "Degraded"

        return "Down"