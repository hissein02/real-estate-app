from rest_framework import serializers

from .models import DepositTransaction
from .services import get_deposit_balance


class DepositTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepositTransaction
        fields = [
            "id", "lease", "transaction_type", "amount", "date",
            "notes", "reference_invoice", "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class DepositBalanceSerializer(serializers.Serializer):
    lease_id = serializers.IntegerField()
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
