from django.contrib import admin

from .models import LogEvent


@admin.register(LogEvent)
class LogEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "service_name",
        "level",
        "environment",
        "timestamp",
    )

    list_filter = (
        "service_name",
        "level",
        "environment",
    )

    search_fields = (
        "event_id",
        "message",
        "service_name",
    )

    ordering = ("-timestamp",)