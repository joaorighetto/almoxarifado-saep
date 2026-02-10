from django.urls import path
from . import views

app_name = "requests"

urlpatterns = [
    path("saidas/nova/", views.issue_create, name="issue_create"),
    path("saidas/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("saidas/<int:pk>/csv/", views.issue_export_csv, name="issue_export_csv"),
]
