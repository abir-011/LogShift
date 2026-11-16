from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse

from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import LogEvent
from .models import LogDeletionAudit
from .admin_views import create_preview_token


@override_settings(LOGSHIFT_INGEST_API_KEY="test-ingest-key")
class LogIngestionTests(APITestCase):

    def setUp(self):

        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.client.credentials(HTTP_X_API_KEY="test-ingest-key")
        self.payload = {
            "event_id": "evt-test-1001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_name": "payment-service",
            "service_version": "1.0.0",
            "environment": "testing",
            "level": "ERROR",
            "event_type": "payment_failure",
            "operation": "process_payment",
            "message": "Payment gateway timeout",
            "message_template": "Payment gateway timeout",
            "cloud": {"provider": "local"},
            "log_source": {"provider": "simulated"},
            "performance": {"duration_ms": 5000},
            "correlation": {"trace_id": "tr-test-001"},
            "attributes": {"payment_id": "pay-test-001"},
            "exception": {},
            "raw": {}
        }

    def create_log(self, **overrides):
        payload = self.payload.copy()
        payload.update(overrides)

        response = self.client.post("/api/v1/logs/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        return response

    def test_create_log_successfully(self):
        response = self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            LogEvent.objects.filter(event_id="evt-test-1001").exists()
        )

    def test_duplicate_event_id_rejected(self):
        self.client.post("/api/v1/logs/", self.payload, format="json")

        response = self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_log_level_rejected(self):
        invalid_payload = self.payload.copy()
        invalid_payload["event_id"] = "evt-test-1002"
        invalid_payload["level"] = "INVALID"

        response = self.client.post(
            "/api/v1/logs/",
            invalid_payload,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            LogEvent.objects.filter(event_id="evt-test-1002").exists()
        )

    def test_batch_ingestion_successfully(self):
        logs = []

        for number in range(2):
            log = self.payload.copy()
            log["event_id"] = f"evt-batch-test-{number}"
            logs.append(log)

        response = self.client.post(
            "/api/v1/logs/batch/",
            {"logs": logs},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(LogEvent.objects.count(), 2)

    def test_batch_ingestion_is_all_or_nothing(self):
        self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        new_log = self.payload.copy()
        new_log["event_id"] = "evt-batch-new"

        duplicate_log = self.payload.copy()

        response = self.client.post(
            "/api/v1/logs/batch/",
            {"logs": [new_log, duplicate_log]},
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            LogEvent.objects.filter(event_id="evt-batch-new").exists()
        )

    def test_filter_logs_by_service(self):
        self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        response = self.client.get(
            "/api/v1/logs/?service_name=payment-service"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_combined_log_filters(self):
        self.create_log()
        self.create_log(
            event_id="evt-test-1003",
            service_name="auth-service",
            environment="production",
            level="INFO",
            message="Authentication succeeded",
        )

        response = self.client.get(
            "/api/v1/logs/?service_name=payment-service&"
            "environment=testing&level=ERROR"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["event_id"], "evt-test-1001"
        )

    def test_environment_filter(self):
        self.create_log()
        self.create_log(
            event_id="evt-test-1004",
            environment="production",
        )

        response = self.client.get("/api/v1/logs/?environment=production")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_matches_supported_log_fields(self):
        self.create_log(
            event_id="evt-search-identifier",
            service_name="search-service",
            event_type="search_failure",
            operation="index_document",
            message="Index writer timeout",
            message_template="Index writer failed for {document_id}",
            correlation={
                "trace_id": "trace-search-001",
                "request_id": "request-search-001",
                "span_id": "span-search-001",
                "parent_span_id": "parent-search-001",
            },
        )

        search_terms = [
            "search",
            "writer timeout",
            "search-identifier",
            "search-service",
            "search_failure",
            "index_document",
            "document_id",
            "trace-search-001",
            "request-search-001",
            "span-search-001",
            "parent-search-001",
        ]

        for term in search_terms:
            with self.subTest(term=term):
                response = self.client.get("/api/v1/logs/", {"search": term})

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 1)

    def test_query_validation_rejects_invalid_timestamps(self):
        for parameter in ("start_time", "end_time"):
            with self.subTest(parameter=parameter):
                response = self.client.get(
                    "/api/v1/logs/", {parameter: "not-a-timestamp"}
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(parameter, response.data)

    def test_query_validation_rejects_naive_timestamps(self):
        for parameter in ("start_time", "end_time"):
            with self.subTest(parameter=parameter):
                response = self.client.get(
                    "/api/v1/logs/", {parameter: "2026-11-12T10:00:00"}
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(parameter, response.data)

    def test_query_validation_accepts_timezone_aware_timestamps(self):
        self.create_log(timestamp="2026-11-12T12:00:00+05:30")

        response = self.client.get(
            "/api/v1/logs/",
            {
                "start_time": "2026-11-12T06:00:00Z",
                "end_time": "2026-11-12T07:00:00Z",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_query_validation_rejects_reversed_timestamps(self):
        response = self.client.get(
            "/api/v1/logs/",
            {
                "start_time": "2026-11-13T00:00:00Z",
                "end_time": "2026-11-12T00:00:00Z",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

    def test_query_validation_rejects_invalid_severity_and_pagination(self):
        invalid_level = self.client.get("/api/v1/logs/", {"level": "NOTICE"})
        invalid_page = self.client.get("/api/v1/logs/", {"page": 0})
        invalid_small_page_size = self.client.get(
            "/api/v1/logs/", {"page_size": 0}
        )
        invalid_large_page_size = self.client.get(
            "/api/v1/logs/", {"page_size": 101}
        )

        self.assertEqual(invalid_level.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_page.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            invalid_small_page_size.status_code, status.HTTP_400_BAD_REQUEST
        )
        self.assertEqual(
            invalid_large_page_size.status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_query_validation_preserves_case_insensitive_severity_filter(self):
        self.create_log()

        response = self.client.get("/api/v1/logs/", {"level": "error"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_custom_page_size_is_reported_in_paginated_response(self):
        for number in range(6):
            LogEvent.objects.create(
                event_id=f"evt-page-{number}",
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=number),
                service_name="payment-service",
                environment="testing",
                level="INFO",
                message=f"Pagination event {number}",
            )

        response = self.client.get("/api/v1/logs/", {"page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)
        self.assertEqual(response.data["page_size"], 5)
        self.assertEqual(len(response.data["results"]), 5)

    def test_out_of_range_page_returns_not_found(self):
        self.create_log()

        response = self.client.get("/api/v1/logs/", {"page": 2})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_individual_log(self):
        self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        response = self.client.get(
            "/api/v1/logs/evt-test-1001/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_id"], "evt-test-1001")

    def test_event_detail_handles_empty_structured_fields(self):
        LogEvent.objects.create(
            event_id="evt-empty-structured",
            timestamp=datetime.now(timezone.utc),
            service_name="payment-service",
            environment="testing",
            level="INFO",
            message="Minimal structured event",
            cloud={},
            log_source={},
            performance={},
            correlation={},
            attributes={},
            exception={},
            raw={},
        )

        response = self.client.get("/api/v1/logs/evt-empty-structured/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cloud"], {})
        self.assertEqual(response.data["log_source"], {})

    def test_retrieve_missing_log_returns_404(self):
        response = self.client.get(
            "/api/v1/logs/evt-does-not-exist/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_statistics_endpoint(self):
        self.client.post(
            "/api/v1/logs/",
            self.payload,
            format="json"
        )

        response = self.client.get("/api/v1/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_logs"], 1)
        self.assertEqual(response.data["error_count"], 1)

    def test_health_endpoint(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertEqual(response.json()["database"], "connected")


class LogManagementTests(APITestCase):
    summary_url = "/api/v1/admin/logs/summary/"
    preview_url = "/api/v1/admin/logs/deletion-preview/"
    delete_url = "/api/v1/admin/logs/delete/"
    history_url = "/api/v1/admin/logs/deletion-history/"
    page_url = "/administration/logs/"

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="ordinary-user",
            password="test-password",
        )
        self.staff_without_permission = user_model.objects.create_user(
            username="staff-without-permission",
            password="test-password",
            is_staff=True,
        )
        self.manager = user_model.objects.create_user(
            username="log-manager",
            password="test-password",
            is_staff=True,
        )
        self.manager.user_permissions.add(
            Permission.objects.get(codename="delete_logevent")
        )
        self.other_manager = user_model.objects.create_user(
            username="other-log-manager",
            password="test-password",
            is_staff=True,
        )
        self.other_manager.user_permissions.add(
            Permission.objects.get(codename="delete_logevent")
        )
        self.superuser = user_model.objects.create_superuser(
            username="superuser",
            password="test-password",
            email="superuser@example.com",
        )

    def login(self, user=None):
        self.client.force_login(user or self.manager)

    def create_log(
        self,
        event_id,
        timestamp,
        service_name="payment-service",
        level="INFO",
        environment="development",
    ):
        return LogEvent.objects.create(
            event_id=event_id,
            timestamp=timestamp,
            service_name=service_name,
            environment=environment,
            level=level,
            message=f"Sensitive log message for {event_id}",
            raw={"secret": "must-not-be-audited"},
        )

    def create_preview(self, **filters):
        response = self.client.get(self.preview_url, filters)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def delete_with_preview(self, preview, confirmation=True):
        return self.client.post(
            self.delete_url,
            {
                "preview_token": preview["preview_token"],
                "confirmation": confirmation,
            },
            format="json",
        )

    def test_anonymous_page_redirects_to_login(self):
        response = self.client.get(self.page_url)

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("/login/", response["Location"])

    def test_non_admin_users_are_forbidden_from_page_and_apis(self):
        for user in (self.user, self.staff_without_permission):
            self.login(user)

            with self.subTest(user=user.username, endpoint="page"):
                self.assertEqual(
                    self.client.get(self.page_url).status_code,
                    status.HTTP_403_FORBIDDEN,
                )

            for endpoint in (self.summary_url, self.preview_url):
                with self.subTest(user=user.username, endpoint=endpoint):
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            with self.subTest(user=user.username, endpoint=self.delete_url):
                response = self.client.post(
                    self.delete_url,
                    {"confirmation": True},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorized_staff_and_superuser_can_access_management(self):
        for user in (self.manager, self.superuser):
            self.login(user)

            with self.subTest(user=user.username, endpoint="page"):
                self.assertEqual(self.client.get(self.page_url).status_code, 200)

            with self.subTest(user=user.username, endpoint="summary"):
                self.assertEqual(
                    self.client.get(self.summary_url).status_code,
                    status.HTTP_200_OK,
                )

    def test_summary_reports_log_bounds_and_empty_table(self):
        self.login()
        empty_summary = self.client.get(self.summary_url)

        self.assertEqual(empty_summary.status_code, status.HTTP_200_OK)
        self.assertEqual(empty_summary.data["total_logs"], 0)
        self.assertIsNone(empty_summary.data["oldest_log"])
        self.assertIsNone(empty_summary.data["newest_log"])

        oldest = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newest = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.create_log("evt-summary-old", oldest)
        self.create_log("evt-summary-new", newest)

        summary = self.client.get(self.summary_url)

        self.assertEqual(summary.data["total_logs"], 2)
        self.assertEqual(summary.data["oldest_log"], oldest)
        self.assertEqual(summary.data["newest_log"], newest)
        self.assertIsInstance(summary.data["database_size_available"], bool)

    @patch("logs.admin_views.get_database_size_bytes", return_value=None)
    def test_summary_handles_unavailable_database_size(self, _size):
        self.login()

        response = self.client.get(self.summary_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["database_size_bytes"])
        self.assertFalse(response.data["database_size_available"])


    def test_preview_filters_by_datetime_service_level_and_combinations(self):
        self.login()

        self.create_log(
            "evt-before-start",
            datetime(2026, 1, 9, 23, 59, 59, tzinfo=timezone.utc),
            service_name="payment-service",
            level="ERROR",
        )
        self.create_log(
            "evt-at-start",
            datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
            service_name="payment-service",
            level="ERROR",
        )
        self.create_log(
            "evt-other-service",
            datetime(2026, 1, 10, 10, 30, tzinfo=timezone.utc),
            service_name="auth-service",
            level="INFO",
        )
        self.create_log(
            "evt-after-start",
            datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
            service_name="payment-service",
            level="ERROR",
        )

        time_preview = self.create_preview(
            start_time="2026-01-10T10:00:00Z",
        )
        service_preview = self.create_preview(service_name="payment-service")
        level_preview = self.create_preview(level="error")
        combined_preview = self.create_preview(
            start_time="2026-01-10T10:00:00Z",
            end_time="2026-01-10T11:00:00Z",
            service_name="payment-service",
            level="error",
        )

        self.assertEqual(time_preview["count"], 3)
        self.assertEqual(service_preview["count"], 3)
        self.assertEqual(level_preview["count"], 3)
        self.assertEqual(combined_preview["count"], 1)
        self.assertEqual(combined_preview["filters"]["level"], "ERROR")
        self.assertEqual(
            combined_preview["filters"]["start_time"],
            "2026-01-10T10:00:00+00:00",
        )



    def test_preview_filters_by_datetime_environment_and_combinations(self):
        self.login()

        self.create_log(
            "evt-before-start",
            datetime(2026, 1, 10, 9, 59, tzinfo=timezone.utc),
        )
        self.create_log(
            "evt-at-start",
            datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
            environment="production",
            level="ERROR",
        )
        self.create_log(
            "evt-before-end",
            datetime(2026, 1, 10, 10, 59, tzinfo=timezone.utc),
            environment="production",
            level="ERROR",
        )
        self.create_log(
            "evt-at-end",
            datetime(2026, 1, 10, 11, 0, tzinfo=timezone.utc),
            environment="production",
            level="ERROR",
        )
        self.create_log(
            "evt-other-environment",
            datetime(2026, 1, 10, 10, 30, tzinfo=timezone.utc),
            environment="staging",
            level="ERROR",
        )

        time_preview = self.create_preview(
            start_time="2026-01-10T10:00:00Z",
            end_time="2026-01-10T11:00:00Z",
        )
        environment_preview = self.create_preview(environment="production")
        combined_preview = self.create_preview(
            start_time="2026-01-10T10:00:00Z",
            end_time="2026-01-10T11:00:00Z",
            environment="production",
            level="error",
        )

        self.assertEqual(time_preview["count"], 3)
        self.assertEqual(environment_preview["count"], 3)
        self.assertEqual(combined_preview["count"], 2)
        self.assertEqual(
            combined_preview["filters"]["environment"],
            "production",
        )
        self.assertEqual(
            combined_preview["filters"]["level"],
            "ERROR",
        )


    def test_preview_rejects_empty_invalid_and_unknown_filters(self):
        self.login()

        cases = (
            {},
            {"before": "not-a-date"},
            {"level": "NOTICE"},
            {"unknown": "x"},
            {
                "start_time": "2026-01-10T12:00:00Z",
                "end_time": "2026-01-10T11:00:00Z",
            },
            {"start_time": "2026-01-10T10:00:00"},
        )
        for filters in cases:
            with self.subTest(filters=filters):
                response = self.client.get(self.preview_url, filters)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deletion_requires_confirmation_and_rejects_invalid_token(self):
        self.login()
        self.create_log("evt-confirm", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")

        unconfirmed = self.delete_with_preview(preview, confirmation=False)
        invalid = self.client.post(
            self.delete_url,
            {"preview_token": "invalid", "confirmation": True},
            format="json",
        )
        unrestricted = self.client.post(
            self.delete_url,
            {"confirmation": True},
            format="json",
        )
        unknown_field = self.client.post(
            self.delete_url,
            {
                "preview_token": preview["preview_token"],
                "confirmation": True,
                "unexpected": "value",
            },
            format="json",
        )

        self.assertEqual(unconfirmed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unrestricted.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown_field.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(LogEvent.objects.filter(event_id="evt-confirm").exists())

    def test_altered_preview_token_is_rejected(self):
        self.login()
        self.create_log("evt-token", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")
        altered_token = f"{preview['preview_token']}altered"

        response = self.client.post(
            self.delete_url,
            {"preview_token": altered_token, "confirmation": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(LogEvent.objects.filter(event_id="evt-token").exists())

    def test_expired_preview_token_is_rejected(self):
        self.login()

        with patch("django.core.signing.time.time", return_value=1):
            expired_token = create_preview_token(
                self.manager,
                {"service_name": "payment-service"},
                0,
                0,
            )
        response = self.client.post(
            self.delete_url,
            {"preview_token": expired_token, "confirmation": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_token_cannot_be_used_by_another_manager(self):
        self.login(self.manager)
        self.create_log("evt-user-bound", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")
        self.login(self.other_manager)

        response = self.delete_with_preview(preview)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(LogEvent.objects.filter(event_id="evt-user-bound").exists())

    def test_changed_snapshot_requires_a_fresh_preview(self):
        self.login()
        log = self.create_log("evt-changed", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")
        log.delete()

        response = self.delete_with_preview(preview)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(LogDeletionAudit.objects.count(), 0)

    def test_new_logs_after_preview_are_not_deleted(self):
        self.login()
        self.create_log("evt-previewed", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-02T00:00:00Z",
        )
        self.create_log("evt-new-after-preview", datetime(2026, 1, 1, tzinfo=timezone.utc))

        response = self.delete_with_preview(preview)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted_count"], 1)
        self.assertFalse(LogEvent.objects.filter(event_id="evt-previewed").exists())
        self.assertTrue(LogEvent.objects.filter(event_id="evt-new-after-preview").exists())

    def test_zero_match_preview_cannot_create_audit_records(self):
        self.login()
        preview = self.create_preview(service_name="missing-service")

        response = self.delete_with_preview(preview)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(LogDeletionAudit.objects.count(), 0)

    def test_preview_token_cannot_delete_logs_twice(self):
        self.login()
        self.create_log("evt-replay", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")

        first_response = self.delete_with_preview(preview)
        second_response = self.delete_with_preview(preview)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(LogDeletionAudit.objects.count(), 1)

    def test_django_admin_cannot_bypass_audited_log_deletion(self):
        log = self.create_log("evt-admin-bypass", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.login(self.superuser)

        response = self.client.post(
            reverse("admin:logs_logevent_delete", args=[log.pk]),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(LogEvent.objects.filter(pk=log.pk).exists())

    def test_deletion_creates_durable_non_sensitive_audit_record(self):
        self.login()
        self.create_log("evt-audit", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service", level="info")

        response = self.delete_with_preview(preview)
        audit = LogDeletionAudit.objects.get(pk=response.data["audit_id"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(audit.actor, self.manager)
        self.assertEqual(audit.actor_username, self.manager.username)
        self.assertEqual(audit.filters, {"service_name": "payment-service", "level": "INFO"})
        self.assertEqual(audit.preview_count, 1)
        self.assertEqual(audit.deleted_count, 1)
        self.assertIsNotNone(audit.performed_at)
        self.assertFalse(LogEvent.objects.filter(event_id="evt-audit").exists())
        self.assertNotIn("message", audit.filters)
        self.assertNotIn("raw", audit.filters)
        self.manager.delete()
        audit.refresh_from_db()
        self.assertIsNone(audit.actor)
        self.assertEqual(audit.actor_username, "log-manager")

    @patch("logs.admin_views.LogDeletionAudit.objects.create")
    def test_audit_failure_rolls_back_log_deletion(self, mocked_create):
        self.login()
        self.create_log("evt-rollback", datetime(2026, 1, 1, tzinfo=timezone.utc))
        preview = self.create_preview(service_name="payment-service")
        mocked_create.side_effect = IntegrityError("audit write failed")

        response = self.delete_with_preview(preview)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertTrue(LogEvent.objects.filter(event_id="evt-rollback").exists())
        self.assertEqual(LogDeletionAudit.objects.count(), 0)

    def test_session_authenticated_deletion_requires_csrf_token(self):
        self.create_log("evt-csrf", datetime(2026, 1, 1, tzinfo=timezone.utc))
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        preview_response = csrf_client.get(
            self.preview_url,
            {"service_name": "payment-service"},
        )

        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        response = csrf_client.post(
            self.delete_url,
            {
                "preview_token": preview_response.data["preview_token"],
                "confirmation": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(LogEvent.objects.filter(event_id="evt-csrf").exists())

    def test_authorized_manager_can_view_deletion_history(self):
        self.login(self.manager)

        LogDeletionAudit.objects.create(
            actor=self.manager,
            actor_username=self.manager.username,
            filters={"service_name": "payment-service"},
            preview_count=5,
            deleted_count=5,
            source=LogDeletionAudit.SOURCE_MANUAL,
        )

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_count"], 1)
        self.assertEqual(response.data["results"][0]["actor_username"], "log-manager")
        self.assertEqual(response.data["results"][0]["deleted_count"], 5)


    def test_ordinary_user_cannot_view_deletion_history(self):
        self.login(self.user)

        response = self.client.get(self.history_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_deletion_history_pagination(self):
        self.login(self.manager)

        for index in range(12):
            LogDeletionAudit.objects.create(
                actor=self.manager,
                actor_username=self.manager.username,
                filters={"service_name": f"service-{index}"},
                preview_count=1,
                deleted_count=1,
                source=LogDeletionAudit.SOURCE_MANUAL,
            )

        first_page = self.client.get(self.history_url)
        second_page = self.client.get(self.history_url, {"page": 2})

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data["total_count"], 12)
        self.assertEqual(first_page.data["total_pages"], 2)
        self.assertEqual(len(first_page.data["results"]), 10)

        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 2)
