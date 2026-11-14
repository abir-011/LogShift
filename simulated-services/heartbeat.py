import os
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HEARTBEAT_URL = os.getenv(
    "LOGSHIFT_URL",
    "http://localhost:8000/api/v1/logs/"
).replace("/logs/", "/services/heartbeat/")

LOGSHIFT_API_KEY = os.getenv("LOGSHIFT_INGEST_API_KEY")

if not LOGSHIFT_API_KEY:
    raise RuntimeError(
        "LOGSHIFT_INGEST_API_KEY environment variable is not set."
    )


def send_heartbeat(service_name, environment, service_version):
    payload = {
        "service_name": service_name,
        "environment": environment,
        "service_version": service_version,
    }

    request = Request(
        HEARTBEAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": LOGSHIFT_API_KEY,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:
            print(
                f"[HEARTBEAT] {service_name} | HTTP {response.status}"
            )
            return True

    except HTTPError as error:
        print(f"[HEARTBEAT ERROR] HTTP {error.code}")

    except URLError as error:
        print(f"[HEARTBEAT CONNECTION ERROR] {error.reason}")

    except OSError as error:
        print(f"[HEARTBEAT CONNECTION ERROR] {error}")

    return False

