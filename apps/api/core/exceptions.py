import logging
from collections import Counter

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _summarize_blockers(protected_objects):
    """Group blocking rows by model: {'invoice': (3, 'invoices'), ...}."""
    counts = Counter()
    plurals = {}
    for obj in protected_objects:
        name = str(obj._meta.verbose_name)
        counts[name] += 1
        plurals[name] = str(obj._meta.verbose_name_plural)
    return {name: (n, plurals[name]) for name, n in counts.items()}


def _blocker_phrase(blockers):
    """'3 invoices and 1 payment' — uses Django's own plural names."""
    parts = [
        f"{n} {name if n == 1 else plural}"
        for name, (n, plural) in sorted(blockers.items())
    ]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f" and {parts[-1]}"


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, DjangoValidationError):
        data = {"detail": exc.messages if hasattr(exc, "messages") else str(exc)}
        return Response(data, status=status.HTTP_400_BAD_REQUEST)

    # A delete blocked by on_delete=PROTECT/RESTRICT is a conflict the caller can
    # resolve, not a server fault. Say exactly what is holding the record.
    if isinstance(exc, (ProtectedError, RestrictedError)):
        blocked = getattr(exc, "protected_objects", None) or getattr(exc, "restricted_objects", [])
        blockers = _summarize_blockers(blocked)
        model = "record"
        view = context.get("view") if context else None
        queryset = getattr(view, "queryset", None)
        if queryset is not None:
            model = queryset.model._meta.verbose_name
        # Phrased to avoid subject/verb agreement problems across counts.
        detail = (
            f"This {model} cannot be deleted: it is still referenced by "
            f"{_blocker_phrase(blockers)}. Remove or reassign those records first."
            if blockers
            else f"This {model} cannot be deleted: other records still reference it."
        )
        return Response(
            {"detail": detail, "blocked_by": {k: v[0] for k, v in blockers.items()}},
            status=status.HTTP_409_CONFLICT,
        )

    if response is not None:
        return response

    # Services signal business-rule violations with ValueError and a message
    # written for the operator ("Invoice is already void."). Several views
    # already translate it to 400; do it everywhere rather than leaking a 500.
    if isinstance(exc, ValueError):
        logger.warning("Business rule rejected the request: %s", exc)
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    logger.exception("Unhandled exception in view", exc_info=exc)
    return Response(
        {"detail": "An unexpected error occurred."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
