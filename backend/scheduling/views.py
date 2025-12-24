from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView, View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.dateparse import parse_datetime
from django.db.models import Q, Prefetch
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from core.mixins import DoctorRequiredMixin, PatientRequiredMixin
from django.db import IntegrityError, DatabaseError
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from datetime import datetime, timedelta
from collections import defaultdict
import re

from .models import AppointmentSchedule, Appointment, Recipe, Diagnosis
from .serializers import AppointmentScheduleSerializer, AppointmentSerializer
from patients.models import Patient
from staff.models import Doctor, Specialization

# Утилита для работы с московским временем
# Данные хранятся в UTC в базе (Django с USE_TZ=True)
from django.utils import timezone

def to_moscow_time(dt):
    """Конвертирует datetime в московское время"""
    if dt is None:
        return None
    # Если naive datetime, делаем его aware с московским временем
    if not timezone.is_aware(dt):
        return timezone.make_aware(dt)
    # Конвертируем в московское время
    return timezone.localtime(dt)

def moscow_now():
    """Возвращает текущее время в московском часовом поясе"""
    return timezone.localtime(timezone.now())

class AppointmentScheduleViewSet(viewsets.ModelViewSet):
    queryset = AppointmentSchedule.objects.all()
    serializer_class = AppointmentScheduleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        from django.utils import timezone
        queryset = AppointmentSchedule.objects.filter(
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('doctor', 'room')
        doctor_id = self.request.query_params.get('doctor_id')
        doctor = self.request.query_params.get('doctor')
        date = self.request.query_params.get('date')
        
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        elif doctor:
            queryset = queryset.filter(doctor_id=doctor)
        if date:
            queryset = queryset.filter(time_from__date=date)
        return queryset.order_by('time_from')
    @action(detail=False, methods=['get'])
    def available(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date = request.query_params.get('date')
        
        queryset = self.get_queryset()
        
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        if date:
            queryset = queryset.filter(time_from__date=date)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'])
    def schedule_by_doctor(self, request):
        from django.utils import timezone
        doctor_id = request.query_params.get('doctor_id')
        
        if not doctor_id:
            return Response(
                {'detail': 'doctor_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        slots = AppointmentSchedule.objects.filter(
            doctor_id=doctor_id,
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('room').order_by('time_from')
        
        schedule_dict = defaultdict(lambda: defaultdict(list))
        
        for slot in slots:
            date_key = slot.time_from.date().isoformat()
            time_key = slot.time_from.strftime('%H:%M')
            schedule_dict[date_key][time_key].append({
                'id': slot.id,
                'time_from': slot.time_from.isoformat(),
                'time_to': slot.time_to.isoformat(),
                'room': slot.room.room_number if slot.room else 'N/A'
            })
        result = []
        for date_str in sorted(schedule_dict.keys()):
            date_obj = datetime.fromisoformat(date_str).date()
            date_display = date_obj.strftime('%d.%m.%Y')
            day_name = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'][date_obj.weekday()]
            
            times = []
            for time_str in sorted(schedule_dict[date_str].keys()):
                times.append({
                    'time': time_str,
                    'slots': schedule_dict[date_str][time_str]
                })
            result.append({
                'date': date_str,
                'date_display': f"{date_display} ({day_name})",
                'times': times
            })
        return Response(result)
class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'patient_profile'):
            return Appointment.objects.filter(patient=user.patient_profile).select_related(
                'doctor', 'doctor__user', 'patient', 'slot', 'slot__room'
            )
        return Appointment.objects.none()
    def perform_create(self, serializer):
        serializer.save()
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        
        user = request.user
        if hasattr(user, 'patient_profile'):
            patient = user.patient_profile
            all_patients = [patient] + list(patient.children())
            if appointment.patient not in all_patients:
                return Response(
                    {'detail': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        appointment.delete()
        return Response({'detail': 'Appointment cancelled'}, status=status.HTTP_200_OK)
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()
        
        user = request.user
        if hasattr(user, 'patient_profile'):
            patient = user.patient_profile
            all_patients = [patient] + list(patient.children())
            if appointment.patient not in all_patients:
                return Response(
                    {'detail': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        new_slot_id = request.data.get('slot_id')
        if not new_slot_id:
            return Response(
                {'detail': 'slot_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            new_slot = AppointmentSchedule.objects.get(pk=new_slot_id)
        except AppointmentSchedule.DoesNotExist:
            return Response(
                {'detail': 'Slot not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        if not new_slot.is_available():
            return Response(
                {'detail': 'This slot is already booked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if appointment.slot:
            old_slot = appointment.slot
        appointment.slot = new_slot
        appointment.date = new_slot.time_from
        appointment.doctor = new_slot.doctor
        appointment.save()
        
        return Response(
            AppointmentSerializer(appointment, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        appointment = self.get_object()
        
        user = request.user
        if not hasattr(user, 'doctor_profile') or user.doctor_profile != appointment.doctor:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {'detail': 'status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        valid_statuses = [choice[0] for choice in Appointment.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'detail': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        appointment.status = new_status
        

        if new_status == 'cancelled' and appointment.slot:
            appointment.slot = None
        appointment.save()
        
        return Response(
            AppointmentSerializer(appointment, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
class DoctorScheduleView(DoctorRequiredMixin, ListView):
    model = AppointmentSchedule
    template_name = 'scheduling/doctor_schedule.html'
    context_object_name = 'slots'
    
    def get_queryset(self):
        from django.utils import timezone
        self.doctor = get_object_or_404(Doctor, pk=self.kwargs['doctor_id'])
        queryset = AppointmentSchedule.objects.filter(doctor=self.doctor).select_related('room', 'appointment', 'appointment__patient').order_by('time_from')
        

        # Обрабатываем фильтрацию по неделе или дню с учетом часового пояса
        week_start = self.request.GET.get('week')
        date_str = self.request.GET.get('date')
        
        if week_start:
            try:
                from datetime import datetime
                week_date = datetime.strptime(week_start, '%Y-%m-%d').date()
                week_end_date = week_date + timedelta(days=7)
                
                # Конвертируем локальные даты в UTC datetime для правильной фильтрации
                # Создаем начало и конец дня в московском часовом поясе, затем конвертируем в UTC
                week_start_local = timezone.make_aware(datetime.combine(week_date, datetime.min.time()))
                week_end_local = timezone.make_aware(datetime.combine(week_end_date, datetime.min.time()))
                # Конвертируем в UTC для сравнения с БД (Django хранит в UTC)
                week_start_dt = week_start_local.astimezone(timezone.utc)
                week_end_dt = week_end_local.astimezone(timezone.utc)
                
                # Фильтруем по datetime диапазону вместо date, чтобы учесть часовой пояс
                queryset = queryset.filter(time_from__gte=week_start_dt, time_from__lt=week_end_dt)
            except ValueError:
                pass
        elif date_str:
            # Фильтрация по одному дню (для day view)
            try:
                from datetime import datetime
                day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                day_end_date = day_date + timedelta(days=1)
                
                # Конвертируем локальные даты в UTC datetime для правильной фильтрации
                day_start_local = timezone.make_aware(datetime.combine(day_date, datetime.min.time()))
                day_end_local = timezone.make_aware(datetime.combine(day_end_date, datetime.min.time()))
                # Конвертируем в UTC для сравнения с БД (Django хранит в UTC)
                day_start_dt = day_start_local.astimezone(timezone.utc)
                day_end_dt = day_end_local.astimezone(timezone.utc)
                
                queryset = queryset.filter(time_from__gte=day_start_dt, time_from__lt=day_end_dt)
            except ValueError:
                pass
        
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doctor'] = self.doctor
        slots = context['slots']
        

        context['all_patients'] = Patient.objects.all().order_by('lname', 'fname')
        

        from django.utils import timezone
        from collections import defaultdict
        
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
        schedule_by_day = defaultdict(list)
        slots_in_period = []
        for slot in slots:
            # Используем локальное время для определения даты слота
            # Это важно, так как слот хранится в UTC, но должен отображаться по локальной дате
            slot_date = timezone.localtime(slot.time_from).date()
            if week_start_date <= slot_date < week_end_date:
                schedule_by_day[slot_date].append(slot)
                slots_in_period.append(slot)
        available_count = sum(1 for s in slots_in_period if s.is_available())
        

        booked_count = 0
        in_progress_count = 0
        completed_count = 0
        
        for s in slots_in_period:
            
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
        total_count = len(slots_in_period)
        
        context['available_count'] = available_count
        context['booked_count'] = booked_count
        context['in_progress_count'] = in_progress_count
        context['completed_count'] = completed_count
        context['total_count'] = total_count
        

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
                # Эти значения ДОЛЖНЫ совпадать с тем, что показывает {{ slot.time_from|time:"H:i" }} в шаблоне
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
                # Каждый 20-минутный интервал = 30px, значит каждый час = 90px (3 интервала * 30px)
                # ВАЖНО: top считается от начала .day-content (который уже находится после заголовка 100px)
                # Поэтому НЕ добавляем 100px - слоты находятся внутри .day-content с position: relative
                # slot.time_from хранится в UTC, local_time_from уже конвертирован в локальное время
                minutes_from_6am = (start_hour - 6) * 60 + start_min
                if minutes_from_6am < 0:
                    continue  # Пропускаем слоты до 6:00
                
                minutes_duration = (end_hour - start_hour) * 60 + (end_min - start_min)
                # Формула: (минуты от 6:00 / 20 минут) * 30px
                # top = 0px соответствует 6:00 внутри .day-content
                top_position = (minutes_from_6am / 20) * 30
                duration = (minutes_duration / 20) * 30
                
                # Временная отладка для проверки расчета
                if slot.id in [16585, 16586, 16587, 16588]:
                    print(f"DEBUG Slot {slot.id}: Time={slot.time_from}, Local={local_time_from.strftime('%H:%M')}, Hour={start_hour}, Min={start_min}, Minutes from 6am={minutes_from_6am}, Top={top_position}px")
                
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
        # Передаем серверное время в московском часовом поясе для синхронизации с клиентом
        server_time_moscow = moscow_now()
        context['server_time'] = server_time_moscow.isoformat()
        context['server_timezone'] = 'Europe/Moscow'
        
        return context
class AddTimeSlotView(DoctorRequiredMixin, View):
    template_name = 'scheduling/add_timeslot.html'
    
    def get(self, request, doctor_id):
        import json
        from .models import Room
        doctor = get_object_or_404(Doctor, pk=doctor_id)
        
        rooms = Room.objects.all().order_by('room_number').values_list('room_number', flat=True)
        return render(request, self.template_name, {
            'doctor': doctor,
            'existing_rooms_json': json.dumps(list(rooms))
        })
    def post(self, request, doctor_id):
        import json
        from .models import Room
        
        doctor = get_object_or_404(Doctor, pk=doctor_id)
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
                except:
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
            from django.utils import timezone as tz
            # Создаем naive datetime и используем стандартный метод Django для конвертации
            # tz.make_aware() использует TIME_ZONE из settings (Europe/Moscow)
            # Django автоматически конвертирует его в UTC при сохранении в БД
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
            from django.utils import timezone as tz
            # Создаем naive datetime и используем стандартный метод Django для конвертации
            # tz.make_aware() использует TIME_ZONE из settings (Europe/Moscow)
            # Django автоматически конвертирует его в UTC при сохранении в БД
            current_time = datetime.combine(date, day_start)
            end_time = datetime.combine(date, day_end)
            break_start_dt = datetime.combine(date, break_start) if break_start else None
            break_end_dt = datetime.combine(date, break_end) if break_end else None
            
            # Делаем datetime aware с локальным часовым поясом (Europe/Moscow)
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
@method_decorator(require_http_methods(['GET', 'POST']), name='dispatch')
class BookAppointmentView(PatientRequiredMixin, View):
    template_name = 'clinic/appointment_form.html'
    
    def get(self, request):
        step = request.GET.get('step', '1')
        step = int(step) if step.isdigit() else 1
        

        session_data = request.session.get('appointment_data', {})
        
        user = request.user
        from staff.models import Specialization
        specializations = Specialization.objects.all().order_by('name')
        
        context = {
            'step': step,
            'session_data': session_data,
            'specializations': specializations,
        }
        

        if step == 1:
            context['selected_spec'] = session_data.get('specialization_id')
            return render(request, self.template_name, context)
        elif step == 2:
            spec_id = session_data.get('specialization_id')
            if not spec_id:
                return redirect('{}?step=1'.format(reverse('scheduling:book_appointment')))
            doctors = Doctor.objects.filter(specialization_id=spec_id).select_related('user', 'specialization').order_by('lname', 'fname')
            context['doctors'] = doctors
            context['selected_doctor'] = session_data.get('doctor_id')
            context['selected_spec'] = spec_id
            return render(request, self.template_name, context)
        elif step == 3:
            import json
            doctor_id = session_data.get('doctor_id')
            if not doctor_id:
                return redirect('{}?step=2'.format(reverse('scheduling:book_appointment')))
            doctor = get_object_or_404(Doctor, pk=doctor_id)
            from django.utils import timezone
            now = timezone.now()
            slots_qs = AppointmentSchedule.objects.filter(
                doctor_id=doctor_id,
                appointment__isnull=True,
                time_from__gte=now
            ).select_related('doctor', 'room').order_by('time_from')
            

            slots_data = []
            available_dates_set = set()
            for slot in slots_qs:
                # Конвертируем время в московский часовой пояс
                moscow_time_from = to_moscow_time(slot.time_from)
                slot_date = moscow_time_from.date()
                available_dates_set.add(slot_date.isoformat())
                moscow_time_to = to_moscow_time(slot.time_to) if slot.time_to else None
                slots_data.append({
                        'id': slot.id,
                    'date': slot_date.isoformat(),
                        'time_from': moscow_time_from.isoformat(),
                        'time_from_str': moscow_time_from.strftime('%H:%M'),
                        'time_to_str': moscow_time_to.strftime('%H:%M') if moscow_time_to else '',
                    'room': slot.room.room_number if slot.room else None,
                })
            available_dates_list = sorted(list(available_dates_set))
            
            # Передаем текущее время сервера в московском часовом поясе для сравнения в JavaScript
            server_now_local = moscow_now()
            
            context['doctor'] = doctor
            context['slots_json'] = json.dumps(slots_data)
            context['available_dates_json'] = json.dumps(available_dates_list)
            context['server_now'] = server_now_local.isoformat()
            context['selected_slot'] = session_data.get('slot_id')
            context['selected_date'] = session_data.get('selected_date')
            return render(request, self.template_name, context)
        elif step == 4:
            slot_id = session_data.get('slot_id')
            if not slot_id:
                return redirect('{}?step=3'.format(reverse('scheduling:book_appointment')))
            is_authenticated = user.is_authenticated
            if is_authenticated and hasattr(user, 'patient_profile'):
                patient = user.patient_profile
                all_patients = [patient] + list(patient.children())
            else:
                all_patients = []
            context['all_patients'] = all_patients
            context['is_authenticated'] = is_authenticated
            context['session_data'] = session_data
            return render(request, self.template_name, context)
        return redirect('{}?step=1'.format(reverse('scheduling:book_appointment')))
    def post(self, request):
        action_type = request.POST.get('action')
        session_data = request.session.get('appointment_data', {})
        

        if action_type == 'step1':
            specialization_id = request.POST.get('specialization_id')
            if not specialization_id:
                return redirect('{}?step=1&error=Выберите специализацию'.format(reverse('scheduling:book_appointment')))
            session_data['specialization_id'] = specialization_id
            request.session['appointment_data'] = session_data
            return redirect('{}?step=2'.format(reverse('scheduling:book_appointment')))
        elif action_type == 'step2':
            doctor_id = request.POST.get('doctor_id')
            if not doctor_id:
                return redirect('{}?step=2&error=Выберите врача'.format(reverse('scheduling:book_appointment')))
            session_data['doctor_id'] = doctor_id
            request.session['appointment_data'] = session_data
            return redirect('{}?step=3'.format(reverse('scheduling:book_appointment')))
        elif action_type == 'step3':
            slot_id = request.POST.get('slot_id')
            selected_date = request.POST.get('selected_date')
            if not slot_id:
                return redirect('{}?step=3&error=Выберите время приема'.format(reverse('scheduling:book_appointment')))
            session_data['slot_id'] = slot_id
            session_data['selected_date'] = selected_date
            request.session['appointment_data'] = session_data
            return redirect('{}?step=4'.format(reverse('scheduling:book_appointment')))
        elif action_type == 'step4':
            create_new_patient = request.POST.get('create_new_patient')
            slot_id = session_data.get('slot_id')
            user = request.user
            is_authenticated = user.is_authenticated
            
            if not slot_id:
                return redirect('{}?step=3&error=Выберите время приема'.format(reverse('scheduling:book_appointment')))
            if not is_authenticated:
                create_new_patient = 'true'
            if create_new_patient == 'true':
                fname = request.POST.get('fname', '').strip()
                lname = request.POST.get('lname', '').strip()
                tname = request.POST.get('tname', '').strip()
                bdate_str = request.POST.get('bdate', '').strip()
                phone = request.POST.get('phone_number', '').strip()
                email = request.POST.get('email', '').strip()
                snils = request.POST.get('snils', '').strip()
                oms = request.POST.get('oms', '').strip()
                add_to_family = request.POST.get('add_to_family') == 'on'
                
                if not fname or not lname or not bdate_str or not snils or not oms:
                    return redirect('{}?step=4&error=Заполните все обязательные поля'.format(reverse('scheduling:book_appointment')))
                if phone:
                    phone_digits = re.sub(r'\D', '', phone)
                    phone = phone_digits[:11] if phone_digits else None
                else:
                    phone = None
                try:
                    if '.' in bdate_str:
                        
                        bdate = datetime.strptime(bdate_str, '%d.%m.%Y').date()
                    elif '-' in bdate_str and len(bdate_str.split('-')[0]) == 4:
                        
                        bdate = datetime.strptime(bdate_str, '%Y-%m-%d').date()
                    elif '-' in bdate_str:
                        
                        bdate = datetime.strptime(bdate_str, '%d-%m-%Y').date()
                    else:
                        return redirect('{}?step=4&error=Неверный формат даты рождения. Используйте формат дд.мм.гггг'.format(reverse('scheduling:book_appointment')))
                except ValueError:
                    return redirect('{}?step=4&error=Неверный формат даты рождения. Используйте формат дд.мм.гггг'.format(reverse('scheduling:book_appointment')))
                try:
                    
                    patient = Patient(
                        fname=fname,
                        lname=lname,
                        tname=tname or None,
                        bdate=bdate,
                        phone_number=phone,
                        email=email or None,
                        snils=snils,
                        oms=oms
                    )
                    patient.save()
                    

                    if is_authenticated and add_to_family and hasattr(user, 'patient_profile'):
                        patient.add_parent(user.patient_profile)
                    patient_id = patient.id
                except (IntegrityError, DatabaseError) as e:
                    error_msg = str(e).lower()
                    if 'snils' in error_msg or ('unique constraint' in error_msg and 'snils' in error_msg):
                        return redirect('{}?step=4&error=Пациент с таким СНИЛС уже существует'.format(reverse('scheduling:book_appointment')))
                    elif 'oms' in error_msg or ('unique constraint' in error_msg and 'oms' in error_msg):
                        return redirect('{}?step=4&error=Пациент с таким ОМС уже существует'.format(reverse('scheduling:book_appointment')))
                    elif 'phone' in error_msg:
                        return redirect('{}?step=4&error=Неверный формат телефона'.format(reverse('scheduling:book_appointment')))
                    else:
                        return redirect('{}?step=4&error=Ошибка при создании пациента: данные уже существуют в базе'.format(reverse('scheduling:book_appointment')))
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'phone' in error_msg:
                        return redirect('{}?step=4&error=Неверный формат телефона'.format(reverse('scheduling:book_appointment')))
                    return redirect('{}?step=4&error=Ошибка при создании пациента: {}'.format(reverse('scheduling:book_appointment'), str(e)))
            else:
                patient_id = request.POST.get('patient_id')
                if not patient_id:
                    return redirect('{}?step=4&error=Выберите пациента'.format(reverse('scheduling:book_appointment')))
                try:
                    patient = Patient.objects.get(pk=patient_id)
                except Patient.DoesNotExist:
                    return redirect('{}?step=4&error=Пациент не найден'.format(reverse('scheduling:book_appointment')))
                if is_authenticated and hasattr(user, 'patient_profile'):
                    user_patient = user.patient_profile
                    all_patients = [user_patient] + list(user_patient.children())
                    if patient not in all_patients:
                        return redirect('{}?step=4&error=Нет доступа к этому пациенту'.format(reverse('scheduling:book_appointment')))
            try:
                from django.utils import timezone
                slot = AppointmentSchedule.objects.get(pk=slot_id)
                

                if slot.time_from < timezone.now():
                    return redirect('{}?step=3&error=Нельзя записаться на прошедшее время'.format(reverse('scheduling:book_appointment')))
                appointment = Appointment.objects.create(
                    patient=patient,
                    doctor=slot.doctor,
                    slot=slot,
                    date=slot.time_from,
                    status='booked'
                )
                

                request.session.pop('appointment_data', None)
                

                if not is_authenticated:
                    return redirect('scheduling:offer_account_creation', pk=appointment.pk)
                return redirect('scheduling:appointment_info', pk=appointment.pk)
            except IntegrityError as e:
                error_msg = str(e)
                if 'unique constraint' in error_msg.lower() or 'duplicate' in error_msg.lower():
                    return redirect('{}?step=4&error=Эта запись уже существует. Возможно, выбранное время уже занято'.format(reverse('scheduling:book_appointment')))
                else:
                    return redirect('{}?step=4&error=Ошибка при создании записи: данные уже существуют в базе'.format(reverse('scheduling:book_appointment')))
            except Exception as e:
                return redirect('{}?step=4&error=Ошибка при создании записи: {}'.format(reverse('scheduling:book_appointment'), str(e)))
        return redirect('{}?step=1'.format(reverse('scheduling:book_appointment')))
@method_decorator(require_http_methods(['POST']), name='dispatch')
class BookForOtherDoctorView(DoctorRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        from django.utils import timezone
        from django.contrib import messages
        current_appointment_id = request.POST.get('current_appointment_id')
        target_slot_id = request.POST.get('target_slot_id')
        current = get_object_or_404(Appointment, pk=current_appointment_id)
        slot = get_object_or_404(AppointmentSchedule, pk=target_slot_id)
        

        if slot.time_from < timezone.now():
            messages.error(request, 'Нельзя записаться на прошедшее время')
            return redirect(reverse('scheduling:doctor_schedule', args=[slot.doctor.pk]))
        new_appointment = Appointment(patient=current.patient, slot=slot, date=slot.time_from)
        new_appointment.save()
        return redirect(reverse('scheduling:doctor_schedule', args=[slot.doctor.pk]))
class AppointmentDetailView(DoctorRequiredMixin, View):
    template_name = 'scheduling/appointment_detail.html'
    
    def get(self, request, pk):
        import json
        from collections import defaultdict
        appointment = get_object_or_404(Appointment, pk=pk)
        doctor = request.user.doctor_profile
        

        if appointment.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        try:
            recipe = Recipe.objects.get(appointment=appointment)
        except Recipe.DoesNotExist:
            recipe = None
        from django.utils import timezone
        available_slots_qs = AppointmentSchedule.objects.filter(
            doctor=doctor,
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('room').order_by('time_from')
        

        next_slots_data = []
        next_available_dates_set = set()
        for slot in available_slots_qs:
            # Конвертируем время в московское
            moscow_time_from = to_moscow_time(slot.time_from)
            moscow_time_to = to_moscow_time(slot.time_to) if slot.time_to else None
            slot_date = moscow_time_from.date()
            next_available_dates_set.add(slot_date.isoformat())
            next_slots_data.append({
                'id': slot.id,
                'date': slot_date.isoformat(),
                'time_from': moscow_time_from.isoformat(),
                'time_from_str': moscow_time_from.strftime('%H:%M'),
                'time_to_str': moscow_time_to.strftime('%H:%M') if moscow_time_to else '',
                'room': slot.room.room_number if slot.room else None,
            })
        next_available_dates_list = sorted(list(next_available_dates_set))
        

        from staff.models import Specialization
        # Получаем только те специальности, у которых есть врачи (кроме текущего врача)
        # Используем prefetch_related для оптимизации запросов
        specializations = Specialization.objects.filter(
            doctor__isnull=False
        ).exclude(
            doctor__id=doctor.id
        ).prefetch_related('doctor_set').distinct().order_by('name')
        

        referral_specialization_id = request.GET.get('referral_specialization')
        referral_doctor_id = request.GET.get('referral_doctor')
        all_doctors = Doctor.objects.exclude(id=doctor.id).select_related('specialization').order_by('lname', 'fname')
        if referral_specialization_id:
            all_doctors = all_doctors.filter(specialization_id=referral_specialization_id)
        referral_slots_data = []
        referral_available_dates_set = set()
        referral_doctor = None
        if referral_doctor_id:
            try:
                referral_doctor = Doctor.objects.get(pk=referral_doctor_id)
                referral_slots_qs = AppointmentSchedule.objects.filter(
                    doctor=referral_doctor,
                    appointment__isnull=True,
                    time_from__gte=timezone.now()
                ).select_related('room').order_by('time_from')
                
                for slot in referral_slots_qs:
                    # Конвертируем время в московское
                    moscow_time_from = to_moscow_time(slot.time_from)
                    moscow_time_to = to_moscow_time(slot.time_to) if slot.time_to else None
                    slot_date = moscow_time_from.date()
                    referral_available_dates_set.add(slot_date.isoformat())
                    referral_slots_data.append({
                        'id': slot.id,
                        'date': slot_date.isoformat(),
                        'time_from': moscow_time_from.isoformat(),
                        'time_from_str': moscow_time_from.strftime('%H:%M'),
                        'time_to_str': moscow_time_to.strftime('%H:%M') if moscow_time_to else '',
                        'room': slot.room.room_number if slot.room else None,
                    })
            except Doctor.DoesNotExist:
                referral_doctor_id = None
        referral_available_dates_list = sorted(list(referral_available_dates_set))
        

        diagnoses = Diagnosis.objects.all().order_by('name')
        

        all_doctors_data = []
        for doc in Doctor.objects.exclude(id=doctor.id).select_related('specialization').order_by('lname', 'fname'):
            all_doctors_data.append({
                'id': doc.id,
                'name': f'{doc.lname} {doc.fname}',
                'specialization_id': doc.specialization.id,
                'specialization_name': doc.specialization.name,
            })
        context = {
            'appointment': appointment,
            'recipe': recipe,
            'next_slots_json': json.dumps(next_slots_data),
            'next_available_dates_json': json.dumps(next_available_dates_list),
            'all_doctors': all_doctors,
            'all_doctors_json': json.dumps(all_doctors_data),
            'specializations': specializations,
            'diagnoses': diagnoses,
            'referral_slots_json': json.dumps(referral_slots_data),
            'referral_available_dates_json': json.dumps(referral_available_dates_list),
            'referral_doctor_id': referral_doctor_id,
            'referral_specialization_id': referral_specialization_id,
        }
        return render(request, self.template_name, context)


@method_decorator(require_http_methods(['POST']), name='dispatch')
class UpdateAppointmentStatusView(DoctorRequiredMixin, View):
    def post(self, request, pk):
        from django.utils import timezone
        from django.contrib import messages
        appointment = get_object_or_404(Appointment, pk=pk)
        doctor = request.user.doctor_profile
        

        if appointment.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        
        # Простое изменение статуса (для начала приема)
        new_status = request.POST.get('status')
        if new_status and new_status in ['booked', 'in_progress', 'completed', 'cancelled']:
            appointment.status = new_status
            if new_status == 'cancelled' and appointment.slot:
                appointment.slot = None
            appointment.save()
            
            if new_status == 'in_progress':
                messages.success(request, 'Прием начат')
                return redirect('scheduling:appointment_detail', pk=pk)
            else:
                messages.success(request, f'Статус изменен на "{appointment.get_status_display()}"')
                return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        
        # Обработка рецепта (для завершения приема)
        # Рецепт можно заполнить только для завершенных приемов
        if appointment.status != 'completed':
            messages.error(request, 'Рецепт можно заполнить только для завершенных приемов')
            return redirect('scheduling:appointment_detail', pk=pk)
        
        diagnosis_id = request.POST.get('diagnosis')
        diagnosis_text = request.POST.get('diagnosis_text', '').strip()
        

        if not diagnosis_id and diagnosis_text:
            try:
                diagnosis = Diagnosis.objects.get(name__iexact=diagnosis_text)
                diagnosis_id = str(diagnosis.id)
            except Diagnosis.DoesNotExist:
                pass
        try:
            recipe = Recipe.objects.get(appointment=appointment)
        except Recipe.DoesNotExist:
            
            if not diagnosis_id:
                messages.error(request, 'Необходимо выбрать диагноз')
                return redirect('scheduling:appointment_detail', pk=pk)
            diagnosis = get_object_or_404(Diagnosis, pk=diagnosis_id)
            recipe = Recipe.objects.create(appointment=appointment, diagnosis=diagnosis)
        if diagnosis_id:
            recipe.diagnosis = get_object_or_404(Diagnosis, pk=diagnosis_id)
        elif not recipe.diagnosis:
            
            messages.error(request, 'Необходимо выбрать диагноз')
            return redirect('scheduling:appointment_detail', pk=pk)
        complaints = request.POST.get('complaints', '').strip()
        recommendations = request.POST.get('recommendations', '').strip()
        recipe.complaints = complaints if complaints else None
        recipe.recommendations = recommendations if recommendations else None
        

        enable_next_appointment = request.POST.get('enable_next_appointment') == 'on'
        if enable_next_appointment:
            next_slot_id = request.POST.get('next_appointment_slot')
            if next_slot_id:
                next_slot = get_object_or_404(AppointmentSchedule, pk=next_slot_id)
                
                if next_slot.time_from < timezone.now():
                    from django.contrib import messages
                    messages.error(request, 'Нельзя записаться на прошедшее время')
                    return redirect('scheduling:appointment_detail', pk=pk)
                if next_slot.doctor == doctor and next_slot.is_available():
                    recipe.next_appointment_slot = next_slot
                    
                    if not Appointment.objects.filter(slot=next_slot).exists():
                        new_appointment = Appointment(
                            patient=appointment.patient,
                            doctor=doctor,
                            slot=next_slot,
                            date=next_slot.time_from,
                            status='booked'
                        )
                        new_appointment.save()
            else:
                recipe.next_appointment_slot = None
        else:
            recipe.next_appointment_slot = None
        enable_referral = request.POST.get('enable_referral') == 'on'
        if enable_referral:
            referral_doctor_id = request.POST.get('referral_doctor')
            referral_slot_id = request.POST.get('referral_slot')
            if referral_doctor_id and referral_slot_id:
                referral_doctor = get_object_or_404(Doctor, pk=referral_doctor_id)
                referral_slot = get_object_or_404(AppointmentSchedule, pk=referral_slot_id)
                
                if referral_slot.time_from < timezone.now():
                    messages.error(request, 'Нельзя записаться на прошедшее время')
                    return redirect('scheduling:appointment_detail', pk=pk)
                if referral_slot.doctor == referral_doctor and referral_slot.is_available():
                    recipe.referral_doctor = referral_doctor
                    recipe.referral_slot = referral_slot
                    
                    if not Appointment.objects.filter(slot=referral_slot).exists():
                        new_appointment = Appointment(
                            patient=appointment.patient,
                            doctor=referral_doctor,
                            slot=referral_slot,
                            date=referral_slot.time_from,
                            status='booked'
                        )
                        new_appointment.save()
            else:
                recipe.referral_doctor = None
                recipe.referral_slot = None
        else:
            recipe.referral_doctor = None
            recipe.referral_slot = None
        recipe.save()
        
        # Меняем статус приема на завершенный при сохранении рецепта
        if appointment.status != 'completed':
            appointment.status = 'completed'
            appointment.save()
        
        messages.success(request, 'Прием завершен')
        return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
class GetReferralSlotsView(DoctorRequiredMixin, View):
    def get(self, request, doctor_id):
        from django.utils import timezone
        
        doctor = get_object_or_404(Doctor, pk=doctor_id)
        
        slots = AppointmentSchedule.objects.filter(
            doctor=doctor,
            appointment__isnull=True,
            time_from__gte=timezone.now()
        ).select_related('room').order_by('time_from')
        
        slots_data = []
        available_dates_set = set()
        for slot in slots:
            # Конвертируем время в московское
            moscow_time_from = to_moscow_time(slot.time_from)
            moscow_time_to = to_moscow_time(slot.time_to) if slot.time_to else None
            slot_date = moscow_time_from.date()
            available_dates_set.add(slot_date.isoformat())
            slots_data.append({
                'id': slot.id,
                'date': slot_date.isoformat(),
                'time_from': moscow_time_from.isoformat(),
                'time_from_str': moscow_time_from.strftime('%H:%M'),
                'time_to_str': moscow_time_to.strftime('%H:%M') if moscow_time_to else '',
                'room': slot.room.room_number if slot.room else None,
            })
        
        available_dates_list = sorted(list(available_dates_set))
        
        return JsonResponse({
            'slots': slots_data,
            'available_dates': available_dates_list
        }, safe=False)


class OfferAccountCreationView(View):
    template_name = 'scheduling/offer_account_creation.html'
    
    def get(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        
        if request.user.is_authenticated:
            return redirect('scheduling:appointment_detail', pk=pk)
        context = {
            'appointment': appointment,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        action = request.POST.get('action')
        appointment = get_object_or_404(Appointment, pk=pk)
        
        if action == 'create_account':
            request.session['appointment_id_after_registration'] = pk
            return redirect('accounts:register')
        elif action == 'skip':
            return redirect('scheduling:appointment_info', pk=pk)
        return redirect('scheduling:offer_account_creation', pk=pk)


class AppointmentInfoView(View):
    template_name = 'scheduling/appointment_info.html'
    
    def get(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        user = request.user
        
        # Проверка прав доступа
        has_permission = False
        
        # Пациенты могут видеть свои приёмы и приёмы своих детей
        if hasattr(user, 'patient_profile'):
            patient = user.patient_profile
            all_patients = [patient] + list(patient.children())
            if appointment.patient in all_patients:
                has_permission = True
        
        # Докторы могут видеть приёмы своих пациентов
        elif hasattr(user, 'doctor_profile'):
            doctor = user.doctor_profile
            if appointment.doctor == doctor:
                has_permission = True
        
        # Админы могут видеть все приёмы
        elif user.is_authenticated and getattr(user, 'role', None) == 'admin':
            has_permission = True
        
        if not has_permission:
            return HttpResponseForbidden('Доступ запрещён')
        
        # Если запрос JSON (для pop-up)
        if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
            try:
                recipe = Recipe.objects.get(appointment=appointment)
                recipe_data = {
                    'id': recipe.id,
                    'diagnosis': {
                        'id': recipe.diagnosis.id,
                        'name': recipe.diagnosis.name
                    } if recipe.diagnosis else None,
                    'complaints': recipe.complaints or '',
                    'recommendations': recipe.recommendations or '',
                    'next_appointment': {
                        'id': recipe.next_appointment_slot.id,
                        'date': recipe.next_appointment_slot.time_from.strftime('%d.%m.%Y %H:%M'),
                        'room': recipe.next_appointment_slot.room.room_number if recipe.next_appointment_slot.room else None
                    } if recipe.next_appointment_slot else None,
                    'referral_doctor': {
                        'id': recipe.referral_doctor.id,
                        'name': f"{recipe.referral_doctor.lname} {recipe.referral_doctor.fname}",
                        'specialization': recipe.referral_doctor.specialization.name if recipe.referral_doctor.specialization else None
                    } if recipe.referral_doctor else None,
                    'referral_slot': {
                        'id': recipe.referral_slot.id,
                        'date': recipe.referral_slot.time_from.strftime('%d.%m.%Y %H:%M'),
                        'room': recipe.referral_slot.room.room_number if recipe.referral_slot.room else None
                    } if recipe.referral_slot else None,
                }
            except Recipe.DoesNotExist:
                recipe_data = None
            
            return JsonResponse({
                'id': appointment.id,
                'patient': {
                    'id': appointment.patient.id,
                    'name': f"{appointment.patient.lname} {appointment.patient.fname} {appointment.patient.tname or ''}".strip(),
                    'bdate': appointment.patient.bdate.strftime('%d.%m.%Y') if appointment.patient.bdate else None,
                    'snils': appointment.patient.snils,
                    'oms': appointment.patient.oms
                },
                'doctor': {
                    'id': appointment.doctor.id,
                    'name': f"{appointment.doctor.lname} {appointment.doctor.fname}",
                    'specialization': appointment.doctor.specialization.name if appointment.doctor.specialization else None
                },
                'date': appointment.date.strftime('%d.%m.%Y %H:%M'),
                'status': appointment.status,
                'status_display': appointment.get_status_display(),
                'room': appointment.slot.room.room_number if appointment.slot and appointment.slot.room else None,
                'recipe': recipe_data
            })
        
        context = {
            'appointment': appointment,
            'clinic_phone': '8 (800) 707-56-27',  # Можно вынести в настройки
            'clinic_phone_url': '+78007075627',  # Для tel: ссылки
            'clinic_email': 'info@clinicsirius.ru',  # Можно вынести в настройки
            'is_authenticated': user.is_authenticated,
            'is_doctor': hasattr(user, 'doctor_profile'),
            'is_admin': getattr(user, 'role', None) == 'admin',
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)
        user = request.user
        
        if hasattr(user, 'patient_profile'):
            patient = user.patient_profile
            all_patients = [patient] + list(patient.children())
            if appointment.patient not in all_patients:
                return HttpResponseBadRequest('Доступ запрещён')
        appointment.delete()
        

        referer = request.META.get('HTTP_REFERER', reverse('index'))
        if '?' in referer:
            return redirect(f"{referer}&success=Запись успешно отменена")
        else:
            return redirect(f"{referer}?success=Запись успешно отменена")


class CancelAppointmentView(View):
    def post(self, request, pk):
        from django.contrib import messages
        
        appointment = get_object_or_404(Appointment, pk=pk)
        user = request.user
        
        if not user.is_authenticated:
            messages.error(request, 'Необходима авторизация')
            return redirect('accounts:login')
        
        has_permission = False
        
        if hasattr(user, 'patient_profile'):
            patient = user.patient_profile
            all_patients = [patient] + list(patient.children())
            if appointment.patient in all_patients:
                has_permission = True
        elif hasattr(user, 'doctor_profile'):
            doctor = user.doctor_profile
            if appointment.doctor == doctor:
                has_permission = True
        
        if not has_permission:
            messages.error(request, 'У вас нет прав для отмены этой записи')
            referer = request.META.get('HTTP_REFERER', reverse('index'))
            return redirect(referer)
        
        appointment.status = Appointment.STATUS_CANCELLED
        if appointment.slot:
            appointment.slot = None
        appointment.save()
        
        messages.success(request, 'Запись успешно отменена')
        referer = request.META.get('HTTP_REFERER', reverse('index'))
        if '?' in referer:
            return redirect(f"{referer}&success=Запись успешно отменена")
        else:
            return redirect(f"{referer}?success=Запись успешно отменена")


@method_decorator(require_http_methods(['GET', 'POST']), name='dispatch')
class BookSlotView(LoginRequiredMixin, View):
    template_name = 'scheduling/book_slot.html'
    login_url = 'accounts:login'
    
    def get(self, request, slot_id):
        from django.utils import timezone
        slot = get_object_or_404(AppointmentSchedule, pk=slot_id)
        user = request.user
        role = getattr(user, 'role', None)
        
        # Для докторов - форма записи пациента
        if role == 'doctor':
            doctor = getattr(user, 'doctor_profile', None)
            if not doctor:
                return HttpResponseBadRequest('Профиль врача не найден')
            
            if slot.doctor != doctor:
                return HttpResponseBadRequest('Доступ запрещён')
            
            if not slot.is_available():
                messages.error(request, 'Этот слот уже занят')
                return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
            
            # Проверяем, не прошел ли слот по времени
            if slot.time_from < timezone.now():
                messages.error(request, 'Нельзя записаться на прошедшее время')
                return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
            
            all_patients = Patient.objects.all().order_by('lname', 'fname')
            
            context = {
                'slot': slot,
                'doctor': doctor,
                'all_patients': all_patients,
            }
            return render(request, self.template_name, context)
        
        # Для пациентов - простая запись на себя
        elif role == 'patient':
            patient = getattr(user, 'patient_profile', None)
            if not patient:
                messages.error(request, 'Профиль пациента не найден')
                return redirect('index')
            
            if not slot.is_available():
                messages.error(request, 'Этот слот уже занят')
                referer = request.META.get('HTTP_REFERER', reverse('index'))
                return redirect(referer)
            
            from django.utils import timezone
            if slot.time_from < timezone.now():
                messages.error(request, 'Нельзя записаться на прошедшее время')
                referer = request.META.get('HTTP_REFERER', reverse('index'))
                return redirect(referer)
            
            existing_appointment = Appointment.objects.filter(
                patient=patient,
                slot=slot
            ).first()
            
            if existing_appointment:
                messages.info(request, 'У вас уже есть запись на это время')
                return redirect('scheduling:appointment_detail', pk=existing_appointment.pk)
            
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=slot.doctor,
                slot=slot,
                date=slot.time_from,
                status=Appointment.STATUS_BOOKED
            )
            
            messages.success(request, 'Запись успешно создана')
            return redirect('scheduling:appointment_detail', pk=appointment.pk)
        
        else:
            return HttpResponseBadRequest('Доступ запрещён')
    
    def post(self, request, slot_id):
        from django.contrib import messages
        from django.utils import timezone
        
        slot = get_object_or_404(AppointmentSchedule, pk=slot_id)
        user = request.user
        role = getattr(user, 'role', None)
        
        # Для докторов - запись пациента
        if role == 'doctor':
            doctor = getattr(user, 'doctor_profile', None)
            if not doctor or slot.doctor != doctor:
                return HttpResponseBadRequest('Доступ запрещён')
            
            if not slot.is_available():
                messages.error(request, 'Этот слот уже занят')
                return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
            
            # Проверяем, не прошел ли слот по времени
            if slot.time_from < timezone.now():
                messages.error(request, 'Нельзя записаться на прошедшее время')
                return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
            
            # Используем логику из UpdateAppointmentPatientView
            create_new = request.POST.get('create_new_patient') == 'true'
            all_patients = Patient.objects.all().order_by('lname', 'fname')
            
            if create_new:
                fname = request.POST.get('fname', '').strip()
                lname = request.POST.get('lname', '').strip()
                tname = request.POST.get('tname', '').strip()
                bdate_str = request.POST.get('bdate', '').strip()
                phone = request.POST.get('phone_number', '').strip()
                email = request.POST.get('email', '').strip()
                snils = request.POST.get('snils', '').strip()
                oms = request.POST.get('oms', '').strip()
                
                if not fname or not lname or not bdate_str or not snils or not oms:
                    return render(request, self.template_name, {
                        'slot': slot,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Заполните все обязательные поля'
                    })
                
                if phone:
                    phone = re.sub(r'\D', '', phone)[:11] if re.sub(r'\D', '', phone) else None
                
                try:
                    if '.' in bdate_str:
                        bdate = datetime.strptime(bdate_str, '%d.%m.%Y').date()
                    elif '-' in bdate_str and len(bdate_str.split('-')[0]) == 4:
                        bdate = datetime.strptime(bdate_str, '%Y-%m-%d').date()
                    elif '-' in bdate_str:
                        bdate = datetime.strptime(bdate_str, '%d-%m-%Y').date()
                    else:
                        raise ValueError
                except ValueError:
                    return render(request, self.template_name, {
                        'slot': slot,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Неверный формат даты рождения'
                    })
                
                try:
                    patient = Patient.objects.create(
                        fname=fname,
                        lname=lname,
                        tname=tname or None,
                        bdate=bdate,
                        phone_number=phone,
                        email=email or None,
                        snils=snils,
                        oms=oms
                    )
                except (IntegrityError, DatabaseError) as e:
                    error_msg = str(e).lower()
                    if 'snils' in error_msg:
                        error = 'Пациент с таким СНИЛС уже существует'
                    elif 'oms' in error_msg:
                        error = 'Пациент с таким ОМС уже существует'
                    elif 'phone' in error_msg:
                        error = 'Неверный формат телефона'
                    else:
                        error = 'Ошибка при создании пациента'
                    return render(request, self.template_name, {
                        'slot': slot,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': error
                    })
            else:
                patient_id = request.POST.get('patient_id')
                if not patient_id:
                    return render(request, self.template_name, {
                        'slot': slot,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Выберите пациента'
                    })
                
                try:
                    patient = Patient.objects.get(pk=patient_id)
                except Patient.DoesNotExist:
                    return render(request, self.template_name, {
                        'slot': slot,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Пациент не найден'
                    })
            
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                slot=slot,
                date=slot.time_from,
                status=Appointment.STATUS_BOOKED
            )
            
            messages.success(request, 'Запись успешно создана')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        
        # Для пациентов - запись на себя
        elif role == 'patient':
            patient = getattr(user, 'patient_profile', None)
            if not patient:
                messages.error(request, 'Профиль пациента не найден')
                return redirect('index')
            
            if not slot.is_available():
                messages.error(request, 'Этот слот уже занят')
                referer = request.META.get('HTTP_REFERER', reverse('index'))
                return redirect(referer)
            
            if slot.time_from < timezone.now():
                messages.error(request, 'Нельзя записаться на прошедшее время')
                referer = request.META.get('HTTP_REFERER', reverse('index'))
                return redirect(referer)
            
            existing_appointment = Appointment.objects.filter(
                patient=patient,
                slot=slot
            ).first()
            
            if existing_appointment:
                messages.info(request, 'У вас уже есть запись на это время')
                return redirect('scheduling:appointment_detail', pk=existing_appointment.pk)
            
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=slot.doctor,
                slot=slot,
                date=slot.time_from,
                status=Appointment.STATUS_BOOKED
            )
            
            messages.success(request, 'Запись успешно создана')
            return redirect('scheduling:appointment_detail', pk=appointment.pk)
        
        else:
            return HttpResponseBadRequest('Доступ запрещён')


class UpdateAppointmentPatientView(PatientRequiredMixin, View):
    template_name = 'scheduling/book_slot.html'
    
    def get(self, request, slot_id):
        slot = get_object_or_404(AppointmentSchedule, pk=slot_id)
        doctor = request.user.doctor_profile
        

        if slot.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        if not slot.is_available():
            messages.error(request, 'Этот слот уже занят')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        all_patients = Patient.objects.all().order_by('lname', 'fname')
        
        context = {
            'slot': slot,
            'doctor': doctor,
            'all_patients': all_patients,
        }
        return render(request, self.template_name, context)
    def post(self, request, slot_id):
        slot = get_object_or_404(AppointmentSchedule, pk=slot_id)
        doctor = request.user.doctor_profile
        

        if slot.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        if not slot.is_available():
            messages.error(request, 'Этот слот уже занят')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        create_new = request.POST.get('create_new_patient') == 'true'
        
        if create_new:
            
            fname = request.POST.get('fname', '').strip()
            lname = request.POST.get('lname', '').strip()
            tname = request.POST.get('tname', '').strip()
            bdate_str = request.POST.get('bdate', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            email = request.POST.get('email', '').strip()
            snils = request.POST.get('snils', '').strip()
            oms = request.POST.get('oms', '').strip()
            
            if not fname or not lname or not bdate_str or not snils or not oms:
                messages.error(request, 'Заполните все обязательные поля')
                all_patients = Patient.objects.all().order_by('lname', 'fname')
                return render(request, self.template_name, {
                    'slot': slot,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': 'Заполните все обязательные поля'
                })
            if phone:
                phone = re.sub(r'\D', '', phone)[:11] if re.sub(r'\D', '', phone) else None
            try:
                if '.' in bdate_str:
                    bdate = datetime.strptime(bdate_str, '%d.%m.%Y').date()
                elif '-' in bdate_str and len(bdate_str.split('-')[0]) == 4:
                    bdate = datetime.strptime(bdate_str, '%Y-%m-%d').date()
                elif '-' in bdate_str:
                    bdate = datetime.strptime(bdate_str, '%d-%m-%Y').date()
                else:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Неверный формат даты рождения')
                all_patients = Patient.objects.all().order_by('lname', 'fname')
                return render(request, self.template_name, {
                    'slot': slot,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': 'Неверный формат даты рождения'
                })
            try:
                patient = Patient.objects.create(
                    fname=fname,
                    lname=lname,
                    tname=tname or None,
                    bdate=bdate,
                    phone_number=phone,
                    email=email or None,
                    snils=snils,
                    oms=oms
                )
            except (IntegrityError, DatabaseError) as e:
                error_msg = str(e).lower()
                if 'snils' in error_msg:
                    messages.error(request, 'Пациент с таким СНИЛС уже существует')
                elif 'oms' in error_msg:
                    messages.error(request, 'Пациент с таким ОМС уже существует')
                elif 'phone' in error_msg:
                    messages.error(request, 'Неверный формат телефона')
                else:
                    messages.error(request, 'Ошибка при создании пациента')
                all_patients = Patient.objects.all().order_by('lname', 'fname')
                error_display = 'Неверный формат телефона' if 'phone' in error_msg else 'Ошибка при создании пациента'
                return render(request, self.template_name, {
                    'slot': slot,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': error_display
                })
        else:
            
            patient_id = request.POST.get('patient_id')
            if not patient_id:
                messages.error(request, 'Выберите пациента')
                all_patients = Patient.objects.all().order_by('lname', 'fname')
                return render(request, self.template_name, {
                    'slot': slot,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': 'Выберите пациента'
                })
            try:
                patient = Patient.objects.get(pk=patient_id)
            except Patient.DoesNotExist:
                messages.error(request, 'Пациент не найден')
                all_patients = Patient.objects.all().order_by('lname', 'fname')
                return render(request, self.template_name, {
                    'slot': slot,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': 'Пациент не найден'
                })
        try:
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                slot=slot,
                date=slot.time_from,
                status='booked'
            )
            messages.success(request, f'Пациент {patient.lname} {patient.fname} записан на прием')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        except IntegrityError:
            messages.error(request, 'Ошибка при создании записи. Возможно, слот уже занят.')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        except Exception as e:
            messages.error(request, f'Ошибка при создании записи: {str(e)}')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)


@method_decorator(require_http_methods(['GET', 'POST']), name='dispatch')
class ChangeBookedAppointmentPatientView(DoctorRequiredMixin, View):
    template_name = 'scheduling/change_appointment_patient.html'
    
    def get(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        doctor = request.user.doctor_profile
        
        if appointment.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        
        if appointment.status != 'booked':
            messages.error(request, 'Можно изменить пациента только для забронированных записей')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        
        all_patients = Patient.objects.all().order_by('lname', 'fname')
        
        context = {
            'appointment': appointment,
            'doctor': doctor,
            'all_patients': all_patients,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        doctor = request.user.doctor_profile
        
        if appointment.doctor != doctor:
            return HttpResponseBadRequest('Доступ запрещён')
        
        # Проверяем, не передан ли action, если нет - считаем что это изменение пациента
        action = request.POST.get('action', 'change_patient')
        all_patients = Patient.objects.all().order_by('lname', 'fname')
        
        if action == 'change_status':
            new_status = request.POST.get('status')
            if new_status in ['booked', 'in_progress', 'completed', 'cancelled']:
                appointment.status = new_status
                if new_status == 'cancelled' and appointment.slot:
                    appointment.slot = None
                appointment.save()
                
                if new_status == 'in_progress':
                    messages.success(request, 'Прием начат')
                    return redirect('scheduling:appointment_detail', pk=appointment.pk)
                else:
                    messages.success(request, f'Статус изменен на "{appointment.get_status_display()}"')
                    return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        
        elif action == 'change_patient':
            if appointment.status != 'booked':
                return render(request, self.template_name, {
                    'appointment': appointment,
                    'doctor': doctor,
                    'all_patients': all_patients,
                    'error': 'Можно изменить пациента только для забронированных записей'
                })
            
            create_new = request.POST.get('create_new_patient') == 'true'
            
            if create_new:
                fname = request.POST.get('fname', '').strip()
                lname = request.POST.get('lname', '').strip()
                tname = request.POST.get('tname', '').strip()
                bdate_str = request.POST.get('bdate', '').strip()
                phone = request.POST.get('phone_number', '').strip()
                email = request.POST.get('email', '').strip()
                snils = request.POST.get('snils', '').strip()
                oms = request.POST.get('oms', '').strip()
                
                if not fname or not lname or not bdate_str or not snils or not oms:
                    return render(request, self.template_name, {
                        'appointment': appointment,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Заполните все обязательные поля'
                    })
                
                if phone:
                    phone = re.sub(r'\D', '', phone)[:11] if re.sub(r'\D', '', phone) else None
                
                try:
                    if '.' in bdate_str:
                        bdate = datetime.strptime(bdate_str, '%d.%m.%Y').date()
                    elif '-' in bdate_str and len(bdate_str.split('-')[0]) == 4:
                        bdate = datetime.strptime(bdate_str, '%Y-%m-%d').date()
                    elif '-' in bdate_str:
                        bdate = datetime.strptime(bdate_str, '%d-%m-%Y').date()
                    else:
                        raise ValueError
                except ValueError:
                    return render(request, self.template_name, {
                        'appointment': appointment,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Неверный формат даты рождения'
                    })
                
                try:
                    patient = Patient.objects.create(
                        fname=fname,
                        lname=lname,
                        tname=tname or None,
                        bdate=bdate,
                        phone_number=phone,
                        email=email or None,
                        snils=snils,
                        oms=oms
                    )
                except (IntegrityError, DatabaseError) as e:
                    error_msg = str(e).lower()
                    if 'snils' in error_msg:
                        error = 'Пациент с таким СНИЛС уже существует'
                    elif 'oms' in error_msg:
                        error = 'Пациент с таким ОМС уже существует'
                    elif 'phone' in error_msg:
                        error = 'Неверный формат телефона'
                    else:
                        error = 'Ошибка при создании пациента'
                    return render(request, self.template_name, {
                        'appointment': appointment,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': error
                    })
            else:
                patient_id = request.POST.get('patient_id')
                if not patient_id:
                    return render(request, self.template_name, {
                        'appointment': appointment,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Выберите пациента'
                    })
                
                try:
                    patient = Patient.objects.get(pk=patient_id)
                except Patient.DoesNotExist:
                    return render(request, self.template_name, {
                        'appointment': appointment,
                        'doctor': doctor,
                        'all_patients': all_patients,
                        'error': 'Пациент не найден'
                    })
            
            appointment.patient = patient
            appointment.save()
            messages.success(request, f'Пациент изменен на {patient.lname} {patient.fname}')
            return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)
        
        return redirect('scheduling:doctor_schedule', doctor_id=doctor.pk)