from rest_framework import serializers

from .models import Tenant, Lease


class TenantSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = Tenant
        fields = [
            "id", "first_name", "last_name", "company_name", "is_company",
            "email", "phone", "id_number", "address", "notes",
            "display_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LeaseSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.display_name", read_only=True)
    unit_name = serializers.CharField(source="unit.__str__", read_only=True)
    monthly_rent_equivalent = serializers.ReadOnlyField()

    class Meta:
        model = Lease
        fields = [
            "id", "unit", "unit_name", "tenant", "tenant_name",
            "status", "start_date", "end_date",
            "rent_unit_price", "currency", "billing_interval_months",
            "billing_cycle_anchor", "prorate_first_period",
            "deposit_amount",
            "late_fee_type", "late_fee_value", "late_fee_grace_period_days",
            "renewed_from", "notes",
            "monthly_rent_equivalent",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "renewed_from"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class LeaseRenewSerializer(serializers.Serializer):
    new_end_date = serializers.DateField(required=False, allow_null=True)
    new_rent_unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )


class LeaseTerminateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1)
    termination_date = serializers.DateField()


class LeaseForceDeleteSerializer(serializers.Serializer):
    """Confirmation for the cascading delete. `confirm` must be explicit."""

    confirm = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Must confirm the cascading delete.")
        return value
