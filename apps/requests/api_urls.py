from rest_framework.routers import DefaultRouter

from .api import IssueRequestViewSet

router = DefaultRouter()
router.register("saidas", IssueRequestViewSet, basename="issue-request")

urlpatterns = router.urls
