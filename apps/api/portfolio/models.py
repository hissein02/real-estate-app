from django.db import models


class Owner(models.Model):
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    is_company = models.BooleanField(default=False)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "company_name"]

    @property
    def display_name(self):
        if self.is_company:
            return self.company_name or f"Company #{self.pk}"
        return f"{self.first_name} {self.last_name}".strip() or f"Owner #{self.pk}"

    def __str__(self):
        return self.display_name


class PropertyType(models.TextChoices):
    RESIDENTIAL = "residential", "Residential"
    COMMERCIAL = "commercial", "Commercial"
    MIXED = "mixed", "Mixed"
    INDUSTRIAL = "industrial", "Industrial"
    LAND = "land", "Land"


class Property(models.Model):
    name = models.CharField(max_length=200)
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.RESIDENTIAL,
    )
    owner = models.ForeignKey(Owner, on_delete=models.PROTECT, related_name="properties")
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="Cameroon")
    postal_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "properties"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(self.city)
        if self.postal_code:
            parts.append(self.postal_code)
        parts.append(self.country)
        return ", ".join(parts)


class UnitType(models.TextChoices):
    APARTMENT = "apartment", "Apartment"
    STUDIO = "studio", "Studio"
    VILLA = "villa", "Villa"
    OFFICE = "office", "Office"
    SHOP = "shop", "Shop"
    WAREHOUSE = "warehouse", "Warehouse"
    PARKING = "parking", "Parking"
    OTHER = "other", "Other"


class Unit(models.Model):
    building = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="units")
    name = models.CharField(max_length=100)
    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        default=UnitType.APARTMENT,
    )
    floor = models.IntegerField(null=True, blank=True)
    surface_area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("building", "name")]
        ordering = ["building", "name"]

    @property
    def is_occupied(self):
        from tenants.models import LeaseStatus
        return self.leases.filter(status=LeaseStatus.ACTIVE).exists()

    def __str__(self):
        return f"{self.building.name} \u2013 {self.name}"
