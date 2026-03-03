"""Context processors para dados globais das telas de requests."""

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
        "is_warehouse_user": request.user.groups.filter(name="almoxarifado").exists(),
        "is_section_chief": request.user.groups.filter(name="chefe_secao").exists(),
    }
