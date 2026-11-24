from .models import Notification


def notifications_context(request):
    """Context processor providing unread notifications and count for authenticated users."""
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).select_related('sender', 'task', 'project')[:5]
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return {
            'navbar_unread_notifications': unread_notifications,
            'navbar_unread_count': unread_count,
        }
    return {
        'navbar_unread_notifications': [],
        'navbar_unread_count': 0,
    }
