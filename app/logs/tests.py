from datetime import datetime, timezone

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