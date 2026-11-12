from django.urls import path

from .views import (
    LogIngestView,
    BatchLogIngestView,
    LogDetailView,
    LogStatsView,
    ServiceListView,
)

urlpatterns = [
    path("logs/", LogIngestView.as_view(), name="logs"),
    path("logs/batch/", BatchLogIngestView.as_view(), name="log-batch-ingest"),
    path("logs/<str:event_id>/", LogDetailView.as_view(), name="log-detail"),
    path("stats/", LogStatsView.as_view(), name="log-stats"),
    path("services/", ServiceListView.as_view(), name="service-list"),
]