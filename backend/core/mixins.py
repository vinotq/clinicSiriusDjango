from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from django.shortcuts import redirect

class RoleRequiredMixin(AccessMixin):
    required_role = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.required_role and request.user.role != self.required_role:
            if request.user.role == 'doctor':
                return redirect('staff:doctor_home')
            elif request.user.role == 'patient':
                return redirect('index')
            elif request.user.role == 'admin':
                return redirect('clinic_admin:dashboard')
            else:
                return redirect('index')
        return super().dispatch(request, *args, **kwargs)
    def handle_no_permission(self):
        return redirect('accounts:login')
class DoctorRequiredMixin(LoginRequiredMixin, RoleRequiredMixin):
    required_role = 'doctor'
    login_url = 'accounts:login'
class PatientRequiredMixin(LoginRequiredMixin, RoleRequiredMixin):
    required_role = 'patient'
    login_url = 'accounts:login'
class AdminRequiredMixin(LoginRequiredMixin, RoleRequiredMixin):
    required_role = 'admin'
    login_url = 'accounts:login'

class AdminOrDoctorRequiredMixin(LoginRequiredMixin, AccessMixin):
    """Миксин для доступа админов и докторов"""
    login_url = 'accounts:login'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        role = getattr(request.user, 'role', None)
        if role not in ('admin', 'doctor'):
            if role == 'patient':
                return redirect('index')
            else:
                return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    
    def handle_no_permission(self):
        return redirect('accounts:login')
