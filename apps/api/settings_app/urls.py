from django.urls import path

from .views import (
    BrandingView,
    CompanyInfoView,
    CompanyLogoView,
    EmailSettingsView,
    InvoiceEmailPreviewView,
    InvoiceEmailTestView,
    NotificationTemplateDetailView,
    SendTestEmailView,
    SignatoryDetailView,
    SignatoryListCreateView,
    SignatorySignatureView,
    TaskDetailView,
    TaskListView,
)

urlpatterns = [
    path("settings/company/", CompanyInfoView.as_view(), name="settings-company"),
    path("settings/company/logo/", CompanyLogoView.as_view(), name="settings-company-logo"),
    path("settings/signatories/", SignatoryListCreateView.as_view(), name="settings-signatories"),
    path(
        "settings/signatories/<int:pk>/",
        SignatoryDetailView.as_view(),
        name="settings-signatory-detail",
    ),
    path(
        "settings/signatories/<int:pk>/signature/",
        SignatorySignatureView.as_view(),
        name="settings-signatory-signature",
    ),
    path("settings/email/", EmailSettingsView.as_view(), name="settings-email"),
    path("settings/tasks/", TaskListView.as_view(), name="settings-tasks-list"),
    path(
        "settings/tasks/<str:task_key>/",
        TaskDetailView.as_view(),
        name="settings-task-detail",
    ),
    path(
        "settings/email-templates/<str:notification_type>/",
        NotificationTemplateDetailView.as_view(),
        name="settings-template-detail",
    ),
    path(
        "settings/email-templates/<str:notification_type>/send-test/",
        SendTestEmailView.as_view(),
        name="settings-template-test",
    ),
    path(
        "settings/invoice-email/preview/",
        InvoiceEmailPreviewView.as_view(),
        name="settings-invoice-email-preview",
    ),
    path(
        "settings/invoice-email/send-test/",
        InvoiceEmailTestView.as_view(),
        name="settings-invoice-email-test",
    ),
    path("branding/", BrandingView.as_view(), name="public-branding"),
]
