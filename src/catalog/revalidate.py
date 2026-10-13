"""Tell the frontend to drop cached pages after admin edits (ARCHITECTURE.md §6).

Signal handlers call `schedule(tag)`. Tags collect per thread until the
transaction commits, then go out in one fire-and-forget request, so saving a
product with its inlines sends a single webhook.
"""

import json
import logging
import threading
import urllib.request

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 3

_pending = threading.local()


def schedule(tag):
    if not settings.FRONTEND_REVALIDATE_URL:
        return
    tags = getattr(_pending, "tags", None)
    if tags is None:
        tags = _pending.tags = set()
    tags.add(tag)
    # Every handler registers a callback; the first one to run sends all tags
    # and the rest find nothing left. Tags from a rolled-back transaction
    # just ride along with the next commit.
    transaction.on_commit(_flush)


def _flush():
    tags = getattr(_pending, "tags", None)
    if not tags:
        return
    _pending.tags = set()
    threading.Thread(target=_send, args=(sorted(tags),), daemon=True).start()


def _send(tags):
    request = urllib.request.Request(
        settings.FRONTEND_REVALIDATE_URL,
        data=json.dumps({"tags": tags}).encode(),
        headers={
            "Authorization": f"Bearer {settings.REVALIDATE_SECRET}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            logger.info("Revalidated %s (HTTP %s)", tags, response.status)
    except Exception:
        logger.exception("Frontend revalidation failed for %s", tags)
