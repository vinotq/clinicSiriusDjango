from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.contrib import messages
from django.db import IntegrityError
from django.core.paginator import Paginator

from core.mixins import AdminRequiredMixin
from staff.models import Doctor, Specialization
from .utils import parse_date_ddmmyyyy

class DoctorListView(AdminRequiredMixin, TemplateView):
    """Список врачей."""

    template_name = 'clinic_admin/doctors/list.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для списка врачей."""
        context = super().get_context_data(**kwargs)
        doctors = Doctor.objects.all().select_related('specialization').order_by('lname', 'fname')
        paginator = Paginator(doctors, 25)
        page = self.request.GET.get('page')
        doctors_page = paginator.get_page(page)
        context['doctors_page'] = doctors_page
        return context


class DoctorCreateView(AdminRequiredMixin, TemplateView):
    """Создание нового врача."""

    template_name = 'clinic_admin/doctors/form.html'

    def get(self, request, *args, **kwargs):
        """Обработка GET запроса для создания врача."""
        return render(request, self.template_name, {
            'action': 'create',
            'specializations': Specialization.objects.all().order_by('name')
        })
    
    def post(self, request, *args, **kwargs):
        try:
            bdate = parse_date_ddmmyyyy(request.POST.get('bdate'))
            if not bdate:
                return render(request, self.template_name, {
                    'action': 'create',
                    'specializations': Specialization.objects.all().order_by('name'),
                    'error': 'Неверный формат даты. Используйте формат ДД.ММ.ГГГГ'
                })
            specialization_id = request.POST.get('specialization')
            if not specialization_id:
                return render(request, self.template_name, {
                    'action': 'create',
                    'specializations': Specialization.objects.all().order_by('name'),
                    'error': 'Необходимо выбрать специализацию'
                })
            doctor = Doctor.objects.create(
                lname=request.POST.get('lname', '').strip(),
                fname=request.POST.get('fname', '').strip(),
                tname=request.POST.get('tname', '').strip() or None,
                bdate=bdate,
                phone_number=request.POST.get('phone_number', '').strip() or None,
                phone=request.POST.get('phone_number', '').strip() or None,
                email=request.POST.get('email', '').strip(),
                specialization_id=specialization_id,
            )
            messages.success(request, f'Врач {doctor.lname} {doctor.fname} успешно создан')
            return redirect('clinic_admin:doctor_detail', pk=doctor.pk)
        except IntegrityError as e:
            error_msg = 'Ошибка при создании врача'
            if 'email' in str(e):
                error_msg = 'Врач с таким email уже существует'
            return render(request, self.template_name, {
                'action': 'create',
                'specializations': Specialization.objects.all().order_by('name'),
                'error': error_msg
            })
        except Exception as e:
            return render(request, self.template_name, {
                'action': 'create',
                'specializations': Specialization.objects.all().order_by('name'),
                'error': f'Ошибка при создании врача: {str(e)}'
            })
class DoctorEditView(AdminRequiredMixin, View):
    """Создание расписания доктора."""

    template_name = 'clinic_admin/schedule/add_timeslot.html'

    def get(self, request, pk):
        """Обработка GET запроса для создания расписания."""
        import json
        from scheduling.models import Room
        doctor = get_object_or_404(Doctor, pk=pk)
        
        rooms = Room.objects.all().order_by('room_number').values_list('room_number', flat=True)
        return render(request, self.template_name, {
            'doctor': doctor,
            'existing_rooms_json': json.dumps(list(rooms))
        })
    
    def post(self, request, pk):
        import json
        from scheduling.models import Room, AppointmentSchedule
        from datetime import datetime, timedelta
        from django.utils import timezone as tz
        
        doctor = get_object_or_404(Doctor, pk=pk)
        mode = request.POST.get('mode', 'day')
        date_str = request.POST.get('date', '').strip()
        room_number = request.POST.get('room_number', '').strip()
        
        rooms = Room.objects.all().order_by('room_number').values_list('room_number', flat=True)
        rooms_json = json.dumps(list(rooms))
        
        if not date_str or not room_number:
            date_str_display = date_str
            if date_str and '-' in date_str:
                try:
                    temp_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    date_str_display = temp_date.strftime('%d.%m.%Y')
                except (ValueError, TypeError):
                    pass
            return render(request, self.template_name, {
                'doctor': doctor,
                'error': 'Укажите дату и кабинет',
                'selected_date': date_str_display,
                'existing_rooms_json': rooms_json
            })
        
        try:
            if '.' in date_str:
                date = datetime.strptime(date_str, '%d.%m.%Y').date()
                date_str_display = date_str
            else:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                date_str_display = date.strftime('%d.%m.%Y')
        except ValueError:
            date_str_display = date_str
            return render(request, self.template_name, {
                'doctor': doctor,
                'error': 'Неверный формат даты. Используйте формат дд.мм.гггг (например, 25.12.2024)',
                'selected_date': date_str_display,
                'existing_rooms_json': rooms_json
            })
        
        room, _ = Room.objects.get_or_create(room_number=room_number)
        created_slots = []
        
        if mode == 'single':
            single_time_str = request.POST.get('single_time', '09:00')
            single_duration = int(request.POST.get('single_duration', '30'))
            
            try:
                time_from = datetime.strptime(single_time_str, '%H:%M').time()
            except ValueError:
                return render(request, self.template_name, {
                    'doctor': doctor,
                    'error': 'Неверный формат времени',
                    'selected_date': date_str_display,
                    'existing_rooms_json': rooms_json
                })
            
            dt_from = datetime.combine(date, time_from)
            dt_to = dt_from + timedelta(minutes=single_duration)
            if not tz.is_aware(dt_from):
                dt_from = tz.make_aware(dt_from)
            if not tz.is_aware(dt_to):
                dt_to = tz.make_aware(dt_to)
            
            slot = AppointmentSchedule.objects.create(
                doctor=doctor,
                room=room,
                time_from=dt_from,
                time_to=dt_to
            )
            created_slots.append(slot)
        else:
            day_start_str = request.POST.get('day_start', '09:00')
            day_end_str = request.POST.get('day_end', '18:00')
            slot_duration = int(request.POST.get('slot_duration', '30'))
            has_break = request.POST.get('has_break') == 'on'
            break_start_str = request.POST.get('break_start', '13:00')
            break_end_str = request.POST.get('break_end', '14:00')
            
            try:
                day_start = datetime.strptime(day_start_str, '%H:%M').time()
                day_end = datetime.strptime(day_end_str, '%H:%M').time()
                break_start = datetime.strptime(break_start_str, '%H:%M').time() if has_break else None
                break_end = datetime.strptime(break_end_str, '%H:%M').time() if has_break else None
            except ValueError:
                return render(request, self.template_name, {
                    'doctor': doctor,
                    'error': 'Неверный формат времени',
                    'selected_date': date_str_display,
                    'existing_rooms_json': rooms_json
                })
            
            if day_start >= day_end:
                return render(request, self.template_name, {
                    'doctor': doctor,
                    'error': 'Время начала должно быть раньше времени окончания',
                    'selected_date': date_str_display,
                    'existing_rooms_json': rooms_json
                })
            
            current_time = datetime.combine(date, day_start)
            end_time = datetime.combine(date, day_end)
            break_start_dt = datetime.combine(date, break_start) if break_start else None
            break_end_dt = datetime.combine(date, break_end) if break_end else None
            
            if not tz.is_aware(current_time):
                current_time = tz.make_aware(current_time)
            if not tz.is_aware(end_time):
                end_time = tz.make_aware(end_time)
            if break_start_dt and not tz.is_aware(break_start_dt):
                break_start_dt = tz.make_aware(break_start_dt)
            if break_end_dt and not tz.is_aware(break_end_dt):
                break_end_dt = tz.make_aware(break_end_dt)
            
            while current_time + timedelta(minutes=slot_duration) <= end_time:
                slot_end = current_time + timedelta(minutes=slot_duration)
                
                if has_break and break_start_dt and break_end_dt:
                    if not (slot_end <= break_start_dt or current_time >= break_end_dt):
                        current_time = break_end_dt
                        continue
                
                existing = AppointmentSchedule.objects.filter(
                    doctor=doctor,
                    time_from=current_time,
                    time_to=slot_end
                ).exists()
                
                if not existing:
                    slot = AppointmentSchedule.objects.create(
                        doctor=doctor,
                        room=room,
                        time_from=current_time,
                        time_to=slot_end
                    )
                    created_slots.append(slot)
                current_time = slot_end
        
        if created_slots:
            return render(request, self.template_name, {
                'doctor': doctor,
                'success': f'Создано окон: {len(created_slots)}',
                'selected_date': date_str_display,
                'existing_rooms_json': rooms_json
            })
        else:
            return render(request, self.template_name, {
                'doctor': doctor,
                'error': 'Не удалось создать окна. Возможно, они уже существуют.',
                'selected_date': date_str_display,
                'existing_rooms_json': rooms_json
            })


class DoctorDetailView(AdminRequiredMixin, TemplateView):
    """Детальная информация о враче."""

    template_name = 'clinic_admin/doctors/detail.html'

    def get_context_data(self, **kwargs):
        """Получение контекста для детальной информации о враче."""
        context = super().get_context_data(**kwargs)
        doctor = get_object_or_404(Doctor, pk=kwargs['pk'])
        
        from django.utils import timezone
        from scheduling.models import AppointmentSchedule
        from datetime import datetime, timedelta
        from collections import defaultdict
        from django.core.exceptions import ObjectDoesNotExist
        
        context['doctor'] = doctor
        
        slots = AppointmentSchedule.objects.filter(
            doctor=doctor
        ).select_related('room', 'appointment', 'appointment__patient').order_by('time_from')
        
        available_count = sum(1 for s in slots if s.is_available())
        booked_count = 0
        in_progress_count = 0
        completed_count = 0
        
        for s in slots:
            try:
                appointment = s.appointment
                status = appointment.status
                if status == 'booked':
                    booked_count += 1
                elif status == 'in_progress':
                    in_progress_count += 1
                elif status == 'completed':
                    completed_count += 1
            except ObjectDoesNotExist:
                pass
        context['available_count'] = available_count
        context['booked_count'] = booked_count
        context['in_progress_count'] = in_progress_count
        context['completed_count'] = completed_count
        context['total_count'] = len(slots)
        
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
                    now = timezone.now().date()
                    week_start_date = now - timedelta(days=now.weekday())
            else:
                now = timezone.now().date()
                week_start_date = now - timedelta(days=now.weekday())
            week_end_date = week_start_date + timedelta(days=7)
            context['view_type'] = 'week'
        schedule_by_day = defaultdict(list)
        for slot in slots:
            # Используем локальное время для определения даты слота
            local_time_from = timezone.localtime(slot.time_from)
            slot_date = local_time_from.date()
            if week_start_date <= slot_date < week_end_date:
                schedule_by_day[slot_date].append(slot)
        week_days = []
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        
        days_to_show = 1 if context.get('view_type') == 'day' else 7
        
        for i in range(days_to_show):
            day_date = week_start_date + timedelta(days=i)
            day_slots = sorted(schedule_by_day.get(day_date, []), key=lambda s: s.time_from)
            
            slots_with_positions = []
            now = timezone.now()
            
            for slot in day_slots:
                # Используем timezone.localtime() для конвертации времени в локальный часовой пояс
                # При USE_TZ=True время в БД хранится в UTC, timezone.localtime() конвертирует в TIME_ZONE (Europe/Moscow)
                local_time_from = timezone.localtime(slot.time_from)
                local_time_to = timezone.localtime(slot.time_to)
                
                # Получаем часы и минуты из локального времени (московского)
                start_hour = local_time_from.hour
                start_min = local_time_from.minute
                end_hour = local_time_to.hour
                end_min = local_time_to.minute
                
                # Проверяем, прошел ли слот по времени
                is_past = slot.time_from < now
                
                # Если слот свободный и находится в прошлом - пропускаем его (не показываем)
                if slot.is_available() and is_past:
                    continue
                
                # Расчет позиции: начинаем с 6:00, каждый 20-минутный интервал = 30px
                minutes_from_6am = (start_hour - 6) * 60 + start_min
                if minutes_from_6am < 0:
                    continue  # Пропускаем слоты до 6:00
                
                minutes_duration = (end_hour - start_hour) * 60 + (end_min - start_min)
                # Формула: (минуты от 6:00 / 20 минут) * 30px
                top_position = (minutes_from_6am / 20) * 30
                duration = (minutes_duration / 20) * 30
                
                slots_with_positions.append({
                    'slot': slot,
                    'top': top_position,
                    'height': max(duration, 30),
                    'end': top_position + duration,
                    'is_past': is_past
                })
            if slots_with_positions:
                slots_with_positions.sort(key=lambda x: x['top'])
                
                groups = []
                for slot_data in slots_with_positions:
                    overlapping_groups = []
                    for idx, group in enumerate(groups):
                        for s in group:
                            if slot_data['top'] < s['end'] and slot_data['end'] > s['top']:
                                overlapping_groups.append(idx)
                                break
                    if overlapping_groups:
                        merged_group = [slot_data]
                        for idx in reversed(sorted(overlapping_groups)):
                            merged_group.extend(groups[idx])
                        for idx in reversed(sorted(overlapping_groups)):
                            groups.pop(idx)
                        groups.append(merged_group)
                    else:
                        groups.append([slot_data])
                for group in groups:
                    if len(group) > 1:
                        gap = 2
                        total_gaps = (len(group) - 1) * gap
                        width_percent = (100 - total_gaps) / len(group)
                        
                        for idx, slot_data in enumerate(group):
                            slot_data['left'] = idx * (width_percent + gap)
                            slot_data['width'] = width_percent
                    else:
                        group[0]['left'] = 1
                        group[0]['width'] = 98
            week_days.append({
                'date': day_date,
                'day_name': day_names[day_date.weekday()],
                'day_num': day_date.day,
                'month_name': month_names[day_date.month - 1],
                'slots': slots_with_positions,
                'is_today': day_date == timezone.now().date()
            })
        context['week_days'] = week_days
        context['week_start'] = week_start_date
        context['week_end'] = week_end_date - timedelta(days=1)
        context['prev_week'] = (week_start_date - timedelta(days=7)).strftime('%Y-%m-%d')
        context['next_week'] = (week_start_date + timedelta(days=7)).strftime('%Y-%m-%d')
        context['today'] = timezone.now().date().strftime('%Y-%m-%d')
        
        return context


class DoctorDeleteView(AdminRequiredMixin, View):
    """Удаление врача."""

    def post(self, request, *args, **kwargs):
        """Обработка POST запроса на удаление врача."""
        doctor = get_object_or_404(Doctor, pk=kwargs['pk'])
        doctor_name = f"{doctor.lname} {doctor.fname}"
        doctor.delete()
        messages.success(request, f'Врач {doctor_name} успешно удален')
        return redirect('clinic_admin:doctor_list')