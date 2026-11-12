from django.contrib import admin

from .models import Owner, Property, Unit


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ["display_name", "is_company", "email", "phone", "created_at"]
    list_filter = ["is_company"]
    search_fields = ["first_name", "last_name", "company_name", "email"]


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0
    fields = ["name", "unit_type", "floor", "surface_area", "is_active"]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["name", "property_type", "owner", "city", "country", "created_at"]
    list_filter = ["property_type", "country"]
    search_fields = ["name", "address_line1", "city"]
    raw_id_fields = ["owner"]
    inlines = [UnitInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["__str__", "unit_type", "floor", "surface_area", "is_active"]
    list_filter = ["unit_type", "is_active"]
    search_fields = ["name", "building__name"]
    raw_id_fields = ["building"]
