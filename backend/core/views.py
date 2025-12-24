from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.utils import timezone
from staff.models import Specialization
from scheduling.models import Appointment

class IndexView(TemplateView):
    template_name = 'index.html'
    
    def dispatch(self, request, *args, **kwargs):
        
        if request.user.is_authenticated and request.user.role == 'doctor' and hasattr(request.user, 'doctor_profile'):
            return redirect('staff:doctor_home')
        if request.user.is_authenticated and request.user.role == 'admin':
            return redirect('clinic_admin:dashboard')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['specializations'] = Specialization.objects.only('id', 'name').all()[:4]
        

        if self.request.user.is_authenticated and hasattr(self.request.user, 'patient_profile'):
            patient = self.request.user.patient_profile
            now = timezone.now()
            

            family = patient.children()
            all_patients = [patient] + list(family)
            

            upcoming = Appointment.objects.filter(
                patient__in=all_patients,
                date__gte=now
            ).exclude(
                status=Appointment.STATUS_COMPLETED
            ).select_related('doctor', 'doctor__user', 'slot', 'slot__room', 'patient').order_by('date')[:3]
            
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
