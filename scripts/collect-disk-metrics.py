
import os
import shutil
import json
import platform
import logging
import urllib.request
import urllib.error


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("logshift-disk-collector")


def collect_disk_metrics():
    """Collect disk usage metrics for the root filesystem."""

    disk_path = "C:\\" if platform.system() == "Windows" else "/"

    usage = shutil.disk_usage(disk_path)

    total = usage.total
    used = usage.used
    available = usage.free

    usage_percent = round((used / total) * 100, 2)

    return {
        "disk_total_bytes": total,
        "disk_used_bytes": used,
        "disk_available_bytes": available,
        "disk_usage_percent": usage_percent,
    }


def send_metrics(metrics):
    """Submit disk metrics to the LogShift monitoring API."""

    api_url = os.environ.get("LOGSHIFT_METRICS_URL")
    api_key = os.environ.get("LOGSHIFT_MONITORING_API_KEY")

    if not api_url:
        raise RuntimeError("LOGSHIFT_METRICS_URL is not configured.")

    if not api_key:
        raise RuntimeError("LOGSHIFT_MONITORING_API_KEY is not configured.")

    payload = json.dumps(metrics).encode("utf-8")

    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))

        logger.info(
            "Disk metrics submitted successfully. HTTP %s. Collected at: %s",
            response.status,
            result.get("collected_at"),
        )


def main():
    try:
        metrics = collect_disk_metrics()

        logger.info(
            "Collected disk usage: %.2f%%",
            metrics["disk_usage_percent"],
        )

        send_metrics(metrics)

    except urllib.error.HTTPError as error:
        logger.error("Monitoring API returned HTTP %s.", error.code)
        raise

    except urllib.error.URLError as error:
        logger.error("Could not reach monitoring API: %s", error.reason)
        raise

    except Exception:
        logger.exception("Disk monitoring collection failed.")
        raise


if __name__ == "__main__":
    main()
