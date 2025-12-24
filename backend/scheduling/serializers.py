from rest_framework import serializers
from .models import AppointmentSchedule, Appointment
from staff.models import Doctor
from patients.models import Patient


class AppointmentScheduleSerializer(serializers.ModelSerializer):
    """Сериализатор расписания приема."""

    is_available = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    room_number = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentSchedule
        fields = [
            'id',
            'doctor',
            'doctor_name',
            'room',
            'room_number',
            'time_from',
            'time_to',
            'is_available'
        ]

    def get_is_available(self, obj):
        """Проверка доступности слота."""
        return obj.is_available()

    def get_doctor_name(self, obj):
        """Получение имени врача."""
        return f"{obj.doctor.fname} {obj.doctor.lname}"

    def get_room_number(self, obj):
        """Получение номера кабинета."""
        return obj.room.room_number


class AppointmentSerializer(serializers.ModelSerializer):
    """Сериализатор записи на прием."""

    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient',
            'patient_name',
            'doctor',
            'doctor_name',
            'slot',
            'date',
            'status',
            'status_display'
        ]

    def get_doctor_name(self, obj):
        """Получение имени врача."""
        return f"{obj.doctor.fname} {obj.doctor.lname}"

    def get_patient_name(self, obj):
        """Получение имени пациента."""
        return f"{obj.patient.fname} {obj.patient.lname}"

    def get_status_display(self, obj):
        """Получение отображаемого статуса."""
        return obj.get_status_display()
