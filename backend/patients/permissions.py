from rest_framework.permissions import BasePermission, SAFE_METHODS

ALLOWED_WRITE_ROLES = ('doctor', 'manager', 'admin')


class IsAuthenticatedReadOnlyOrRoleWrite(BasePermission):
    """Разрешает чтение аутентифицированным пользователям.
    Разрешает запись только пользователям с ролью в ALLOWED_WRITE_ROLES.
    """

    def has_permission(self, request, view):
        """Проверка разрешения на уровне запроса."""
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES
        )


class IsOwnerOrStaff(BasePermission):
    """Разрешение для доступа к объектам.
    Разрешает персоналу полный доступ на запись,
    аутентифицированным пользователям - чтение,
    пациентам - редактирование своего профиля или детей.
    Блокирует создание через POST для пациентов.
    """

    def has_permission(self, request, view):
        """Проверка разрешения на уровне запроса."""
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated

        role = getattr(request.user, 'role', None)

        if role in ALLOWED_WRITE_ROLES:
            return True

        if (request.method == 'POST' and
                getattr(view, 'action', None) == 'create'):
            return False

        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Проверка разрешения на уровне объекта."""
        role = getattr(request.user, 'role', None)
        if role in ALLOWED_WRITE_ROLES:
            return True

        if role == 'patient':
            try:
                user_patient = getattr(
                    request.user,
                    'patient_profile',
                    None
                )
            except Exception:
                user_patient = None

            if (user_patient and
                    getattr(obj, 'id', None) == getattr(user_patient, 'id', None)):
                return True

            from .models import PatientGroup
            if user_patient:
                return PatientGroup.objects.filter(
                    parent=user_patient,
                    child=obj
                ).exists()

        return False


class IsPatientOwnerOrStaff(BasePermission):
    """Разрешение для доступа к профилю пациента.
    Разрешает чтение аутентифицированным пользователям,
    запись - персоналу, пациентам - только свой профиль.
    """

    def has_permission(self, request, view):
        """Проверка разрешения на уровне запроса."""
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated

        if getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES:
            return True

        return getattr(request.user, 'role', None) == 'patient'

    def has_object_permission(self, request, view, obj):
        """Проверка разрешения на уровне объекта."""
        if getattr(request.user, 'role', None) in ALLOWED_WRITE_ROLES:
            return True

        return getattr(obj, 'user', None) == request.user