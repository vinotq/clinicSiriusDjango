from django.views.generic import TemplateView
from django.shortcuts import redirect, render
from django.utils import timezone
from staff.models import Specialization
from scheduling.models import Appointment

class IndexView(TemplateView):
    """Главная страница приложения."""

    template_name = 'index.html'

    def dispatch(self, request, *args, **kwargs):
        """Перенаправление авторизованных пользователей."""
        if (request.user.is_authenticated and
                request.user.role == 'doctor' and
                hasattr(request.user, 'doctor_profile')):
            return redirect('staff:doctor_home')
        if (request.user.is_authenticated and
                request.user.role == 'admin'):
            return redirect('clinic_admin:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Получение контекста для главной страницы."""
        context = super().get_context_data(**kwargs)

        context['specializations'] = (
            Specialization.objects.only('id', 'name').all()[:4]
        )

        if (self.request.user.is_authenticated and
                hasattr(self.request.user, 'patient_profile')):
            patient = self.request.user.patient_profile
            now = timezone.now()

            family = patient.children()
            all_patients = [patient] + list(family)

            upcoming = Appointment.objects.filter(
                patient__in=all_patients,
                date__gte=now
            ).exclude(
                status=Appointment.STATUS_COMPLETED
            ).select_related(
                'doctor',
                'doctor__user',
                'slot',
                'slot__room',
                'patient'
            ).order_by('date')[:3]

            context['upcoming_appointments'] = upcoming
            context['upcoming_count'] = Appointment.objects.filter(
                patient__in=all_patients,
                date__gte=now
            ).exclude(
                status=Appointment.STATUS_COMPLETED
            ).count()

            context['family_members'] = family
            context['family_count'] = family.count()
            context['patient'] = patient
        return context


def handler400(request, exception):
    """Обработчик ошибки 400 (Bad Request)."""
    return render(request, 'errors/400.html', status=400)


def handler403(request, exception):
    """Обработчик ошибки 403 (Forbidden)."""
    return render(request, 'errors/403.html', status=403)


def handler404(request, exception):
    """
    Обработчик ошибки 404 (Not Found).
    """
    path = request.path
    
    if path.startswith('/static/') or path.startswith('/media/'):
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound()
    
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    """Обработчик ошибки 500 (Internal Server Error)."""
    return render(request, 'errors/500.html', status=500)


def handler503(request, exception=None):
    """Обработчик ошибки 503 (Service Unavailable)."""
    return render(request, 'errors/503.html', status=503)
