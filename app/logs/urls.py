from django.urls import path

from .views import (
    LogIngestView,
    BatchLogIngestView,
    LogDetailView,
    LogStatsView,
    ServiceListView,
    ServiceHeartbeatView,
)
from .admin_views import (
    AdminLogSummaryView,
    LogDeletionPreviewView,
    LogDeletionView,
    LogDeletionHistoryView,
)

urlpatterns = [
    path("logs/", LogIngestView.as_view(), name="logs"),
    path("logs/batch/", BatchLogIngestView.as_view(), name="log-batch-ingest"),
    path("logs/<str:event_id>/", LogDetailView.as_view(), name="log-detail"),
    path("stats/", LogStatsView.as_view(), name="log-stats"),
    path("services/", ServiceListView.as_view(), name="service-list"),
    path(
        "admin/logs/summary/",
        AdminLogSummaryView.as_view(),
        name="admin-log-summary",
    ),
    path(
        "admin/logs/deletion-preview/",
        LogDeletionPreviewView.as_view(),
        name="admin-log-deletion-preview",
    ),
    path(
        "admin/logs/delete/",
        LogDeletionView.as_view(),
        name="admin-log-delete",
    ),
    path(
        "admin/logs/deletion-history/",
        LogDeletionHistoryView.as_view(),
        name="admin-log-deletion-history",
    ),
    path(
        "services/heartbeat/",
        ServiceHeartbeatView.as_view(),
        name="service-heartbeat",
        ),
]
