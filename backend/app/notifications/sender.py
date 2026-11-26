"""Firebase Admin transport, initialized only by the opt-in worker."""

from datetime import timedelta
from email.utils import parsedate_to_datetime
from time import time

from requests.exceptions import RequestException

from app.core.config import get_settings


class PushSendError(Exception):
    def __init__(self, code: str, *, permanent=False, invalid_device=False, retry_after=60):
        super().__init__(code)
        self.code = code
        self.permanent = permanent
        self.invalid_device = invalid_device
        self.retry_after = retry_after


class FirebaseSender:
    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials

        settings = get_settings()
        options = {"httpTimeout": 15}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id
        credential = credentials.Certificate(settings.firebase_credentials_path) if settings.firebase_credentials_path else None
        self.app = firebase_admin.initialize_app(credential, options, name="keyword-push-worker")

    def send(self, fid, notification):
        from firebase_admin import exceptions, messaging

        notification_id = str(notification.id)
        is_chat = hasattr(notification, "room_id")
        slot = f"chat-{notification.room_id}" if is_chat else notification_id
        data = ({"type": "chat_message", "room_id": str(notification.room_id),
                 "sequence": str(notification.sequence), "user_id": str(notification.user_id),
                 "notification_id": notification_id, "title": notification.title,
                 "body": notification.body} if is_chat else
                {"type": "keyword_post", "post_id": str(notification.post_id),
                 "user_id": str(notification.user_id), "notification_id": notification_id})
        message = messaging.Message(
            fid=fid,
            notification=None if is_chat else messaging.Notification(title=notification.title, body=notification.body),
            data=data,
            android=messaging.AndroidConfig(
                priority="high", ttl=timedelta(seconds=get_settings().push_ttl_seconds),
                # Android chat data messages remain non-collapsible across rooms.
                collapse_key=None if is_chat else slot,
                notification=None if is_chat else messaging.AndroidNotification(channel_id="keyword-posts", tag=slot),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-push-type": "alert", "apns-priority": "10", "apns-collapse-id": slot,
                         "apns-expiration": str(int(time()) + get_settings().push_ttl_seconds)},
                payload=messaging.APNSPayload(aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=notification.title, body=notification.body) if is_chat else None,
                    sound="default")),
            ),
        )
        try:
            messaging.send(message, app=self.app)
        except messaging.UnregisteredError as error:
            raise PushSendError("unregistered", permanent=True, invalid_device=True) from error
        except (exceptions.InvalidArgumentError, messaging.SenderIdMismatchError) as error:
            raise PushSendError("invalid_message_or_project", permanent=True) from error
        except exceptions.FirebaseError as error:
            response = getattr(error, "http_response", None)
            retry_after = response.headers.get("Retry-After", "60") if response is not None else "60"
            try:
                delay = int(retry_after)
            except ValueError:
                try:
                    delay = int(parsedate_to_datetime(retry_after).timestamp() - time())
                except (TypeError, ValueError, OverflowError):
                    delay = 60
            raise PushSendError("firebase_unavailable", retry_after=max(60, delay)) from error
        except (OSError, TimeoutError, RequestException) as error:
            raise PushSendError("transport_unavailable") from error
