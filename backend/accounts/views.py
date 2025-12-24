from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import LoginSerializer, RegistrationSerializer
from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth import login, get_user_model, logout
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.shortcuts import redirect, get_object_or_404, render
from patients.models import Patient, PatientGroup
from django.db import ProgrammingError, OperationalError, IntegrityError
import re
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from core.mixins import PatientRequiredMixin

def validate_username(username):
    errors = []
    
    if len(username) < 3:
        errors.append("Имя пользователя должно быть не менее 3 символов")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors.append("Имя пользователя может содержать только буквы, цифры и подчеркивание")
    
    return errors

def validate_password(password):
    errors = []
    
    if len(password) < 8:
        errors.append("Пароль должен быть не менее 8 символов")
    
    if not re.search(r'[A-Za-z]', password):
        errors.append("Пароль должен содержать хотя бы одну букву")
    
    if not re.search(r'[0-9]', password):
        errors.append("Пароль должен содержать хотя бы одну цифру")
    
    return errors

class RegistrationAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = RegistrationSerializer

    def post(self, request):
        user = request.data.get('user', {})
        
        serializer = self.serializer_class(data=user, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class LoginAPIView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request):
        user = request.data.get('user', {})

        serializer = self.serializer_class(data=user, context={'request': request})
        serializer.is_valid(raise_exception=True)

        email = user.get('email', '').strip().lower()
        password = user.get('password')
        
        User = get_user_model()
        try:
            user_obj = User.objects.get(email__iexact=email)
            if user_obj.check_password(password) and user_obj.is_active:
                login(request, user_obj)
        except User.DoesNotExist:
            pass

        return Response(serializer.data, status=status.HTTP_200_OK)

@method_decorator(require_http_methods(['GET', 'POST']), name='dispatch')
class RegisterTemplateView(TemplateView):
    template_name = 'clinic/register.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.request.GET.get('email', '')
        return context
    
    def post(self, request, *args, **kwargs):
        User = get_user_model()
        
        email = request.POST.get('email', '').strip().lower()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        context = self.get_context_data()
        errors = []
        
        if not email:
            errors.append('Email обязателен')
        elif User.objects.filter(email__iexact=email).exists():
            errors.append('Пользователь с таким email уже существует')
        
        if not username:
            errors.append('Имя пользователя обязательно')
        else:
            username_errors = validate_username(username)
            if username_errors:
                errors.extend(username_errors)
            elif User.objects.filter(username=username).exists():
                errors.append('Пользователь с таким именем уже существует')
        
        if not password:
            errors.append('Пароль обязателен')
        else:
            password_errors = validate_password(password)
            if password_errors:
                errors.extend(password_errors)
        
        if password != password_confirm:
            errors.append('Пароли не совпадают')
        
        if errors:
            context['error'] = ' '.join(errors)
            context['email'] = email
            return self.render_to_response(context)
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='patient'
            )
            
            existing_patient = None
            try:
                existing_patient = Patient.objects.filter(email__iexact=email).first()
            except Patient.DoesNotExist:
                pass
            
            if existing_patient:
                if existing_patient.user is None:
                    existing_patient.user = user
                    existing_patient.email = email
                    existing_patient.save()
                else:
                    Patient.objects.create(
                        user=user,
                        fname='Г. Г.',
                        lname='Швачко',
                        tname='Геннадьевич',
                        bdate='1990-01-01',
                        snils='00000000000',
                        oms='0000000000000000',
                        email=email
                    )
            else:
                Patient.objects.create(
                    user=user,
                    fname='Г. Г.',
                    lname='Швачко',
                    tname='Геннадьевич',
                    bdate='1990-01-01',
                    snils='00000000000',
                    oms='0000000000000000',
                    email=email
                )
            
            login(request, user)
            return redirect('index')
        except IntegrityError as e:
            error_msg = str(e)
            if 'username' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'username' in error_msg:
                context['error'] = 'Пользователь с таким именем уже существует'
            elif 'email' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'email' in error_msg:
                context['error'] = 'Пользователь с таким email уже существует'
            else:
                context['error'] = 'Ошибка при создании профиля: данные уже существуют в базе'
            context['email'] = email
            return self.render_to_response(context)
        except Exception as e:
            context['error'] = f'Ошибка при создании профиля: {str(e)}'
            context['email'] = email
            return self.render_to_response(context)

@method_decorator(require_http_methods(['GET', 'POST']), name='dispatch')
class LoginTemplateView(TemplateView):
    template_name = 'clinic/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        referer = self.request.META.get('HTTP_REFERER', '')
        anchor = ''
        if '#services' in referer:
            anchor = '#services'
        elif '#specializations' in referer:
            anchor = '#specializations'
        elif '#booking' in referer:
            anchor = '#booking'
        elif '#contacts' in referer:
            anchor = '#contacts'
        elif '#care' in referer:
            anchor = '#care'
        elif '#account' in referer:
            anchor = '#account'
        context['redirect_anchor'] = anchor
        return context
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember = request.POST.get('remember')
        anchor = request.POST.get('anchor', '').strip()
        
        context = self.get_context_data()
        
        if not email or not password:
            context['error'] = 'Email и пароль обязательны'
            return self.render_to_response(context)
        
        User = get_user_model()
        try:
            user_obj = User.objects.get(email__iexact=email)
            if user_obj.check_password(password):
                if user_obj.is_active:
                    login(request, user_obj)
                    
                    if not remember:
                        request.session.set_expiry(0)
                    
                    from django.urls import reverse
                    redirect_url = reverse('index')
                    if anchor:
                        redirect_url += anchor
                    return redirect(redirect_url)
                else:
                    context['error'] = 'Ваш аккаунт деактивирован'
            else:
                context['error'] = 'Неверный email или пароль'
        except User.DoesNotExist:
            context['error'] = 'Неверный email или пароль'
        except Exception as e:
            context['error'] = f'Ошибка при входе: {str(e)}'
        
        return self.render_to_response(context)

class LogoutTemplateView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('index')
    
    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect('index')

class ProfileTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
    login_url = 'accounts:login'
    
    def get_template_names(self):
        """Выбираем шаблон в зависимости от роли пользователя"""
        user = self.request.user
        role = getattr(user, 'role', None)
        
        if role == 'doctor':
            return ['accounts/doctor_profile.html', 'accounts/profile.html']
        elif role == 'admin':
            return ['accounts/admin_profile.html', 'accounts/profile.html']
        else:
            return ['accounts/profile.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = getattr(user, 'role', None)
        context['user'] = user
        context['role'] = role
        
        # Для пациентов
        if role == 'patient' and hasattr(user, 'patient_profile'):
            context['patient'] = user.patient_profile
            context['family_members'] = user.patient_profile.children()
            try:
                context['invites'] = list(user.patient_profile.invites.filter(used=False))
            except (ProgrammingError, OperationalError):
                context['invites'] = []
        
        # Для докторов
        elif role == 'doctor' and hasattr(user, 'doctor_profile'):
            from scheduling.models import Appointment
            from django.utils import timezone
            doctor = user.doctor_profile
            context['doctor'] = doctor
            context['total_appointments'] = Appointment.objects.filter(doctor=doctor).count()
            context['upcoming_appointments_count'] = Appointment.objects.filter(
                doctor=doctor,
                date__gte=timezone.now()
            ).exclude(status='cancelled').count()
            context['completed_appointments'] = Appointment.objects.filter(
                doctor=doctor,
                status='completed'
            ).count()
        
        # Для админов
        elif role == 'admin':
            from patients.models import Patient
            from staff.models import Doctor
            from scheduling.models import Appointment
            context['total_patients'] = Patient.objects.count()
            context['total_doctors'] = Doctor.objects.count()
            context['total_appointments'] = Appointment.objects.count()
        
        return context

    def post(self, request, *args, **kwargs):
        user = request.user


        patient = getattr(user, 'patient_profile', None)
        if 'delete_patient' in request.POST and patient:
            try:
                patient.delete()
            except Exception:
                pass
            context = self.get_context_data()
            context['success'] = 'Профиль пациента удалён'
            return self.render_to_response(context)

        if patient:
            fname = request.POST.get('fname', '').strip()
            lname = request.POST.get('lname', '').strip()
            tname = request.POST.get('tname', '').strip()
            bdate = request.POST.get('bdate', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            pemail = request.POST.get('patient_email', '').strip()
            snils = request.POST.get('snils', '').strip()
            oms = request.POST.get('oms', '').strip()

            if not fname:
                context = self.get_context_data()
                context['error'] = 'Имя обязательно для заполнения'
                return self.render_to_response(context)
            if not lname:
                context = self.get_context_data()
                context['error'] = 'Фамилия обязательна для заполнения'
                return self.render_to_response(context)
            if not snils:
                context = self.get_context_data()
                context['error'] = 'СНИЛС обязателен для заполнения'
                return self.render_to_response(context)
            if not oms:
                context = self.get_context_data()
                context['error'] = 'Полис ОМС обязателен для заполнения'
                return self.render_to_response(context)
            if not bdate:
                context = self.get_context_data()
                context['error'] = 'Дата рождения обязательна для заполнения'
                return self.render_to_response(context)

                patient.fname = fname
                patient.lname = lname
            patient.tname = tname if tname else None
            
            if phone:
                phone_digits = re.sub(r'\D', '', phone)
                patient.phone_number = phone_digits[:11] if phone_digits else None
            else:
                patient.phone_number = None
            
            patient.email = pemail if pemail else None
            patient.snils = snils
            patient.oms = oms
            
            try:
                from datetime import datetime
                patient.bdate = datetime.strptime(bdate, '%Y-%m-%d').date()
            except Exception as e:
                context = self.get_context_data()
                context['error'] = f'Неверный формат даты рождения: {str(e)}'
                return self.render_to_response(context)
            
            try:
                patient.save()
            except IntegrityError as e:
                error_msg = str(e)
                context = self.get_context_data()
                if 'snils' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'snils' in error_msg:
                    context['error'] = 'Пациент с таким СНИЛС уже существует'
                elif 'oms' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'oms' in error_msg:
                    context['error'] = 'Пациент с таким ОМС уже существует'
                else:
                    context['error'] = 'Ошибка при сохранении: данные уже существуют в базе'
                return self.render_to_response(context)
            except Exception as e:
                context = self.get_context_data()
                context['error'] = f'Ошибка при сохранении: {str(e)}'
                return self.render_to_response(context)

        context = self.get_context_data()
        context['success'] = 'Данные сохранены'
        return self.render_to_response(context)

class SettingsTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/settings.html'
    login_url = 'accounts:login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context
    
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')

        context = self.get_context_data()
        action = request.POST.get('action', '')
        user = request.user

        if action == 'update_account':
            email = request.POST.get('email', '').strip()
            username = request.POST.get('username', '').strip()

            if not email or not username:
                context['account_error'] = 'Email и имя пользователя обязательны'
                return self.render_to_response(context)

            if email != user.email:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                    context['account_error'] = 'Этот email уже используется'
                    return self.render_to_response(context)

            if username != user.username:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                    context['account_error'] = 'Это имя пользователя уже занято'
                    return self.render_to_response(context)

            try:
                user.email = email
                user.username = username
                user.save()
                context['account_success'] = 'Данные аккаунта успешно обновлены'
            except IntegrityError as e:
                error_msg = str(e)
                if 'username' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'username' in error_msg:
                    context['account_error'] = 'Это имя пользователя уже занято'
                elif 'email' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'email' in error_msg:
                    context['account_error'] = 'Этот email уже используется'
                else:
                    context['account_error'] = 'Ошибка при обновлении данных: данные уже существуют в базе'
            except Exception as e:
                context['account_error'] = f'Ошибка при обновлении данных: {str(e)}'

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            new_password_confirm = request.POST.get('new_password_confirm', '')

            if not current_password or not new_password:
                context['password_error'] = 'Заполните все поля'
                return self.render_to_response(context)

            if not user.check_password(current_password):
                context['password_error'] = 'Неверный текущий пароль'
                return self.render_to_response(context)

            if new_password != new_password_confirm:
                context['password_error'] = 'Пароли не совпадают'
                return self.render_to_response(context)

            if len(new_password) < 8:
                context['password_error'] = 'Пароль должен содержать минимум 8 символов'
                return self.render_to_response(context)

            try:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)
                context['password_success'] = 'Пароль успешно изменён'
            except Exception as e:
                context['password_error'] = f'Ошибка при смене пароля: {str(e)}'

        elif action == 'delete_account':
            from django.contrib.auth import logout
            try:
                logout(request)
                user.delete()
                return redirect('index')
            except Exception as e:
                context['account_error'] = f'Ошибка при удалении аккаунта: {str(e)}'

        return self.render_to_response(context)
    
class ChangeLoginView(TemplateView):
    template_name = 'accounts/change_login.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')

        context = self.get_context_data()
        new_username = request.POST.get('new_username', '').strip()

        if not new_username:
            context['error'] = 'Имя пользователя не указано'
            return self.render_to_response(context)

        username_errors = validate_username(new_username)
        if username_errors:
            context['error'] = ' '.join(username_errors)
            return self.render_to_response(context)

        User = get_user_model()
        if User.objects.filter(username=new_username).exists():
            context['error'] = 'Пользователь с таким именем уже существует'
            return self.render_to_response(context)

        try:
            user = request.user
            user.username = new_username
            user.save()
            context['success'] = 'Имя пользователя успешно изменено'
        except IntegrityError as e:
            error_msg = str(e)
            if 'username' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'username' in error_msg:
                context['error'] = 'Пользователь с таким именем уже существует'
            else:
                context['error'] = 'Ошибка при смене имени пользователя: данные уже существуют в базе'
        except Exception as e:
            context['error'] = f'Ошибка при смене имени пользователя: {str(e)}'

        return self.render_to_response(context)
    
class DeleteAccountView(TemplateView):
    template_name = 'accounts/delete_account.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')

        context = self.get_context_data()
        try:
            user = request.user
            logout(request)
            user.delete()
            return redirect('index')
        except Exception as e:
            context['error'] = f'Ошибка при удалении аккаунта: {str(e)}'
            return self.render_to_response(context)


class EditFamilyMemberView(PatientRequiredMixin, View):
    login_url = 'accounts:login'
    template_name = 'accounts/edit_family_member.html'
    
    def get(self, request, member_id):
        user = request.user
        if not hasattr(user, 'patient_profile'):
            return redirect('accounts:profile')
        
        patient = user.patient_profile
        member = get_object_or_404(Patient, pk=member_id)
        
        if not PatientGroup.objects.filter(parent=patient, child=member).exists():
            return redirect('accounts:profile')
        
        context = {
            'member': member,
            'patient': patient,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, member_id):
        user = request.user
        if not hasattr(user, 'patient_profile'):
            return redirect('accounts:profile')
        
        patient = user.patient_profile
        member = get_object_or_404(Patient, pk=member_id)
        
        if not PatientGroup.objects.filter(parent=patient, child=member).exists():
            return redirect('accounts:profile')
        
        fname = request.POST.get('fname', '').strip()
        lname = request.POST.get('lname', '').strip()
        tname = request.POST.get('tname', '').strip()
        bdate = request.POST.get('bdate', '').strip()
        phone = request.POST.get('phone_number', '').strip()
        pemail = request.POST.get('patient_email', '').strip()
        snils = request.POST.get('snils', '').strip()
        oms = request.POST.get('oms', '').strip()
        
        errors = []
        if not fname:
            errors.append('Имя обязательно для заполнения')
        if not lname:
            errors.append('Фамилия обязательна для заполнения')
        if not snils:
            errors.append('СНИЛС обязателен для заполнения')
        if not oms:
            errors.append('Полис ОМС обязателен для заполнения')
        if not bdate:
            errors.append('Дата рождения обязательна для заполнения')
        
        if errors:
            context = {
                'member': member,
                'patient': patient,
                'error': '; '.join(errors)
            }
            return render(request, self.template_name, context)
        
        member.fname = fname
        member.lname = lname
        member.tname = tname if tname else None
        
        if phone:
            phone_digits = re.sub(r'\D', '', phone)
            member.phone_number = phone_digits[:11] if phone_digits else None
        else:
            member.phone_number = None
        
        member.email = pemail if pemail else None
        member.snils = snils
        member.oms = oms
        
        try:
            from datetime import datetime
            member.bdate = datetime.strptime(bdate, '%Y-%m-%d').date()
        except Exception as e:
            context = {
                'member': member,
                'patient': patient,
                'error': f'Неверный формат даты рождения: {str(e)}'
            }
            return render(request, self.template_name, context)
        
        try:
            member.save()
            return redirect('accounts:profile?success=Данные члена семьи успешно обновлены')
        except IntegrityError as e:
            error_msg = str(e)
            context = {
                'member': member,
                'patient': patient,
            }
            if 'snils' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'snils' in error_msg:
                context['error'] = 'Пациент с таким СНИЛС уже существует'
            elif 'oms' in error_msg.lower() or 'unique constraint' in error_msg.lower() and 'oms' in error_msg:
                context['error'] = 'Пациент с таким ОМС уже существует'
            else:
                context['error'] = 'Ошибка при сохранении: данные уже существуют в базе'
            return render(request, self.template_name, context)
        except Exception as e:
            context = {
                'member': member,
                'patient': patient,
                'error': f'Ошибка при сохранении: {str(e)}'
            }
            return render(request, self.template_name, context)