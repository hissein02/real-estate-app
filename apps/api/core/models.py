from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    MANAGER = "manager", "Manager"
    ACCOUNTANT = "accountant", "Accountant"
    AGENT = "agent", "Agent"
    READ_ONLY = "read_only", "Read Only"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READ_ONLY,
    )

    class Meta:
        db_table = "core_user"

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN

    @property
    def can_write(self):
        return self.role in (Role.ADMIN, Role.MANAGER, Role.ACCOUNTANT, Role.AGENT)

    @property
    def can_manage_finance(self):
        return self.role in (Role.ADMIN, Role.MANAGER, Role.ACCOUNTANT)

    def __str__(self):
        full = self.get_full_name()
        return f"{full} ({self.username})" if full else self.username
