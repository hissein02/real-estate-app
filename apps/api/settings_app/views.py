import os

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminRole

from .models import CompanyInfo, EmailSettings, Signatory
from .validators import validate_logo
from .serializers import (
    CompanyInfoSerializer,
    EmailSettingsSerializer,
    NotificationTemplateSerializer,
    SignatorySerializer,
    SignatoryWriteSerializer,
    TaskConfigSerializer,
    TaskUpdateSerializer,
    TestEmailSerializer,
    InvoiceTestEmailSerializer,
)
from .services import (
    get_template,
    list_tasks,
    send_test_email,
    update_task,
    update_template,
)


class CompanyInfoView(APIView):
    """GET / PUT company information.

    GET is available to any authenticated user (needed by the UI layout).
    PUT is restricted to admin role.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminRole()]

    def get(self, request):
        info = CompanyInfo.load()
        return Response(CompanyInfoSerializer(info).data)

    def put(self, request):
        info = CompanyInfo.load()
        serializer = CompanyInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(info, field, value)
        info.save()

        return Response(CompanyInfoSerializer(info).data)


class CompanyLogoView(APIView):
    """POST to upload a logo, DELETE to remove it. Admin only."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("logo")
        if not file:
            return Response(
                {"detail": "No file provided. Send as 'logo' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_logo(file)
        except ValidationError as e:
            messages = e.messages if hasattr(e, "messages") else [str(e)]
            return Response(
                {"detail": messages[0] if len(messages) == 1 else messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        info = CompanyInfo.load()

        # Delete old logo file if exists
        if info.logo:
            info.logo.delete(save=False)

        # Normalise filename to logo.<ext>
        ext = os.path.splitext(file.name)[1].lower()
        file.name = f"logo{ext}"

        info.logo = file
        info.save()

        return Response(CompanyInfoSerializer(info).data)

    def delete(self, request):
        info = CompanyInfo.load()
        if info.logo:
            info.logo.delete(save=False)
            info.logo = ""
            info.save()
        return Response(CompanyInfoSerializer(info).data)


class SignatoryListCreateView(APIView):
    """GET all signatories / POST to create a new one. Admin only."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        signatories = Signatory.objects.all()
        return Response(SignatorySerializer(signatories, many=True).data)

    def post(self, request):
        serializer = SignatoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sig = Signatory.objects.create(**serializer.validated_data)
        return Response(SignatorySerializer(sig).data, status=status.HTTP_201_CREATED)


class SignatoryDetailView(APIView):
    """GET / PATCH / DELETE a single signatory. Admin only."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def _get_object(self, pk):
        try:
            return Signatory.objects.get(pk=pk)
        except Signatory.DoesNotExist:
            return None

    def get(self, request, pk):
        sig = self._get_object(pk)
        if not sig:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SignatorySerializer(sig).data)

    def patch(self, request, pk):
        sig = self._get_object(pk)
        if not sig:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SignatoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(sig, field, value)
        sig.save()
        return Response(SignatorySerializer(sig).data)

    def delete(self, request, pk):
        sig = self._get_object(pk)
        if not sig:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Clear FK reference in CompanyInfo before deletion
        CompanyInfo.objects.filter(pdf_signatory=sig).update(pdf_signatory=None)
        if sig.signature_image:
            sig.signature_image.delete(save=False)
        sig.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignatorySignatureView(APIView):
    """POST to upload a signature image / DELETE to remove it. Admin only."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    def _get_object(self, pk):
        try:
            return Signatory.objects.get(pk=pk)
        except Signatory.DoesNotExist:
            return None

    def post(self, request, pk):
        sig = self._get_object(pk)
        if not sig:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get("signature")
        if not file:
            return Response(
                {"detail": "No file provided. Send as 'signature' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            return Response(
                {"detail": "Only PNG, JPG, and WEBP images are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file.size > 2 * 1024 * 1024:
            return Response(
                {"detail": "File size must not exceed 2 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if sig.signature_image:
            sig.signature_image.delete(save=False)

        file.name = f"signatory_{sig.pk}_signature{ext}"
        sig.signature_image = file
        sig.save()

        return Response(SignatorySerializer(sig).data)

    def delete(self, request, pk):
        sig = self._get_object(pk)
        if not sig:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if sig.signature_image:
            sig.signature_image.delete(save=False)
            sig.signature_image = ""
            sig.save()
        return Response(SignatorySerializer(sig).data)


class EmailSettingsView(APIView):
    """GET / PUT email + SMTP settings (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        settings_obj = EmailSettings.load()
        serializer = EmailSettingsSerializer(settings_obj)
        return Response(serializer.data)

    def put(self, request):
        settings_obj = EmailSettings.load()
        serializer = EmailSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        # Don't overwrite password if the masked placeholder was sent back
        if data.get("smtp_password") == "********":
            data.pop("smtp_password")

        for field, value in data.items():
            setattr(settings_obj, field, value)
        settings_obj.save()  # triggers apply_to_django_settings()

        return Response(EmailSettingsSerializer(settings_obj).data)


class TaskListView(APIView):
    """GET list of all scheduled tasks (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        tasks = list_tasks()
        serializer = TaskConfigSerializer(tasks, many=True)
        return Response(serializer.data)


class TaskDetailView(APIView):
    """PATCH a single scheduled task (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def patch(self, request, task_key):
        serializer = TaskUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = update_task(
                task_key,
                is_enabled=serializer.validated_data.get("is_enabled"),
                hour=serializer.validated_data.get("hour"),
                minute=serializer.validated_data.get("minute"),
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(TaskConfigSerializer(result).data)


class NotificationTemplateDetailView(APIView):
    """GET / PUT a notification email template (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, notification_type):
        try:
            data = get_template(notification_type)
        except ValueError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = NotificationTemplateSerializer(data)
        return Response(serializer.data)

    def put(self, request, notification_type):
        serializer = NotificationTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            data = update_template(
                notification_type,
                subject_template=serializer.validated_data.get(
                    "subject_template"
                ),
                body_template=serializer.validated_data.get("body_template"),
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(NotificationTemplateSerializer(data).data)


class SendTestEmailView(APIView):
    """POST — send a test email using the template with sample data."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, notification_type):
        serializer = TestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_test_email(
                notification_type,
                serializer.validated_data["recipient_email"],
            )
        except ValueError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to send: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": "Test email sent successfully."})


class InvoiceEmailPreviewView(APIView):
    """GET — render the invoice email template with sample data for preview."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from billing.services.email_service import render_invoice_email_preview

        html = render_invoice_email_preview()
        return Response({"html": html})


class InvoiceEmailTestView(APIView):
    """POST — send a test invoice email to the given address."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = InvoiceTestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        name = (
            user.get_full_name()
            or getattr(user, "username", None)
            or user.email
        )
        triggered_by = f"Admin: {name}"

        try:
            from billing.services.email_service import send_test_invoice_email

            send_test_invoice_email(
                serializer.validated_data["recipient_email"],
                triggered_by=triggered_by,
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to send: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": "Test invoice email sent successfully."})


class BrandingView(APIView):
    """GET public branding info (no auth required). Returns display_name and logo_url."""

    permission_classes = []  # public, no auth required
    authentication_classes = []  # skip JWT auth entirely

    def get(self, request):
        info = CompanyInfo.load()
        return Response({
            "display_name": info.display_name or "RealEstate",
            "logo_url": info.logo.url if info.logo else None,
        })
