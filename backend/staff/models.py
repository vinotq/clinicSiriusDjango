from django.db import models
from django.conf import settings


class Specialization(models.Model):
    """Модель специализации врача."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Doctor(models.Model):
    """Модель врача."""

    fname = models.CharField(max_length=100)
    lname = models.CharField(max_length=100)
    tname = models.CharField(max_length=100, blank=True, null=True)
    bdate = models.DateField()
    phone_number = models.CharField(max_length=11, blank=True, null=True)
    email = models.EmailField()
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.CASCADE
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='doctor_profile'
    )

    class Meta:
        ordering = ['lname', 'fname']

    def __str__(self):
        return f"Доктор {self.lname} {self.fname}"

    def get_short_name(self):
        """Возвращает ФИО в формате 'Фамилия И. О.'"""
        initials = f"{self.fname[0]}." if self.fname else ""
        if self.tname:
            initials += f" {self.tname[0]}."
        return f"{self.lname} {initials}".strip()