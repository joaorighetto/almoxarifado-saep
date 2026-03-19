"""Views de autenticação e perfil de usuário."""

from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import user_is_section_chief, user_is_warehouse


@method_decorator(never_cache, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class RoleBasedLoginView(LoginView):
    """Login com redirecionamento de acordo com grupo/papel do usuário."""

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        user = self.request.user
        if user_is_warehouse(user):
            return reverse("requests:warehouse_approved_queue")
        if user_is_section_chief(user):
            return reverse("requests:chief_pending_approvals")
        return reverse("requests:material_request_create")
