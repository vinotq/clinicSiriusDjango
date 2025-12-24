from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from patients.models import Patient
from staff.models import Doctor


class Room(models.Model):
    """Модель кабинета."""

    room_number = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.room_number


class AppointmentSchedule(models.Model):
    """Модель расписания приема врача."""

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointmentschedule_set'
    )
    time_from = models.DateTimeField()
    time_to = models.DateTimeField()

    def is_available(self):
        """Проверяет доступность слота для записи."""
        try:
            return not self.appointment
        except ObjectDoesNotExist:
            return True

    def __str__(self):
        return f"{self.doctor.lname} {self.doctor.fname} - {self.time_from}"


class Diagnosis(models.Model):
    """Модель диагноза."""

    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """Модель рецепта/заключения врача."""

    appointment = models.OneToOneField(
        'Appointment',
        on_delete=models.CASCADE,
        related_name='recipe'
    )
    diagnosis = models.ForeignKey(
        Diagnosis,
        on_delete=models.PROTECT
    )
    complaints = models.TextField(blank=True, null=True)
    recommendations = models.TextField(blank=True, null=True)
    next_appointment_slot = models.ForeignKey(
        AppointmentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_appointments'
    )
    referral_doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    referral_slot = models.ForeignKey(
        AppointmentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_appointments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Рецепт для {self.appointment}"


class Appointment(models.Model):
    """Модель записи на прием."""

    STATUS_BOOKED = 'booked'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_BOOKED, 'Забронировано'),
        (STATUS_IN_PROGRESS, 'В процессе'),
        (STATUS_COMPLETED, 'Завершено'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='appointment'
    )
    slot = models.OneToOneField(
        AppointmentSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment'
    )
    date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_BOOKED
    )

    class Meta:
        unique_together = [['patient', 'doctor', 'date']]
        ordering = ['-date']

    def __str__(self):
        return (
            f"{self.patient.lname} {self.patient.fname} - "
            f"{self.doctor.lname} {self.doctor.fname} ({self.date})"
        )
