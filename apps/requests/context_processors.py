"""Context processors para dados globais das telas de requests."""

from apps.accounts.models import user_is_section_chief, user_is_warehouse
from apps.requests.models import RequestNotification


def request_notifications_context(request):
    """Expõe contagem de notificações não lidas para usuário autenticado."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "unread_notifications_count": 0,
            "is_warehouse_user": False,
            "is_section_chief": False,
        }
    unread_count = RequestNotification.objects.filter(user=request.user, is_read=False).count()
    return {
        "unread_notifications_count": unread_count,
        "is_warehouse_user": user_is_warehouse(request.user),
        "is_section_chief": user_is_section_chief(request.user),
    }
