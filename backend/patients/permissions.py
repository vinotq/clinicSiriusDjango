from rest_framework.permissions import BasePermission, SAFE_METHODS

ALLOWED_WRITE_ROLES = ('doctor', 'manager', 'admin')

class IsAuthenticatedReadOnlyOrRoleWrite(BasePermission):
    """
    Разрешает чтение аутентифицированным пользователям.
    Разрешает запись только пользователям с ролью в ALLOWED_WRITE_ROLES.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES


class IsOwnerOrStaff(BasePermission):
    """
    Object-level permission to allow staff (doctor/manager/admin) full write access,
    allow authenticated users to read, and allow `patient` users to edit their own
    profile or their children only.
    Also blocks generic POST-create on the view for patients (they should use
    the `create-family-member` action instead).
    """
    def has_permission(self, request, view):
        # Allow read for authenticated users
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated

        role = getattr(request.user, 'role', None)

        # Staff roles allowed to write
        if role in ALLOWED_WRITE_ROLES:
            return True

        # Patients should not be able to POST to the generic create endpoint
        if request.method == 'POST' and getattr(view, 'action', None) == 'create':
            return False

        # Otherwise allow and fallback to object-level checks
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Staff roles can do anything
        role = getattr(request.user, 'role', None)
        if role in ALLOWED_WRITE_ROLES:
            return True

        # For patient role: allow editing own profile
        if role == 'patient':
            # obj may be Patient instance
            try:
                user_patient = getattr(request.user, 'patient_profile', None)
            except Exception:
                user_patient = None

            if user_patient and getattr(obj, 'id', None) == getattr(user_patient, 'id', None):
                return True

            # allow editing if obj is a child of the current user's patient_profile
            from .models import PatientGroup
            if user_patient:
                return PatientGroup.objects.filter(parent=user_patient, child=obj).exists()

        return False
    
# patients/permissions.py
class IsPatientOwnerOrStaff(BasePermission):
    def has_permission(self, request, view):
        # чтение — для аутентифицированных
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # запись — staff/doctor/manager/admin как раньше
        if getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES:
            return True
        # если роль patient, разрешаем только создание family-member через специальный action
        # и разрешаем изменения только для собственных child-entries — проверка в has_object_permission
        return getattr(request.user, 'role', None) == 'patient'

    def has_object_permission(self, request, view, obj):
        # staff/doctor/manager/admin — всегда
        if getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES:
            return True
        # patient может изменять только если obj.user == request.user (его собственный профиль)
        return getattr(obj, 'user', None) == request.user