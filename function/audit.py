import json
import logging
import os
from datetime import datetime, timezone

from azure.storage.queue import QueueClient


AUDIT_QUEUE_NAME = "audit-events"


def write_audit_event(
    request_id: str,
    stage: str,
    status: str,
    actor: str = "system",
    decision: str | None = None,
    reason: str | None = None,
    message: str | None = None,
) -> None:
    """
    Write an audit event to the audit-events Azure Storage Queue.
    """

    connection_string = os.environ.get(
        "AzureWebJobsStorage"
    )

    if not connection_string:
        raise RuntimeError(
            "AzureWebJobsStorage is not configured."
        )

    event = {
        "request_id": request_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "stage": stage,
        "status": status,
        "actor": actor,
        "decision": decision,
        "reason": reason,
        "message": message,
    }

    try:

        queue = QueueClient.from_connection_string(
            conn_str=connection_string,
            queue_name=AUDIT_QUEUE_NAME,
        )

        queue.send_message(
            json.dumps(
                event,
                ensure_ascii=False,
            )
        )

        logging.info(
            "Audit event written: %s / %s / %s",
            request_id,
            stage,
            status,
        )

    except Exception:

        logging.exception(
            "Failed to write audit event: %s",
            request_id,
        )

        raise