from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.contrib import messages
from django.db import IntegrityError, DatabaseError
from django.urls import reverse
from datetime import datetime, timedelta
from collections import defaultdict

from core.mixins import AdminRequiredMixin, AdminOrDoctorRequiredMixin
from patients.models import Patient, PatientGroup
from scheduling.models import Appointment, AppointmentSchedule
from staff.models import Doctor
from django.utils import timezone
import json
from .utils import parse_date_ddmmyyyy

class PatientListView(AdminOrDoctorRequiredMixin, TemplateView):
    """Список пациентов."""

    template_name = 'clinic_admin/patients/list.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для списка пациентов."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = getattr(user, 'role', None)

        doctor = None
        if role == 'doctor':
            doctor = getattr(user, 'doctor_profile', None)

        if doctor:
            patients = Patient.objects.filter(
                appointments__doctor=doctor
            ).distinct().select_related('user')
        else:
            patients = Patient.objects.all().select_related('user')

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

        visit_status = self.request.GET.get('visit_status', '')
        if visit_status and doctor:
            if visit_status == 'has_upcoming':
                patients = patients.filter(
                    appointments__doctor=doctor,
                    appointments__date__gte=timezone.now(),
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

        if doctor:
            patients = patients.annotate(
                total_appointments=Count(
                    'appointments',
                    filter=Q(appointments__doctor=doctor)
                ),
                last_appointment_date=Max(
                    'appointments__date',
                    filter=Q(appointments__doctor=doctor)
                ),
                upcoming_count=Count(
                    'appointments',
                    filter=Q(
                        appointments__doctor=doctor,
                        appointments__date__gte=timezone.now(),
                        appointments__status__in=['booked', 'in_progress']
                    )
                )
            )

        sort_by = self.request.GET.get('sort', 'lname')
        if sort_by == 'last_visit':
            patients = patients.order_by(
                '-last_appointment_date',
                'lname',
                'fname'
            )
        elif sort_by == 'total_visits':
            patients = patients.order_by(
                '-total_appointments',
                'lname',
                'fname'
            )
        else:
            patients = patients.order_by('lname', 'fname')

        if self.request.GET.get('suggestions') == '1':
            from django.http import JsonResponse
            suggestions = list(patients[:10].values_list(
                'lname',
                'fname',
                'tname',
                'snils',
                'oms',
                'email'
            ))
            suggestions_list = []
            for item in suggestions:
                parts = [item[0], item[1]]
                if item[2]:
                    parts.append(item[2])
                suggestions_list.append(' '.join(parts))
                if item[3]:
                    suggestions_list.append(item[3])
                if item[4]:
                    suggestions_list.append(item[4])
                if item[5]:
                    suggestions_list.append(item[5])
            return JsonResponse({'suggestions': suggestions_list[:20]})

        paginator = Paginator(patients, 25)
        page = self.request.GET.get('page')
        patients_page = paginator.get_page(page)
        
        context['patients_page'] = patients_page
        context['q'] = search_query
        context['visit_status'] = visit_status
        context['sort'] = sort_by
        context['is_doctor'] = doctor is not None
        context['doctor'] = doctor
        
        return context


class PatientCreateView(AdminRequiredMixin, TemplateView):
    """Создание нового пациента."""

    template_name = 'clinic_admin/patients/form.html'

    def get(self, request, *args, **kwargs):
        """Обработка GET запроса для создания пациента."""
        return render(request, self.template_name, {'action': 'create'})
    
    def post(self, request, *args, **kwargs):
        try:
            bdate = parse_date_ddmmyyyy(request.POST.get('bdate'))
            if not bdate:
                return render(request, self.template_name, {
                    'action': 'create',
                    'error': 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ'
                })
            patient = Patient.objects.create(
                lname=request.POST.get('lname', '').strip(),
                fname=request.POST.get('fname', '').strip(),
                tname=request.POST.get('tname', '').strip() or None,
                bdate=bdate,
                phone_number=request.POST.get('phone_number', '').strip() or None,
                email=request.POST.get('email', '').strip() or None,
                snils=request.POST.get('snils', '').strip(),
                oms=request.POST.get('oms', '').strip(),
            )
            messages.success(request, f'Пациент {patient.lname} {patient.fname} успешно создан')
            return redirect('clinic_admin:patient_detail', pk=patient.pk)
        except (IntegrityError, DatabaseError) as e:
            error_msg = 'Ошибка при создании пациента'
            error_str = str(e).lower()
            if 'snils' in error_str:
                error_msg = 'Пациент с таким СНИЛС уже существует'
            elif 'oms' in error_str:
                error_msg = 'Пациент с таким полисом ОМС уже существует'
            elif 'phone' in error_str:
                error_msg = 'Неверный формат телефона'
            return render(request, self.template_name, {
                'action': 'create',
                'error': error_msg
            })
        except Exception as e:
            error_str = str(e).lower()
            if 'phone' in error_str:
                error_msg = 'Неверный формат телефона'
            else:
                error_msg = f'Ошибка при создании пациента: {str(e)}'
            return render(request, self.template_name, {
                'action': 'create',
                'error': error_msg
            })


class PatientDetailView(AdminOrDoctorRequiredMixin, TemplateView):
    """Детальная информация о пациенте."""

    template_name = 'clinic_admin/patients/detail.html'
    template_name = 'clinic_admin/patients/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        role = getattr(user, 'role', None)
        patient = get_object_or_404(Patient, pk=kwargs['pk'])
        
        context['patient'] = patient

        doctor = None
        if role == 'doctor':
            doctor = getattr(user, 'doctor_profile', None)
        
        if doctor:
            appointments = Appointment.objects.filter(
                patient=patient,
                doctor=doctor
            ).select_related('doctor', 'doctor__specialization', 'slot', 'slot__room').order_by('-date')
        else:
            # Для админа показываем все приёмы
            appointments = Appointment.objects.filter(
                patient=patient
            ).select_related('doctor', 'doctor__specialization', 'slot', 'slot__room').order_by('-date')
        
        context['appointments'] = appointments
        

        parents = list(patient.parents())
        children = list(patient.children())
        context['parents'] = parents
        context['children'] = children
        

        siblings = []
        for parent in parents:
            parent_children = parent.children()
            for sibling in parent_children:
                if sibling.pk != patient.pk and sibling not in siblings:
                    siblings.append(sibling)
        context['siblings'] = siblings
        

        family_members = list(children)
        family_member_ids = {m.pk for m in family_members}
        for parent in parents:
            if parent.pk not in family_member_ids:
                family_members.append(parent)
                family_member_ids.add(parent.pk)
        for sibling in siblings:
            if sibling.pk not in family_member_ids:
                family_members.append(sibling)
                family_member_ids.add(sibling.pk)
        context['family_members'] = family_members
        

        doctors = Doctor.objects.all().select_related('specialization').order_by('lname', 'fname')
        context['doctors'] = doctors
        

        slots_qs = AppointmentSchedule.objects.filter(
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('doctor', 'room').order_by('time_from')
        
        slots_data = []
        available_dates_set = set()
        for slot in slots_qs:
            # Конвертируем время в московское
            moscow_time_from = timezone.localtime(slot.time_from)
            slot_date = moscow_time_from.date()
            available_dates_set.add(slot_date.isoformat())
            moscow_time_to = timezone.localtime(slot.time_to) if slot.time_to else None
            slots_data.append({
                'id': slot.id,
                'doctor_id': slot.doctor.pk,
                'date': slot_date.isoformat(),
                'time_from_str': moscow_time_from.strftime('%H:%M'),
                'time_to_str': moscow_time_to.strftime('%H:%M') if moscow_time_to else '',
                'room': slot.room.room_number if slot.room else None,
            })
        context['slots_json'] = json.dumps(slots_data)
        context['available_dates_json'] = json.dumps(sorted(list(available_dates_set)))
        

        view_type = self.request.GET.get('view', 'week')
        selected_date_str = self.request.GET.get('date')
        
        if view_type == 'day':
            if selected_date_str:
                try:
                    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                except ValueError:
                    selected_date = timezone.now().date()
            else:
                selected_date = timezone.now().date()
            week_start_date = selected_date
            week_end_date = selected_date + timedelta(days=1)
            context['view_type'] = 'day'
            context['selected_date'] = selected_date
            context['selected_date_str'] = selected_date.strftime('%Y-%m-%d')
            context['prev_day'] = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
            context['next_day'] = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            week_start_str = self.request.GET.get('week')
            if week_start_str:
                try:
                    week_start_date = datetime.strptime(week_start_str, '%Y-%m-%d').date()
                except ValueError:
                    week_start_date = timezone.now().date()
                    week_start_date = week_start_date - timedelta(days=week_start_date.weekday())
            else:
                now = timezone.now().date()
                week_start_date = now - timedelta(days=now.weekday())
            week_end_date = week_start_date + timedelta(days=7)
            context['view_type'] = 'week'
        appointments_by_day = defaultdict(list)
        for appointment in appointments:
            # Используем локальное время для определения даты приема
            if hasattr(appointment.date, 'date'):
                # appointment.date - это datetime
                local_appt_date = timezone.localtime(appointment.date)
                appt_date = local_appt_date.date()
            else:
                # appointment.date - это date объект
                appt_date = appointment.date
            if week_start_date <= appt_date < week_end_date:
                appointments_by_day[appt_date].append(appointment)
        week_days = []
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        
        days_to_show = 1 if context.get('view_type') == 'day' else 7
        
        for i in range(days_to_show):
            day_date = week_start_date + timedelta(days=i)
            day_appointments = sorted(
                appointments_by_day.get(day_date, []), 
                key=lambda a: a.date if hasattr(a.date, 'hour') else datetime.combine(a.date, datetime.min.time())
            )
            

            appointments_with_positions = []
            for appointment in day_appointments:
                # Используем timezone.localtime() для конвертации времени в локальный часовой пояс (московский)
                if appointment.slot:
                    local_time_from = timezone.localtime(appointment.slot.time_from)
                    local_time_to = timezone.localtime(appointment.slot.time_to)
                else:
                    # Если нет слота, используем дату приема
                    if hasattr(appointment.date, 'hour'):
                        local_time_from = timezone.localtime(appointment.date)
                        local_time_to = local_time_from + timedelta(hours=1)
                    else:
                        # Если date - это date объект, создаем datetime
                        dt_from = datetime.combine(appointment.date, datetime.min.time())
                        if not timezone.is_aware(dt_from):
                            dt_from = timezone.make_aware(dt_from)
                        local_time_from = timezone.localtime(dt_from)
                        local_time_to = local_time_from + timedelta(hours=1)
                
                # Получаем часы и минуты из локального времени (московского)
                start_hour = local_time_from.hour
                start_min = local_time_from.minute
                end_hour = local_time_to.hour
                end_min = local_time_to.minute
                
                minutes_from_start = (start_hour - 6) * 60 + start_min
                minutes_duration = (end_hour - start_hour) * 60 + (end_min - start_min)
                top_position = (minutes_from_start / 20) * 30
                duration = (minutes_duration / 20) * 30
                
                appointments_with_positions.append({
                    'appointment': appointment,
                    'top': top_position,
                    'height': max(duration, 30),
                    'end': top_position + duration
                })
            if appointments_with_positions:
                appointments_with_positions.sort(key=lambda x: x['top'])
                
                groups = []
                for appt_data in appointments_with_positions:
                    overlapping_groups = []
                    for idx, group in enumerate(groups):
                        for a in group:
                            if appt_data['top'] < a['end'] and appt_data['end'] > a['top']:
                                overlapping_groups.append(idx)
                                break
                    if overlapping_groups:
                        merged_group = [appt_data]
                        for idx in reversed(sorted(overlapping_groups)):
                            merged_group.extend(groups[idx])
                        for idx in reversed(sorted(overlapping_groups)):
                            groups.pop(idx)
                        groups.append(merged_group)
                    else:
                        groups.append([appt_data])
                for group in groups:
                    if len(group) > 1:
                        gap = 2
                        total_gaps = (len(group) - 1) * gap
                        width_percent = (100 - total_gaps) / len(group)
                        
                        for idx, appt_data in enumerate(group):
                            appt_data['left'] = idx * (width_percent + gap)
                            appt_data['width'] = width_percent
                    else:
                        group[0]['left'] = 1
                        group[0]['width'] = 98
            week_days.append({
                'date': day_date,
                'day_name': day_names[day_date.weekday()],
                'day_num': day_date.day,
                'month_name': month_names[day_date.month - 1],
                'appointments': appointments_with_positions,
                'is_today': day_date == timezone.now().date()
            })
        context['week_days'] = week_days
        context['week_start'] = week_start_date
        week_end = week_end_date - timedelta(days=1)
        context['week_end'] = week_end
        context['week_end_month_name'] = month_names[week_end.month - 1]
        context['prev_week'] = (week_start_date - timedelta(days=7)).strftime('%Y-%m-%d')
        context['next_week'] = (week_start_date + timedelta(days=7)).strftime('%Y-%m-%d')
        context['today'] = timezone.now().date().strftime('%Y-%m-%d')
        
        return context


class PatientEditView(AdminRequiredMixin, View):
    """Редактирование пациента."""

    template_name = 'clinic_admin/patients/form.html'

    def get(self, request, pk):
        """Обработка GET запроса для редактирования пациента."""
        patient = get_object_or_404(Patient, pk=pk)
        return render(request, self.template_name, {
            'action': 'edit',
            'patient': patient
        })
    
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk)
        
        try:
            bdate = parse_date_ddmmyyyy(request.POST.get('bdate'))
            if not bdate:
                messages.error(request, 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ')
                return redirect('clinic_admin:patient_detail', pk=patient.pk)
            
            patient.lname = request.POST.get('lname', '').strip()
            patient.fname = request.POST.get('fname', '').strip()
            patient.tname = request.POST.get('tname', '').strip() or None
            patient.bdate = bdate
            patient.phone_number = request.POST.get('phone_number', '').strip() or None
            patient.email = request.POST.get('email', '').strip() or None
            patient.snils = request.POST.get('snils', '').strip()
            patient.oms = request.POST.get('oms', '').strip()
            patient.save()
            
            messages.success(request, f'Пациент {patient.lname} {patient.fname} успешно обновлен')
            return redirect('clinic_admin:patient_detail', pk=patient.pk)
        except (IntegrityError, DatabaseError) as e:
            error_msg = 'Ошибка при обновлении пациента'
            error_str = str(e).lower()
            if 'snils' in error_str:
                error_msg = 'Пациент с таким СНИЛС уже существует'
            elif 'oms' in error_str:
                error_msg = 'Пациент с таким полисом ОМС уже существует'
            elif 'phone' in error_str:
                error_msg = 'Неверный формат телефона'
            messages.error(request, error_msg)
            return redirect('clinic_admin:patient_detail', pk=patient.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении пациента: {str(e)}')
            return redirect('clinic_admin:patient_detail', pk=patient.pk)


class PatientDeleteView(AdminRequiredMixin, View):
    """Удаление пациента."""

    def post(self, request, pk):
        """Обработка POST запроса на удаление пациента."""
        patient = get_object_or_404(Patient, pk=pk)
        patient_name = f"{patient.lname} {patient.fname}"
        patient.delete()
        messages.success(request, f'Пациент {patient_name} успешно удален')
        return redirect('clinic_admin:patient_list')


class PatientBookView(AdminRequiredMixin, View):
    """Запись пациента на прием."""

    def post(self, request, *args, **kwargs):
        """Обработка POST запроса на запись пациента."""
        patient = get_object_or_404(Patient, pk=kwargs['pk'])
        patient_name = f"{patient.lname} {patient.fname}"
        patient.delete()
        messages.success(request, f'Пациент {patient_name} успешно удален')
        return redirect('clinic_admin:patient_list')
class FamilyCreateView(AdminRequiredMixin, View):
    """Создание семейной связи."""

    template_name = 'clinic_admin/families/create.html'

    def get(self, request, *args, **kwargs):
        """Обработка GET запроса для создания семьи."""
        context = {
            'patients': Patient.objects.all().order_by('lname', 'fname')
        }
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        parent_id = request.POST.get('parent_id')
        child_ids = request.POST.getlist('child_ids')  # Множественный выбор
        
        if not parent_id or not child_ids:
            messages.error(request, 'Выберите родителя и хотя бы одного члена семьи')
            return render(request, self.template_name, {
                'patients': Patient.objects.all().order_by('lname', 'fname'),
                'error': 'Выберите родителя и хотя бы одного члена семьи'
            })
        
        try:
            parent = Patient.objects.get(pk=parent_id)
            created_count = 0
            errors = []
            
            for child_id in child_ids:
                try:
                    child = Patient.objects.get(pk=child_id)
                    
                    if parent.pk == child.pk:
                        errors.append(f'Нельзя добавить пациента {child.lname} {child.fname} в свою же семью')
                        continue
                    
                    PatientGroup.objects.get_or_create(parent=parent, child=child)
                    created_count += 1
                except Patient.DoesNotExist:
                    errors.append(f'Пациент с ID {child_id} не найден')
                except IntegrityError:
                    pass  # Связь уже существует, пропускаем
            
            if created_count > 0:
                messages.success(request, f'Успешно создано {created_count} семейных связей')
            if errors:
                for error in errors:
                    messages.warning(request, error)
            
            return redirect('clinic_admin:family_detail', pk=parent.pk)
        except Patient.DoesNotExist:
            messages.error(request, 'Родитель не найден')
            return render(request, self.template_name, {
                'patients': Patient.objects.all().order_by('lname', 'fname'),
                'error': 'Родитель не найден'
            })
        except Exception as e:
            messages.error(request, f'Ошибка при создании семьи: {str(e)}')
            return render(request, self.template_name, {
                'patients': Patient.objects.all().order_by('lname', 'fname'),
                'error': f'Ошибка при создании семьи: {str(e)}'
            })


class FamilyAddMemberView(AdminRequiredMixin, View):
    """Добавление члена семьи."""

    def post(self, request, pk):
        """Обработка POST запроса на добавление члена семьи."""
        patient = get_object_or_404(Patient, pk=pk)
        child_id = request.POST.get('child_id')
        
        if not child_id:
            messages.error(request, 'Выберите пациента')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        
        try:
            child = Patient.objects.get(pk=child_id)
            
            if child.pk == patient.pk:
                messages.error(request, 'Нельзя добавить пациента в свою же семью')
                return redirect('clinic_admin:family_detail', pk=patient.pk)
            
            PatientGroup.objects.get_or_create(parent=patient, child=child)
            messages.success(request, f'{child.lname} {child.fname} успешно добавлен в семью')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        except Patient.DoesNotExist:
            messages.error(request, 'Пациент не найден')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        except IntegrityError:
            messages.info(request, 'Связь уже существует')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при добавлении члена семьи: {str(e)}')
            return redirect('clinic_admin:family_detail', pk=patient.pk)


class FamilyRemoveMemberView(AdminRequiredMixin, View):
    """Удаление члена семьи."""

    def post(self, request, *args, **kwargs):
        """Обработка POST запроса на удаление члена семьи."""
        patient = get_object_or_404(Patient, pk=kwargs['pk'])
        other_patient_id = request.POST.get('child_id') or request.POST.get('parent_id')
        
        if not other_patient_id:
            messages.error(request, 'Не указан пациент для удаления')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        
        try:
            other_patient = Patient.objects.get(pk=other_patient_id)
            
            deleted1, _ = PatientGroup.objects.filter(parent=patient, child=other_patient).delete()
            deleted2, _ = PatientGroup.objects.filter(parent=other_patient, child=patient).delete()
            
            if deleted1 > 0 or deleted2 > 0:
                messages.success(request, f'{other_patient.lname} {other_patient.fname} успешно удален из семьи')
            else:
                messages.info(request, 'Связь не найдена')
            
            return redirect('clinic_admin:family_detail', pk=patient.pk)
            
        except Patient.DoesNotExist:
            messages.error(request, 'Пациент не найден')
            return redirect('clinic_admin:family_detail', pk=patient.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при удалении члена семьи: {str(e)}')
            return redirect('clinic_admin:family_detail', pk=patient.pk)


class FamilyListView(AdminRequiredMixin, TemplateView):
    """Список семей."""

    template_name = 'clinic_admin/families/list.html'

    def _get_all_family_members(self, patient, visited=None):
        """Получение всех членов семьи рекурсивно."""
        if visited is None:
            visited = set()
        
        if patient.pk in visited:
            return visited
        
        visited.add(patient.pk)
        
        parents = patient.parents()
        children = patient.children()
        
        for parent in parents:
            if parent.pk not in visited:
                self._get_all_family_members(parent, visited)
        
        for child in children:
            if child.pk not in visited:
                self._get_all_family_members(child, visited)
        
        return visited

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        patients_with_families = Patient.objects.filter(
            Q(parents_rel__isnull=False) | Q(children_rel__isnull=False)
        ).distinct()
        
        families_dict = {}
        processed_patients = set()
        
        for patient in patients_with_families:
            if patient.pk in processed_patients:
                continue
            
            family_member_ids = self._get_all_family_members(patient)
            
            if len(family_member_ids) > 1:
                family_members = list(Patient.objects.filter(pk__in=family_member_ids))
                
                representative = patient
                for member in family_members:
                    if PatientGroup.objects.filter(parent=member).exists():
                        representative = member
                        break
                
                family_key = min(family_member_ids)
                if family_key not in families_dict:
                    families_dict[family_key] = {
                        'representative': representative,
                        'members': sorted(family_members, key=lambda p: (p.lname, p.fname)),
                        'members_count': len(family_members)
                    }
                    processed_patients.update(family_member_ids)
        
        families_list = list(families_dict.values())
        families_list.sort(key=lambda f: (f['representative'].lname, f['representative'].fname))
        
        paginator = Paginator(families_list, 25)
        page = self.request.GET.get('page')
        families_page = paginator.get_page(page)
        
        context['families_page'] = families_page
        return context


class FamilyDetailView(AdminRequiredMixin, TemplateView):
    """Детальная информация о семье."""

    template_name = 'clinic_admin/families/detail.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для детальной информации о семье."""
        context = super().get_context_data(**kwargs)
        patient = get_object_or_404(Patient, pk=kwargs['pk'])
        

        family_members = set([patient])
        family_members.update(patient.parents())
        family_members.update(patient.children())
        

        for member in list(family_members):
            family_members.update(member.parents())
            family_members.update(member.children())
        context['patient'] = patient
        

        parents_list = list(patient.parents())
        patient_children = list(patient.children())
        

        if patient_children:
            
            for child in patient_children:
                child_parents = child.parents()
                for parent in child_parents:
                    if parent.pk != patient.pk and parent not in parents_list:
                        parents_list.append(parent)
            if patient not in parents_list:
                parents_list.insert(0, patient)
        context['parents'] = parents_list
        context['children'] = patient_children
        context['all_patients'] = Patient.objects.all().order_by('lname', 'fname')
        

        all_family_members = list(family_members)
        family_appointments = Appointment.objects.filter(
            patient__in=all_family_members
        ).exclude(status='cancelled').select_related('doctor', 'doctor__specialization', 'slot', 'slot__room', 'patient').order_by('date')
        
        context['family_appointments'] = family_appointments
        

        from django.utils import timezone
        
        view_type = self.request.GET.get('view', 'week')
        selected_date_str = self.request.GET.get('date')
        
        if view_type == 'day':
            if selected_date_str:
                try:
                    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                except ValueError:
                    selected_date = timezone.now().date()
            else:
                selected_date = timezone.now().date()
            week_start_date = selected_date
            week_end_date = selected_date + timedelta(days=1)
            context['view_type'] = 'day'
            context['selected_date'] = selected_date
            context['selected_date_str'] = selected_date.strftime('%Y-%m-%d')
            context['prev_day'] = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
            context['next_day'] = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            week_start_str = self.request.GET.get('week')
            if week_start_str:
                try:
                    week_start_date = datetime.strptime(week_start_str, '%Y-%m-%d').date()
                except ValueError:
                    week_start_date = timezone.now().date()
                    week_start_date = week_start_date - timedelta(days=week_start_date.weekday())
            else:
                now = timezone.now().date()
                week_start_date = now - timedelta(days=now.weekday())
            week_end_date = week_start_date + timedelta(days=7)
            context['view_type'] = 'week'
        appointments_by_day = defaultdict(list)
        for appointment in family_appointments:
            # Используем локальное время для определения даты приема
            if hasattr(appointment.date, 'date'):
                # appointment.date - это datetime
                local_appt_date = timezone.localtime(appointment.date)
                appt_date = local_appt_date.date()
            else:
                # appointment.date - это date объект
                appt_date = appointment.date
            if week_start_date <= appt_date < week_end_date:
                appointments_by_day[appt_date].append(appointment)
        week_days = []
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        
        days_to_show = 1 if context.get('view_type') == 'day' else 7
        
        for i in range(days_to_show):
            day_date = week_start_date + timedelta(days=i)
            day_appointments = sorted(
                appointments_by_day.get(day_date, []), 
                key=lambda a: a.date if hasattr(a.date, 'hour') else datetime.combine(a.date, datetime.min.time())
            )
            

            appointments_with_positions = []
            now = timezone.now()
            
            for appointment in day_appointments:
                # Используем timezone.localtime() для конвертации времени в локальный часовой пояс
                if appointment.slot:
                    local_time_from = timezone.localtime(appointment.slot.time_from)
                    local_time_to = timezone.localtime(appointment.slot.time_to)
                else:
                    # Если нет слота, используем дату приема
                    if hasattr(appointment.date, 'hour'):
                        local_time_from = timezone.localtime(appointment.date)
                        local_time_to = local_time_from + timedelta(hours=1)
                    else:
                        # Если date - это date объект, создаем datetime
                        dt_from = datetime.combine(appointment.date, datetime.min.time())
                        if not timezone.is_aware(dt_from):
                            dt_from = timezone.make_aware(dt_from)
                        local_time_from = timezone.localtime(dt_from)
                        local_time_to = local_time_from + timedelta(hours=1)
                
                # Получаем часы и минуты из локального времени (московского)
                start_hour = local_time_from.hour
                start_min = local_time_from.minute
                end_hour = local_time_to.hour
                end_min = local_time_to.minute
                
                # Расчет позиции: начинаем с 6:00, каждый 20-минутный интервал = 30px
                minutes_from_6am = (start_hour - 6) * 60 + start_min
                if minutes_from_6am < 0:
                    continue  # Пропускаем приемы до 6:00
                
                minutes_duration = (end_hour - start_hour) * 60 + (end_min - start_min)
                # Формула: (минуты от 6:00 / 20 минут) * 30px
                top_position = (minutes_from_6am / 20) * 30
                duration = (minutes_duration / 20) * 30
                
                appointments_with_positions.append({
                    'appointment': appointment,
                    'top': top_position,
                    'height': max(duration, 30),
                    'end': top_position + duration
                })
            if appointments_with_positions:
                appointments_with_positions.sort(key=lambda x: x['top'])
                
                groups = []
                for appt_data in appointments_with_positions:
                    overlapping_groups = []
                    for idx, group in enumerate(groups):
                        for a in group:
                            if appt_data['top'] < a['end'] and appt_data['end'] > a['top']:
                                overlapping_groups.append(idx)
                                break
                    if overlapping_groups:
                        merged_group = [appt_data]
                        for idx in reversed(sorted(overlapping_groups)):
                            merged_group.extend(groups[idx])
                        for idx in reversed(sorted(overlapping_groups)):
                            groups.pop(idx)
                        groups.append(merged_group)
                    else:
                        groups.append([appt_data])
                for group in groups:
                    if len(group) > 1:
                        gap = 2
                        total_gaps = (len(group) - 1) * gap
                        width_percent = (100 - total_gaps) / len(group)
                        
                        for idx, appt_data in enumerate(group):
                            appt_data['left'] = idx * (width_percent + gap)
                            appt_data['width'] = width_percent
                    else:
                        group[0]['left'] = 1
                        group[0]['width'] = 98
            week_days.append({
                'date': day_date,
                'day_name': day_names[day_date.weekday()],
                'day_num': day_date.day,
                'month_name': month_names[day_date.month - 1],
                'appointments': appointments_with_positions,
                'is_today': day_date == timezone.now().date()
            })
        context['week_days'] = week_days
        context['week_start'] = week_start_date
        week_end = week_end_date - timedelta(days=1)
        context['week_end'] = week_end
        context['week_end_month_name'] = month_names[week_end.month - 1]
        context['prev_week'] = (week_start_date - timedelta(days=7)).strftime('%Y-%m-%d')
        context['next_week'] = (week_start_date + timedelta(days=7)).strftime('%Y-%m-%d')
        context['today'] = timezone.now().date().strftime('%Y-%m-%d')
        
        return context
