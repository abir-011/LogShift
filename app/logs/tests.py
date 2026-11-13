from datetime import datetime, timedelta, timezone

from rest_framework.test import APITestCase
from rest_framework import status

from .models import LogEvent


class LogIngestionTests(APITestCase):

    def setUp(self):
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
