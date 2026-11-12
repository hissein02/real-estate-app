from rest_framework import serializers

from .models import Owner, Property, Unit


class OwnerSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = Owner
        fields = [
            "id", "first_name", "last_name", "company_name", "is_company",
            "email", "phone", "address", "notes", "display_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PropertySerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    full_address = serializers.ReadOnlyField()
    unit_count = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            "id", "name", "property_type", "owner", "owner_name",
            "address_line1", "address_line2", "city", "country", "postal_code",
            "full_address", "description", "unit_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_unit_count(self, obj):
        return obj.units.filter(is_active=True).count()


class UnitSerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source="building.name", read_only=True)
    is_occupied = serializers.ReadOnlyField()

    class Meta:
        model = Unit
        fields = [
            "id", "building", "property_name", "name", "unit_type",
            "floor", "surface_area", "description", "is_active",
            "is_occupied", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UnitNestedSerializer(serializers.ModelSerializer):
    """Lightweight nested serializer used inside PropertyDetailSerializer."""
    is_occupied = serializers.ReadOnlyField()

    class Meta:
        model = Unit
        fields = ["id", "name", "unit_type", "floor", "surface_area", "is_active", "is_occupied"]


class PropertyDetailSerializer(PropertySerializer):
    units = UnitNestedSerializer(many=True, read_only=True)

    class Meta(PropertySerializer.Meta):
        fields = PropertySerializer.Meta.fields + ["units"]
