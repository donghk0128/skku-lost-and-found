"""Run with python -m app.notifications.worker after applying migrations."""

import logging
import signal
from threading import Event

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.notifications.sender import FirebaseSender
from app.notifications.service import deliver_next

logger = logging.getLogger(__name__)


def main():
    if not get_settings().push_enabled:
        raise SystemExit("Set PUSH_ENABLED=true after configuring Firebase credentials.")
    sender = FirebaseSender()
    stopping = Event()
    prefer_chat = False
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    while not stopping.is_set():
        try:
            with SessionLocal() as db:
                worked = deliver_next(db, sender, prefer_chat=prefer_chat)
        except Exception:
            # Do not log exception text, which can include tokens from SDK/SQL parameters.
            logger.error("Push worker transaction failed; retrying after poll interval")
            worked = False
        if worked:
            prefer_chat = not prefer_chat
        else:
            stopping.wait(get_settings().push_poll_seconds)


if __name__ == "__main__":
    main()
