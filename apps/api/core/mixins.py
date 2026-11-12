class AuditedDestroyMixin:
    """Write a full snapshot to the audit log when a record is deleted.

    Mirrors the billing hard-delete services: the row disappears, but what it
    contained stays recoverable from AuditLog.snapshot_json.
    """

    def perform_destroy(self, instance):
        from audit.models import AuditAction, AuditLog
        from core.snapshots import to_jsonable

        snapshot = to_jsonable(self.get_serializer(instance).data)
        object_type = type(instance).__name__
        object_id = str(instance.pk)
        object_repr = str(instance)

        # Runs first: a PROTECT violation aborts here, before anything is logged.
        instance.delete()

        AuditLog.objects.create(
            actor=self.request.user,
            action=AuditAction.HARD_DELETE,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr,
            snapshot_json=snapshot,
            reason=self.request.query_params.get("reason", ""),
        )
