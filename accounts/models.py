from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom Django user with an application-specific employee or HR role."""

    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        HR = "hr", "HR"

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Notification(models.Model):
    """A user-owned notification displayed by the frontend notification bell."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=300)
    kind = models.CharField(max_length=30, default="info")
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Newest notifications are shown first without repeating this ordering.
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} - {self.user}"
