from core.mixins import DoctorRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Doctor, Specialization
from .serializers import DoctorSerializer, SpecializationSerializer
from .permissions import IsDoctorOrStaff, IsAuthenticatedReadOnlyOrRoleWrite
from patients.models import Patient
from scheduling.models import Appointment

class DoctorViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с врачами."""

    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsDoctorOrStaff]

    def get_queryset(self):
        """Получение queryset с фильтрацией по специализации."""
        queryset = Doctor.objects.all().select_related(
            'user',
            'specialization'
        )

        specialization_id = self.request.query_params.get('specialization')
        if specialization_id:
            queryset = queryset.filter(specialization_id=specialization_id)
        return queryset.order_by('lname')

    @action(
        detail=False,
        methods=['get'],
        url_path='me',
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        """Получение профиля текущего пользователя-врача."""
        doctor_profile = getattr(request.user, 'doctor_profile', None)
        if not doctor_profile:
            return Response(
                {'detail': 'No doctor profile for current user'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = DoctorSerializer(
            doctor_profile,
            context={'request': request}
        )
        return Response(serializer.data)


class SpecializationViewSet(viewsets.ModelViewSet):
    """ViewSet для работы со специализациями."""

    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [IsAuthenticatedReadOnlyOrRoleWrite]

    @action(detail=False, methods=['get'])
    def with_doctors(self, request):
        """Получение специализаций с врачами."""
        specializations = Specialization.objects.all().prefetch_related(
            'doctor_set'
        ).order_by('name')

        result = []
        for spec in specializations:
            doctors = spec.doctor_set.all().order_by('lname', 'fname')
            result.append({
                'id': spec.id,
                'name': spec.name,
                'doctors': [
                    {
                        'id': doctor.id,
                        'fname': doctor.fname,
                        'lname': doctor.lname,
                        'tname': doctor.tname or '',
                        'full_name': (
                            f"{doctor.lname} {doctor.fname}" +
                            (f" {doctor.tname}" if doctor.tname else "")
                        ),
                        'email': doctor.email,
                    }
                    for doctor in doctors
                ]
            })

        return Response(result)


class DoctorHomeView(DoctorRequiredMixin, TemplateView):
    """Главная страница врача."""

    template_name = 'clinic/doctor_home.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для главной страницы врача."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        doctor = user.doctor_profile
        context['doctor'] = doctor

        from scheduling.models import Appointment, AppointmentSchedule
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        today_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )
        today_end = today_start + timedelta(days=1)

        context['today_count'] = Appointment.objects.filter(
            doctor=doctor,
            date__gte=today_start,
            date__lt=today_end
        ).count()

        tomorrow_end = today_end + timedelta(days=1)
        context['upcoming_appointments'] = Appointment.objects.filter(
            doctor=doctor,
            date__gte=now,
            date__lt=tomorrow_end
        ).select_related(
            'patient',
            'slot',
            'slot__room'
        ).order_by('date')[:5]

        context['available_slots_today'] = (
            AppointmentSchedule.objects.filter(
                doctor=doctor,
                appointment__isnull=True,
                time_from__gte=now,
                time_from__date=today_start.date()
            ).select_related('room').order_by('time_from')[:5]
        )

        context['patients_count'] = (
            Appointment.objects.filter(doctor=doctor)
            .values('patient')
            .distinct()
            .count()
        )
        context['total_appointments'] = (
            Appointment.objects.filter(doctor=doctor).count()
        )
        context['available_slots_count'] = (
            AppointmentSchedule.objects.filter(
                doctor=doctor,
                appointment__isnull=True,
                time_from__gte=now
            ).count()
        )

        return context


class DoctorProfileView(DoctorRequiredMixin, TemplateView):
    """Профиль врача."""

    template_name = 'staff/doctor_profile.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для профиля врача."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        doctor = user.doctor_profile
        context['doctor'] = doctor

        from scheduling.models import Appointment
        from django.utils import timezone

        now = timezone.now()
        context['total_appointments'] = (
            Appointment.objects.filter(doctor=doctor).count()
        )
        context['upcoming_appointments_count'] = (
            Appointment.objects.filter(
                doctor=doctor,
                date__gte=now
            ).count()
        )
        context['completed_appointments'] = (
            Appointment.objects.filter(
                doctor=doctor,
                status='completed'
            ).count()
        )

        return context

class DoctorPatientsListView(DoctorRequiredMixin, TemplateView):
    template_name = 'staff/doctor_patients.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        doctor = user.doctor_profile
        context['doctor'] = doctor
        
        from patients.models import Patient
        from scheduling.models import Appointment
        from django.utils import timezone
        from django.core.paginator import Paginator
        
        now = timezone.now()
        
        # Базовый queryset - только пациенты, которые хоть раз были на приёме у этого доктора
        # и у которых предстоящий приём не первый (если есть предстоящий, то должен быть прошедший)
        from django.db.models import Exists, OuterRef
        
        # Проверка наличия прошедших приёмов
        has_past_appointments = Appointment.objects.filter(
            patient=OuterRef('pk'),
            doctor=doctor,
            date__lt=now
        )
        
        # Показываем только пациентов, у которых есть хотя бы один прошедший приём
        # Это гарантирует, что если у пациента есть предстоящий приём, то он не будет первым
        patients = Patient.objects.filter(
            Exists(has_past_appointments)
        ).distinct().select_related('user')
        
        # Поиск
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            patients = patients.filter(
                Q(lname__icontains=search_query) |
                Q(fname__icontains=search_query) |
                Q(tname__icontains=search_query) |
                Q(snils__icontains=search_query) |
                Q(oms__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        
        # Фильтр по статусу посещений
        visit_status = self.request.GET.get('visit_status', '')
        if visit_status:
            if visit_status == 'has_upcoming':
                patients = patients.filter(
                    appointments__doctor=doctor,
                    appointments__date__gte=now,
                    appointments__status__in=['booked', 'in_progress']
                ).distinct()
            elif visit_status == 'completed':
                patients = patients.filter(
                    appointments__doctor=doctor,
                    appointments__status='completed'
                ).distinct()
            elif visit_status == 'no_visits':
                patients = patients.exclude(
                    appointments__doctor=doctor
                )
        
        # Аннотация с данными о посещениях
        patients = patients.annotate(
            total_appointments=Count('appointments', filter=Q(appointments__doctor=doctor)),
            last_appointment_date=Max('appointments__date', filter=Q(appointments__doctor=doctor)),
            upcoming_count=Count('appointments', filter=Q(
                appointments__doctor=doctor,
                appointments__date__gte=now,
                appointments__status__in=['booked', 'in_progress']
            )),
            past_appointments_count=Count('appointments', filter=Q(
                appointments__doctor=doctor,
                appointments__date__lt=now
            ))
        )
        
        # Сортировка
        sort_by = self.request.GET.get('sort', 'lname')
        if sort_by == 'last_visit':
            patients = patients.order_by('-last_appointment_date', 'lname', 'fname')
        elif sort_by == 'total_visits':
            patients = patients.order_by('-total_appointments', 'lname', 'fname')
        else:
            patients = patients.order_by('lname', 'fname')
        
        # Подсказки для поиска (AJAX запрос)
        if self.request.GET.get('suggestions') == '1':
            from django.http import JsonResponse
            suggestions = list(patients[:10].values_list(
                'lname', 'fname', 'tname', 'snils', 'oms', 'email'
            ))
            suggestions_list = []
            for item in suggestions:
                parts = [item[0], item[1]]
                if item[2]:
                    parts.append(item[2])
                suggestions_list.append(' '.join(parts))
                if item[3]:  # СНИЛС
                    suggestions_list.append(item[3])
                if item[4]:  # ОМС
                    suggestions_list.append(item[4])
                if item[5]:  # Email
                    suggestions_list.append(item[5])
            return JsonResponse({'suggestions': suggestions_list[:20]})
        
        # Статистика по приёмам этого доктора
        total_patients = patients.count()
        # Все приёмы только этого доктора
        total_appointments_all = Appointment.objects.filter(doctor=doctor).count()
        # Завершённые приёмы только этого доктора
        completed_appointments_all = Appointment.objects.filter(doctor=doctor, status='completed').count()
        # Предстоящие приёмы только этого доктора
        upcoming_appointments_all = Appointment.objects.filter(
            doctor=doctor,
            date__gte=now,
            status__in=['booked', 'in_progress']
        ).count()
        
        # Пагинация
        paginator = Paginator(patients, 25)
        page = self.request.GET.get('page')
        patients_page = paginator.get_page(page)
        
        context['patients_page'] = patients_page
        context['q'] = search_query
        context['visit_status'] = visit_status
        context['sort'] = sort_by
        context['total_patients'] = total_patients
        context['total_appointments_all'] = total_appointments_all
        context['completed_appointments_all'] = completed_appointments_all
        context['upcoming_appointments_all'] = upcoming_appointments_all
        
        return context


class DoctorPatientDetailView(DoctorRequiredMixin, TemplateView):
    template_name = 'staff/doctor_patient_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        doctor = user.doctor_profile
        patient = get_object_or_404(Patient, pk=kwargs['pk'])
        
        # Проверяем, что у доктора есть приёмы этого пациента
        appointments_count = Appointment.objects.filter(
            doctor=doctor,
            patient=patient
        ).count()
        
        if appointments_count == 0:
            return HttpResponseForbidden('У вас нет приёмов этого пациента')
        
        context['patient'] = patient
        context['doctor'] = doctor
        
        # Получаем только прошедшие приёмы этого пациента у этого доктора
        # Предстоящие приёмы не показываем в истории
        now = timezone.now()
        appointments = Appointment.objects.filter(
            patient=patient,
            doctor=doctor,
            date__lt=now
        ).select_related('slot', 'slot__room', 'doctor', 'doctor__specialization').order_by('-date')
        
        context['appointments'] = appointments
        context['appointments_count'] = appointments.count()
        
        # Статистика (только приёмы этого доктора, все приёмы, не только прошедшие)
        now = timezone.now()
        all_doctor_appointments = Appointment.objects.filter(
            patient=patient,
            doctor=doctor
        )
        context['total_appointments'] = all_doctor_appointments.count()
        context['upcoming_appointments'] = all_doctor_appointments.filter(
            date__gte=now
        ).exclude(status='cancelled').count()
        context['completed_appointments'] = all_doctor_appointments.filter(
            status='completed'
        ).count()
        
        return context


class DoctorsListView(TemplateView):
    template_name = 'staff/doctors_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Фильтрация по специализации
        spec_id = self.request.GET.get('spec')
        doctors_queryset = Doctor.objects.all().select_related('user', 'specialization')
        
        if spec_id:
            doctors_queryset = doctors_queryset.filter(specialization_id=spec_id)
        
        context['doctors'] = doctors_queryset.order_by('lname', 'fname')
        context['specializations'] = Specialization.objects.all().order_by('name')
        context['featured_doctors'] = Doctor.objects.all().select_related('user', 'specialization').order_by('lname', 'fname')[:3]
        return context
class DoctorDetailView(DetailView):
    model = Doctor
    template_name = 'staff/doctor_detail.html'
    context_object_name = 'doctor'
    
    def get_queryset(self):
        return Doctor.objects.select_related('user', 'specialization')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = context['doctor']
        
        from scheduling.models import AppointmentSchedule
        from django.utils import timezone
        
        context['schedule'] = AppointmentSchedule.objects.filter(
            doctor=doctor,
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('room').order_by('time_from')[:10]
        
        return context