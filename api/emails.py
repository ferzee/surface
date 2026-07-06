from django.conf import settings
from django.core.mail import send_mail

SUBJECTS = {
    'like': '{actor} liked your post',
    'comment': '{actor} commented on your post',
    'buddy_request': '{actor} sent you a buddy request',
    'buddy_accepted': '{actor} accepted your buddy request',
}

BODIES = {
    'like': '{actor} liked your post on Surface.',
    'comment': '{actor} commented on your post on Surface.',
    'buddy_request': '{actor} sent you a buddy request on Surface.',
    'buddy_accepted': '{actor} accepted your buddy request on Surface.',
}


def send_notification_email(recipient, actor, type):
    if not recipient.notify_by_email or not recipient.email:
        return
    subject = SUBJECTS[type].format(actor=actor.username)
    message = BODIES[type].format(actor=actor.username)
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient.email], fail_silently=False)
    except Exception:
        pass
