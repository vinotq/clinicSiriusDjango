from rest_framework.permissions import BasePermission, SAFE_METHODS

ALLOWED_WRITE_ROLES = ('admin',)

class IsAuthenticatedReadOnlyOrRoleWrite(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES
class IsDoctorOrStaff(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        role = getattr(request.user, 'role', None)
        
        if role in ALLOWED_WRITE_ROLES:
            return True
        if role == 'doctor':
            try:
                user_doctor = getattr(request.user, 'doctor_profile', None)
            except Exception:
                user_doctor = None
            if user_doctor:
                return True
        return False
    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, 'role', None)
        if role in ALLOWED_WRITE_ROLES:
            return True
        if role == 'doctor':
            try:
                user_doctor = getattr(request.user, 'doctor_profile', None)
            except Exception:
                user_doctor = None
            if user_doctor and getattr(obj, 'id', None) == getattr(user_doctor, 'id', None):
                return True
        return False
