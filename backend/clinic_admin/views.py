from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.db import IntegrityError
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date
from collections import defaultdict
import json

from core.mixins import AdminRequiredMixin
from patients.models import Patient, PatientGroup
from staff.models import Doctor, Specialization
from scheduling.models import Appointment, AppointmentSchedule, Room, Recipe
from accounts.models import User
from .utils import parse_date_ddmmyyyy

from .views_patients import (
    PatientListView, PatientCreateView, PatientEditView, 
    PatientDetailView, PatientDeleteView, FamilyListView, FamilyDetailView,
    PatientBookView, FamilyCreateView, FamilyAddMemberView, FamilyRemoveMemberView
)

from .views_doctors import (
    DoctorListView, DoctorCreateView, DoctorEditView,
    DoctorDetailView, DoctorDeleteView
)

class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Главная панель администратора."""

    template_name = 'clinic_admin/dashboard.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для панели администратора."""
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        today_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        today_end = today_start + timedelta(days=1)

        context['patients_count'] = Patient.objects.count()
        context['doctors_count'] = Doctor.objects.count()
        context['today_appointments'] = Appointment.objects.filter(
            date__gte=today_start,
            date__lt=today_end
        ).count()

        return context


class AnalyticsView(AdminRequiredMixin, TemplateView):
    """Представление аналитики клиники."""

    template_name = 'clinic_admin/analytics.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для страницы аналитики."""
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        today = now.date()

        start_date_str = self.request.GET.get('start_date', '').strip()
        end_date_str = self.request.GET.get('end_date', '').strip()

        if start_date_str:
            parsed_date = None
            try:
                if '-' in start_date_str:
                    parsed_date = datetime.strptime(
                        start_date_str,
                        '%Y-%m-%d'
                    ).date()
                else:
                    parsed_date = parse_date_ddmmyyyy(start_date_str)
            except (ValueError, TypeError):
                pass
            if parsed_date:
                start_date = parsed_date
            else:
                start_date = today - timedelta(days=30)
        else:
            days_back_str = self.request.GET.get('days', '30')
            try:
                days_back = int(days_back_str)
            except (ValueError, TypeError):
                days_back = 30
            start_date = today - timedelta(days=days_back)
        if end_date_str:
            parsed_date = None
            try:
                if '-' in end_date_str:
                    parsed_date = datetime.strptime(
                        end_date_str,
                        '%Y-%m-%d'
                    ).date()
                else:
                    parsed_date = parse_date_ddmmyyyy(end_date_str)
            except (ValueError, TypeError):
                pass
            if parsed_date:
                end_date = parsed_date
            else:
                end_date = today
        else:
            end_date = today
        if start_date > end_date:
            start_date = end_date - timedelta(days=30)
        filter_doctor = self.request.GET.get('doctor', '').strip()
        filter_status = self.request.GET.get('status', '').strip()
        filter_specialization = self.request.GET.get('specialization', '').strip()
        


        base_appointments_qs = Appointment.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        )
        

        appointments_qs = base_appointments_qs
        if filter_doctor:
            appointments_qs = appointments_qs.filter(doctor_id=filter_doctor)
        if filter_status:
            appointments_qs = appointments_qs.filter(status=filter_status)
        if filter_specialization:
            appointments_qs = appointments_qs.filter(doctor__specialization_id=filter_specialization)
        status_base_qs = base_appointments_qs
        if filter_doctor:
            status_base_qs = status_base_qs.filter(doctor_id=filter_doctor)
        if filter_specialization:
            status_base_qs = status_base_qs.filter(
                doctor__specialization_id=filter_specialization
            )
        context['total_appointments'] = appointments_qs.count()
        context['appointments_by_status'] = {
            'booked': status_base_qs.filter(status='booked').count(),
            'in_progress': status_base_qs.filter(
                status='in_progress'
            ).count(),
            'completed': status_base_qs.filter(status='completed').count(),
        }

        appointments_by_day = defaultdict(int)
        
        for appt in appointments_qs.all():
            if appt.date:
                day = appt.date.date().isoformat()
                appointments_by_day[day] += 1
        all_days = []
        current_date = start_date
        while current_date <= end_date:
            all_days.append(current_date.isoformat())
            current_date += timedelta(days=1)
        sorted_days = sorted(all_days)
        
        formatted_days = []
        chart_data = []
        for day_str in sorted_days:
            try:
                day_obj = datetime.strptime(day_str, '%Y-%m-%d').date()
                formatted_days.append(day_obj.strftime('%d.%m.%Y'))
                
                chart_data.append(appointments_by_day.get(day_str, 0))
            except (ValueError, TypeError):
                continue
        context['appointments_chart_labels'] = json.dumps(
            formatted_days,
            ensure_ascii=False
        )
        context['appointments_chart_data'] = json.dumps(
            chart_data,
            ensure_ascii=False
        )

        doctors_appointments_qs = Appointment.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        )

        if filter_doctor:
            doctors_appointments_qs = doctors_appointments_qs.filter(doctor_id=filter_doctor)
        if filter_status:
            doctors_appointments_qs = doctors_appointments_qs.filter(status=filter_status)
        if filter_specialization:
            doctors_appointments_qs = doctors_appointments_qs.filter(doctor__specialization_id=filter_specialization)
        doctor_ids = list(doctors_appointments_qs.values_list('doctor_id', flat=True).distinct())
        if doctor_ids:
            doctors_qs = Doctor.objects.filter(pk__in=doctor_ids)
            if filter_specialization:
                doctors_qs = doctors_qs.filter(specialization_id=filter_specialization)
            doctors_stats = doctors_qs.annotate(
                appointments_count=Count('appointment', filter=Q(
                    appointment__in=doctors_appointments_qs
                )),
                completed_count=Count('appointment', filter=Q(
                    appointment__in=doctors_appointments_qs.filter(status='completed')
                ))
            ).order_by('-appointments_count')[:10]
        else:
            doctors_stats = Doctor.objects.none()
        context['top_doctors'] = doctors_stats
        
        context['doctors_chart_labels'] = json.dumps([d.get_short_name() for d in doctors_stats])
        context['doctors_chart_data'] = json.dumps([d.appointments_count for d in doctors_stats])
        
        context['doctors_tooltip_data'] = json.dumps([
            {
                'name': d.get_short_name(),
                'specialization': d.specialization.name,
                'count': d.appointments_count
            } for d in doctors_stats
        ]) if doctors_stats else json.dumps([])
        

        specs_appointments_qs = Appointment.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        )
        

        if filter_doctor:
            specs_appointments_qs = specs_appointments_qs.filter(doctor_id=filter_doctor)
        if filter_status:
            specs_appointments_qs = specs_appointments_qs.filter(status=filter_status)
        if filter_specialization:
            specs_appointments_qs = specs_appointments_qs.filter(
                doctor__specialization_id=filter_specialization
            )
        specializations_stats = Specialization.objects.annotate(
            doctors_count=Count('doctor'),
            appointments_count=Count(
                'doctor__appointment',
                filter=Q(doctor__appointment__in=specs_appointments_qs)
            )
        ).order_by('-appointments_count')

        context['specializations_stats'] = specializations_stats
        context['specs_chart_labels'] = json.dumps(
            [s.name for s in specializations_stats[:10]]
        )
        context['specs_chart_data'] = json.dumps(
            [s.appointments_count for s in specializations_stats[:10]]
        )

        context['total_patients'] = Patient.objects.count()

        days_in_period = (end_date - start_date).days
        if days_in_period > 0:
            estimated_new = int(
                Patient.objects.count() * (days_in_period / 365)
            )
            context['new_patients_last_month'] = min(
                estimated_new,
                Patient.objects.count()
            )
        else:
            context['new_patients_last_month'] = 0
        rooms_appointments_qs = Appointment.objects.filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        )

        if filter_doctor:
            rooms_appointments_qs = rooms_appointments_qs.filter(doctor_id=filter_doctor)
        if filter_status:
            rooms_appointments_qs = rooms_appointments_qs.filter(status=filter_status)
        if filter_specialization:
            rooms_appointments_qs = rooms_appointments_qs.filter(
                doctor__specialization_id=filter_specialization
            )
        rooms_stats = Room.objects.annotate(
            slots_count=Count(
                'appointmentschedule_set',
                filter=Q(
                    appointmentschedule_set__time_from__date__gte=start_date,
                    appointmentschedule_set__time_from__date__lte=end_date
                )
            ),
            booked_count=Count(
                'appointmentschedule_set__appointment',
                filter=Q(
                    appointmentschedule_set__appointment__in=rooms_appointments_qs
                )
            )
        ).order_by('-booked_count')

        context['rooms_stats'] = rooms_stats
        context['rooms_chart_labels'] = json.dumps(
            [f"Кабинет {r.room_number}" for r in rooms_stats]
        )
        context['rooms_chart_data'] = json.dumps(
            [r.booked_count for r in rooms_stats]
        )

        hour_counts = defaultdict(int)
        for appt in appointments_qs:
            hour = appt.date.hour
            hour_counts[hour] += 1
        context['hours_chart_labels'] = json.dumps(
            [f"{h}:00" for h in range(6, 22)]
        )
        context['hours_chart_data'] = json.dumps(
            [hour_counts.get(h, 0) for h in range(6, 22)]
        )

        context['start_date'] = start_date
        context['end_date'] = end_date
        context['start_date_str'] = start_date.strftime('%d.%m.%Y')
        context['end_date_str'] = end_date.strftime('%d.%m.%Y')

        context['filter_doctor'] = filter_doctor
        context['filter_status'] = filter_status
        context['filter_specialization'] = filter_specialization

        context['doctors_list'] = Doctor.objects.all().order_by(
            'lname',
            'fname'
        )
        context['specializations_list'] = (
            Specialization.objects.all().order_by('name')
        )

        if 'appointments_chart_labels' not in context:
            context['appointments_chart_labels'] = json.dumps([], ensure_ascii=False)
        if 'appointments_chart_data' not in context:
            context['appointments_chart_data'] = json.dumps([], ensure_ascii=False)
        if 'doctors_chart_labels' not in context:
            context['doctors_chart_labels'] = json.dumps([], ensure_ascii=False)
        if 'doctors_chart_data' not in context:
            context['doctors_chart_data'] = json.dumps([], ensure_ascii=False)
        if 'specs_chart_labels' not in context:
            context['specs_chart_labels'] = json.dumps([], ensure_ascii=False)
        if 'specs_chart_data' not in context:
            context['specs_chart_data'] = json.dumps([], ensure_ascii=False)
        if 'rooms_chart_labels' not in context:
            context['rooms_chart_labels'] = json.dumps([], ensure_ascii=False)
        if 'rooms_chart_data' not in context:
            context['rooms_chart_data'] = json.dumps([], ensure_ascii=False)
        if 'hours_chart_labels' not in context:
            context['hours_chart_labels'] = json.dumps([], ensure_ascii=False)
        if 'hours_chart_data' not in context:
            context['hours_chart_data'] = json.dumps([], ensure_ascii=False)
        return context


class ClinicScheduleView(AdminRequiredMixin, TemplateView):
    """Расписание клиники с фильтрацией."""

    template_name = 'clinic_admin/schedule/clinic_schedule.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для расписания клиники."""
        context = super().get_context_data(**kwargs)

        date_from_str = self.request.GET.get('date_from', '').strip()
        date_to_str = self.request.GET.get('date_to', '').strip()
        doctor_id = self.request.GET.get('doctor', '').strip()
        room_id = self.request.GET.get('room', '').strip()
        status = self.request.GET.get('status', '').strip()
        patient_search = self.request.GET.get('patient', '').strip()

        date_from = None
        date_to = None
        if date_from_str:
            date_from = parse_date_ddmmyyyy(date_from_str)
        if date_to_str:
            date_to = parse_date_ddmmyyyy(date_to_str)

        slots_qs = AppointmentSchedule.objects.all().select_related(
            'doctor',
            'doctor__specialization',
            'room',
            'appointment',
            'appointment__patient'
        )
        if date_from:
            slots_qs = slots_qs.filter(time_from__date__gte=date_from)
        if date_to:
            slots_qs = slots_qs.filter(time_from__date__lte=date_to)
        if doctor_id:
            slots_qs = slots_qs.filter(doctor_id=doctor_id)
        if room_id:
            slots_qs = slots_qs.filter(room_id=room_id)
        if status:
            slots_qs = slots_qs.filter(appointment__status=status)
        if patient_search:
            slots_qs = slots_qs.filter(
                Q(appointment__isnull=False) & (
                    Q(appointment__patient__lname__icontains=patient_search) |
                    Q(appointment__patient__fname__icontains=patient_search) |
                    Q(appointment__patient__email__icontains=patient_search)
                )
            )

        slots_qs = slots_qs.order_by(
            'time_from',
            'doctor__lname',
            'doctor__fname'
        )

        schedule_dict = defaultdict(lambda: defaultdict(list))

        for slot in slots_qs:
            date_key = slot.time_from.date().isoformat()
            doctor_key = slot.doctor.pk
            schedule_dict[date_key][doctor_key].append(slot)

        day_names_short = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        schedule_list = []
        for date_str in sorted(schedule_dict.keys()):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            doctors_list = []

            doctors_data = []
            for doctor_id, slots in schedule_dict[date_str].items():
                slots_sorted = sorted(slots, key=lambda s: s.time_from)
                doctor = slots_sorted[0].doctor
                doctors_data.append({
                    'doctor': doctor,
                    'slots': slots_sorted,
                    'total_count': len(slots_sorted)
                })

            doctors_data.sort(
                key=lambda d: (d['doctor'].lname, d['doctor'].fname)
            )
            doctors_list = doctors_data
            
            schedule_list.append({
                'date': date_obj,
                'date_str': date_str,
                'day_name_short': day_names_short[date_obj.weekday()],
                'doctors': doctors_list
            })

        appointments_qs = Appointment.objects.all().select_related(
            'patient',
            'doctor',
            'doctor__specialization',
            'slot',
            'slot__room'
        )

        if date_from:
            appointments_qs = appointments_qs.filter(
                date__date__gte=date_from
            )
        if date_to:
            appointments_qs = appointments_qs.filter(date__date__lte=date_to)
        if doctor_id:
            appointments_qs = appointments_qs.filter(doctor_id=doctor_id)
        if room_id:
            appointments_qs = appointments_qs.filter(slot__room_id=room_id)
        if patient_search:
            appointments_qs = appointments_qs.filter(
                Q(patient__lname__icontains=patient_search) |
                Q(patient__fname__icontains=patient_search) |
                Q(patient__email__icontains=patient_search)
            )

        base_appointments_qs = appointments_qs

        if status:
            appointments_qs = appointments_qs.filter(status=status)

        paginator = Paginator(schedule_list, 7)
        page = self.request.GET.get('page', 1)
        schedule_page = paginator.get_page(page)

        context['total_count'] = appointments_qs.count()
        context['booked_count'] = (
            base_appointments_qs.filter(status='booked').count()
        )
        context['in_progress_count'] = (
            base_appointments_qs.filter(status='in_progress').count()
        )
        context['completed_count'] = (
            base_appointments_qs.filter(status='completed').count()
        )

        context['date_from'] = date_from_str
        context['date_to'] = date_to_str
        context['selected_doctor_id'] = doctor_id
        context['selected_room_id'] = room_id
        context['selected_status'] = status
        context['patient_search'] = patient_search

        context['doctors'] = Doctor.objects.all().order_by('lname', 'fname')
        context['rooms'] = Room.objects.all().order_by('room_number')
        context['status_choices'] = Appointment.STATUS_CHOICES

        context['schedule_page'] = schedule_page
        
        return context


class AppointmentUpdateStatusView(AdminRequiredMixin, View):
    """Представление для обновления статуса приема."""

    def post(self, request, *args, **kwargs):
        """Обработка POST запроса на обновление статуса."""
        appointment_id = request.POST.get('appointment_id')
        new_status = request.POST.get('status')

        if not appointment_id or not new_status:
            messages.error(request, 'Не указаны необходимые параметры')
            return redirect('clinic_admin:clinic_schedule')

        if new_status not in dict(Appointment.STATUS_CHOICES).keys():
            messages.error(request, 'Некорректный статус')
            return redirect('clinic_admin:clinic_schedule')

        try:
            appointment = get_object_or_404(Appointment, pk=appointment_id)
            old_status = appointment.status
            appointment.status = new_status

            if new_status == 'cancelled' and appointment.slot:
                slot = appointment.slot
                appointment.slot = None
                appointment.save()
            else:
                appointment.save()

            status_display = dict(Appointment.STATUS_CHOICES)[new_status]
            messages.success(
                request,
                f'Статус приема изменен с '
                f'"{dict(Appointment.STATUS_CHOICES)[old_status]}" '
                f'на "{status_display}"'
            )
        except Exception as e:
            messages.error(
                request,
                f'Ошибка при изменении статуса: {str(e)}'
            )

        referer = request.META.get('HTTP_REFERER', '/admin-panel/schedule/')
        return redirect(referer)


class AppointmentResultsView(AdminRequiredMixin, TemplateView):
    """Представление результатов приема."""

    template_name = 'clinic_admin/appointments/results.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для результатов приема."""
        context = super().get_context_data(**kwargs)
        appointment = get_object_or_404(
            Appointment.objects.select_related(
                'patient',
                'doctor',
                'doctor__specialization',
                'slot',
                'slot__room'
            ),
            pk=kwargs['pk']
        )

        context['appointment'] = appointment

        try:
            recipe = appointment.recipe
            recipe = Recipe.objects.select_related(
                'diagnosis',
                'next_appointment_slot',
                'next_appointment_slot__room',
                'next_appointment_slot__doctor',
                'referral_doctor',
                'referral_doctor__specialization',
                'referral_slot',
                'referral_slot__room'
            ).get(appointment=appointment)
            context['recipe'] = recipe
        except Recipe.DoesNotExist:
            context['recipe'] = None

        return context
