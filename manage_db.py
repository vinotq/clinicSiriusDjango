#!/usr/bin/env python3
"""
Универсальный скрипт для управления базой данных ClinicSirius

Использование:
    python manage_db.py --clear                    # Полностью удалить и пересоздать базу данных
    python manage_db.py --init                     # Инициализировать базу из SQL
    python manage_db.py --admins                   # Создать администраторов
    python manage_db.py --link-profiles            # Привязать профили
    python manage_db.py --create-profiles          # Создать профили для пользователей
    python manage_db.py --full                     # Полная инициализация (clear + init + admins + link-profiles)
    
    # Комбинации:
    python manage_db.py --clear --init             # Удалить базу и инициализировать
    python manage_db.py --init --admins            # Инициализировать и создать админов
    python manage_db.py --link-profiles --create-users  # Привязать профили с созданием пользователей
    python manage_db.py --create-profiles --verbose     # Создать профили с подробным выводом
    
    # Дополнительные опции:
    python manage_db.py --link-profiles --verbose --create-users
    python manage_db.py --clear --confirm          # Подтвердить полное удаление базы данных
    
ВАЖНО: --clear полностью удаляет базу данных и создает новую пустую базу.
       Все данные будут безвозвратно удалены!
"""

import os
import sys
from pathlib import Path

# Настройка Django
try:
    import django
except ImportError:
    print("Ошибка: Django не установлен. Убедитесь, что вы находитесь в виртуальном окружении.")
    print("Активируйте виртуальное окружение и установите зависимости:")
    print("  source venv/bin/activate  # или ваш способ активации")
    print("  pip install -r backend/requirements.txt")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent / 'backend'
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

try:
    django.setup()
except Exception as e:
    print(f"Ошибка при настройке Django: {e}")
    print("Убедитесь, что:")
    print("  1. Вы находитесь в корне проекта")
    print("  2. Виртуальное окружение активировано")
    print("  3. Все зависимости установлены")
    sys.exit(1)

from django.db import connection
from django.db.models import Q
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import call_command
from accounts.models import User
from patients.models import Patient
from staff.models import Doctor, Specialization
import random

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    psycopg2 = None
    ISOLATION_LEVEL_AUTOCOMMIT = None


def print_header(text):
    """Печать заголовка"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_success(text):
    """Печать успешного сообщения"""
    print(f"✓ {text}")


def print_error(text):
    """Печать сообщения об ошибке"""
    print(f"✗ {text}")


def print_warning(text):
    """Печать предупреждения"""
    print(f"⚠ {text}")


def clear_database(confirm=False):
    """Полное удаление и пересоздание базы данных"""
    print_header("Очистка базы данных")
    
    if not confirm:
        print_warning("Для удаления базы данных требуется подтверждение!")
        print("Используйте флаг --confirm для подтверждения")
        return False
    
    if psycopg2 is None:
        print_error("psycopg2 не установлен. Установите его для работы с PostgreSQL:")
        print("  pip install psycopg2-binary")
        return False
    
    print("Начинаю полное удаление базы данных...\n")
    
    # Получаем параметры подключения из settings
    db_config = settings.DATABASES['default']
    db_name = db_config['NAME']
    db_user = db_config['USER']
    db_password = db_config['PASSWORD']
    db_host = db_config['HOST']
    db_port = db_config['PORT']
    
    print(f"База данных: {db_name}")
    print(f"Хост: {db_host}:{db_port}")
    print(f"Пользователь: {db_user}\n")
    
    # Закрываем текущее подключение Django
    print("Закрытие текущего подключения Django...")
    connection.close()
    
    try:
        # Подключаемся к postgres для удаления базы данных
        # (нельзя удалить базу, к которой подключены)
        print("Подключение к серверу PostgreSQL...")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database='postgres'  # Подключаемся к системной БД
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Завершаем все активные подключения к целевой БД
        print(f"Завершение активных подключений к базе {db_name}...")
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{db_name}'
            AND pid <> pg_backend_pid();
        """)
        
        # Удаляем базу данных
        print(f"Удаление базы данных {db_name}...")
        cursor.execute(f'DROP DATABASE IF EXISTS "{db_name}";')
        print_success(f"База данных {db_name} удалена")
        
        # Создаем новую пустую базу данных
        print(f"Создание новой базы данных {db_name}...")
        cursor.execute(f'CREATE DATABASE "{db_name}";')
        print_success(f"База данных {db_name} создана")
        
        cursor.close()
        conn.close()
        
        # Закрываем старое подключение Django и переподключаемся к новой БД
        connection.close()
        
        # Выполняем миграции для создания структуры таблиц
        print("\nВыполнение миграций Django для создания структуры таблиц...")
        try:
            call_command('migrate', verbosity=0, interactive=False)
            print_success("Миграции выполнены успешно")
        except Exception as e:
            print_error(f"Ошибка при выполнении миграций: {str(e)}")
            print_warning("Возможно, нужно выполнить миграции вручную:")
            print("  python backend/manage.py migrate")
            return False
        
        print("\n" + "=" * 60)
        print_success(f"\nОчистка завершена!\nБаза данных {db_name} полностью удалена и пересоздана.")
        print("Структура таблиц создана через миграции Django.")
        print("=" * 60 + "\n")
        
        print_warning("База данных пуста. Для загрузки тестовых данных (расписание, врачи, пациенты) выполните:")
        print("  python manage_db.py --init")
        print("Или используйте полную инициализацию:")
        print("  python manage_db.py --full --confirm")
        
        return True
        
    except psycopg2.Error as e:
        print_error(f"Ошибка при работе с базой данных: {str(e)}")
        print_warning("Убедитесь, что:")
        print("  1. PostgreSQL сервер запущен")
        print("  2. Пользователь имеет права на создание/удаление баз данных")
        print("  3. Нет активных подключений к базе данных")
        return False
    except Exception as e:
        print_error(f"Неожиданная ошибка: {str(e)}")
        return False


def init_database():
    """Инициализация базы данных из SQL"""
    print_header("Инициализация базы данных")
    
    base_dir = Path(__file__).resolve().parent
    sql_file = base_dir / 'database_init.sql'
    
    if not sql_file.exists():
        print_error(f"Файл {sql_file} не найден!")
        return False
    
    print("Чтение файла database_init.sql...")
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Удаляем однострочные комментарии (-- комментарий), но сохраняем структуру
    # Простой подход: удаляем комментарии из строк, учитывая что -- может быть в строках
    import re
    
    def remove_comments(text):
        """Удаляет SQL комментарии, но сохраняет строки"""
        lines = text.split('\n')
        result = []
        in_string = False
        string_char = None
        
        for line in lines:
            cleaned = []
            i = 0
            while i < len(line):
                char = line[i]
                
                # Проверяем начало/конец строки (одинарные или двойные кавычки)
                if char in ("'", '"'):
                    if i == 0 or line[i-1] != '\\':
                        if not in_string:
                            in_string = True
                            string_char = char
                        elif char == string_char:
                            in_string = False
                            string_char = None
                    cleaned.append(char)
                # Проверяем комментарий (только если не в строке)
                elif not in_string and char == '-' and i + 1 < len(line) and line[i+1] == '-':
                    # Найден комментарий, остаток строки пропускаем
                    break
                else:
                    cleaned.append(char)
                i += 1
            
            result.append(''.join(cleaned))
        
        return '\n'.join(result)
    
    sql_content = remove_comments(sql_content)
    
    # Парсим команды (разделитель - точка с запятой)
    commands = []
    current_command = []
    in_dollar_quote = False
    dollar_tag = None
    
    lines = sql_content.split('\n')
    for line in lines:
        stripped = line.strip()
        
        # Пропускаем пустые строки
        if not stripped:
            if current_command:  # Сохраняем пустые строки внутри команды
                current_command.append('')
            continue
        
        # Простая обработка dollar quoting
        if '$$' in stripped:
            if not in_dollar_quote:
                in_dollar_quote = True
                # Находим позицию $$
                dollar_pos = stripped.find('$$')
                if dollar_pos > 0:
                    current_command.append(stripped[:dollar_pos])
                current_command.append('$$')
                # Проверяем, не закрывается ли в этой же строке
                remaining = stripped[dollar_pos + 2:]
                if '$$' in remaining:
                    # Закрывается в этой же строке
                    close_pos = remaining.find('$$')
                    current_command.append(remaining[:close_pos])
                    current_command.append('$$')
                    in_dollar_quote = False
                    remaining = remaining[close_pos + 2:]
                    if remaining.strip():
                        current_command.append(remaining)
                else:
                    current_command.append(remaining)
            else:
                # Ищем закрывающий $$
                dollar_pos = stripped.find('$$')
                if dollar_pos != -1:
                    current_command.append(stripped[:dollar_pos])
                    current_command.append('$$')
                    in_dollar_quote = False
                    remaining = stripped[dollar_pos + 2:]
                    if remaining.strip():
                        current_command.append(remaining)
                else:
                    current_command.append(line)
            continue
        
        if in_dollar_quote:
            # Внутри dollar quote - добавляем строку как есть
            current_command.append(line)
        else:
            # Обычная строка SQL
            current_command.append(stripped)
            
            # Проверяем конец команды (точка с запятой)
            if stripped.endswith(';'):
                command = '\n'.join(current_command)
                if command.strip():
                    commands.append(command)
                current_command = []
    
    # Добавляем последнюю команду, если она есть
    if current_command:
        command = '\n'.join(current_command)
        if command.strip():
            commands.append(command)
    
    print(f"Найдено {len(commands)} SQL команд для выполнения...")
    
    executed = 0
    errors = 0
    
    with connection.cursor() as cursor:
        for i, command in enumerate(commands, 1):
            try:
                if command.strip().upper().startswith('DROP TABLE'):
                    continue
                cursor.execute(command)
                executed += 1
                
                if i % 10 == 0:
                    print(f"Выполнено {i}/{len(commands)} команд...")
            except Exception as e:
                error_msg = str(e)
                ignore_patterns = [
                    'already exists',
                    'duplicate',
                    'violates unique constraint',
                    'unique constraint',
                    'duplicate key'
                ]
                
                should_ignore = any(pattern in error_msg.lower() for pattern in ignore_patterns)
                
                if should_ignore:
                    executed += 1
                    continue
                else:
                    errors += 1
                    print_warning(f"\nОшибка при выполнении команды {i}:")
                    print_error(f"   {error_msg[:200]}")
                    cmd_preview = command[:300].replace('\n', ' ')
                    print_warning(f"   Команда: {cmd_preview}...")
    
    print_success(f"\nИнициализация SQL завершена!\nВыполнено команд: {executed}\nОшибок: {errors}")
    
    return True


def create_admins():
    """Создание администраторов"""
    print_header("Создание администраторов")
    
    admins_data = [
        {
            'email': 'dmitry.volkov@clinic.ru',
            'username': 'dmitry.volkov',
            'password': 'Pass123$',
            'phone': '12345678',
            'full_name': 'Волков Дмитрий'
        },
        {
            'email': 'elena.kozlova@clinic.ru',
            'username': 'elena.kozlova',
            'password': 'Pass123$',
            'phone': '87654321',
            'full_name': 'Козлова Елена'
        }
    ]
    
    created_count = 0
    updated_count = 0
    
    for admin_data in admins_data:
        email = admin_data['email']
        username = admin_data['username']
        full_name = admin_data['full_name']
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'role': User.ROLE_ADMIN,
                'phone': admin_data['phone'],
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        
        if created:
            user.set_password(admin_data['password'])
            user.save()
            created_count += 1
            print_success(f"Создан администратор: {full_name} ({email})")
        else:
            user.username = username
            user.role = User.ROLE_ADMIN
            user.phone = admin_data['phone']
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(admin_data['password'])
            user.save()
            updated_count += 1
            print_warning(f"Обновлен администратор: {full_name} ({email})")
    
    print_success(f"\nВсего создано: {created_count}, обновлено: {updated_count}")
    return True


def normalize_email(email):
    """Нормализация email"""
    if not email:
        return None
    return email.strip().lower()


def link_profiles(verbose=False, create_users=False, dry_run=False):
    """Привязка профилей к пользователям"""
    print_header("Привязка профилей к пользователям")
    
    User = get_user_model()
    
    if dry_run:
        print_warning("Режим dry-run: изменения не будут применены\n")
    
    if create_users:
        print_warning("Режим создания пользователей: будут созданы пользователи, если их нет\n")
    
    # Привязка врачей
    print("Привязка врачей к пользователям...\n")
    doctors_linked = 0
    doctors_skipped = 0
    doctors_errors = 0
    doctors_no_email = 0
    doctors_no_user = 0
    
    doctors = Doctor.objects.filter(user__isnull=True)
    total_doctors = doctors.count()
    print(f"Найдено врачей без привязки: {total_doctors}\n")
    
    for doctor in doctors:
        doctor_email = normalize_email(doctor.email)
        if not doctor_email:
            doctors_no_email += 1
            if verbose:
                print_warning(f"  Врач {doctor.id} ({doctor.lname} {doctor.fname}) не имеет email")
            continue
        
        try:
            user = User.objects.filter(
                Q(email__iexact=doctor_email) | Q(email=doctor_email)
            ).first()
            
            if user:
                if user.role != 'doctor':
                    if verbose:
                        print_warning(f"  Пользователь {user.email} имеет роль {user.role}, а не doctor. Пропущен.")
                    doctors_skipped += 1
                    continue
                
                existing_doctor = Doctor.objects.filter(user=user).exclude(id=doctor.id).first()
                if existing_doctor:
                    if verbose:
                        print_warning(f"  Пользователь {user.email} уже привязан к врачу {existing_doctor.id}. Пропущен.")
                    doctors_skipped += 1
                    continue
                
                if not dry_run:
                    doctor.user = user
                    doctor.save(update_fields=['user'])
                doctors_linked += 1
                print_success(f"  Врач {doctor.id} ({doctor.lname} {doctor.fname}) привязан к пользователю {user.email}")
            else:
                if create_users:
                    try:
                        username = doctor_email.split('@')[0]
                        base_username = username
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f"{base_username}{counter}"
                            counter += 1
                        
                        password = "Pass123$"
                        
                        if not dry_run:
                            with transaction.atomic():
                                user = User.objects.create_user(
                                    username=username,
                                    email=doctor_email,
                                    password=password,
                                    role='doctor'
                                )
                                doctor.user = user
                                doctor.save(update_fields=['user'])
                        
                        doctors_linked += 1
                        print_success(f"  Создан пользователь для врача {doctor.id} ({doctor.lname} {doctor.fname})\n     Email: {doctor_email}, Username: {username}, Пароль: {password}")
                    except Exception as e:
                        doctors_errors += 1
                        print_error(f"  Ошибка при создании пользователя для врача {doctor.id}: {str(e)}")
                else:
                    doctors_no_user += 1
                    if verbose:
                        print_warning(f"  Пользователь с email {doctor_email} не найден для врача {doctor.id} ({doctor.lname} {doctor.fname})")
        except Exception as e:
            doctors_errors += 1
            print_error(f"  Ошибка при привязке врача {doctor.id}: {str(e)}")
    
    # Привязка пациентов
    print("\nПривязка пациентов к пользователям...\n")
    patients_linked = 0
    patients_skipped = 0
    patients_errors = 0
    patients_no_email = 0
    patients_no_user = 0
    
    patients = Patient.objects.filter(user__isnull=True)
    total_patients = patients.count()
    print(f"Найдено пациентов без привязки: {total_patients}\n")
    
    for patient in patients:
        patient_email = normalize_email(patient.email)
        if not patient_email:
            patients_no_email += 1
            if verbose:
                print_warning(f"  Пациент {patient.id} ({patient.lname} {patient.fname}) не имеет email")
            continue
        
        try:
            user = User.objects.filter(
                Q(email__iexact=patient_email) | Q(email=patient_email)
            ).first()
            
            if user:
                if user.role != 'patient':
                    if verbose:
                        print_warning(f"  Пользователь {user.email} имеет роль {user.role}, а не patient. Пропущен.")
                    patients_skipped += 1
                    continue
                
                existing_patient = Patient.objects.filter(user=user).exclude(id=patient.id).first()
                if existing_patient:
                    if verbose:
                        print_warning(f"  Пользователь {user.email} уже привязан к пациенту {existing_patient.id}. Пропущен.")
                    patients_skipped += 1
                    continue
                
                if not dry_run:
                    patient.user = user
                    patient.save(update_fields=['user'])
                patients_linked += 1
                print_success(f"  Пациент {patient.id} ({patient.lname} {patient.fname}) привязан к пользователю {user.email}")
            else:
                if create_users:
                    try:
                        username = patient_email.split('@')[0]
                        base_username = username
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f"{base_username}{counter}"
                            counter += 1
                        
                        password = "Pass123$"
                        
                        if not dry_run:
                            with transaction.atomic():
                                user = User.objects.create_user(
                                    username=username,
                                    email=patient_email,
                                    password=password,
                                    role='patient'
                                )
                                patient.user = user
                                patient.save(update_fields=['user'])
                        
                        patients_linked += 1
                        print_success(f"  Создан пользователь для пациента {patient.id} ({patient.lname} {patient.fname})\n     Email: {patient_email}, Username: {username}, Пароль: {password}")
                    except Exception as e:
                        patients_errors += 1
                        print_error(f"  Ошибка при создании пользователя для пациента {patient.id}: {str(e)}")
                else:
                    patients_no_user += 1
                    if verbose:
                        print_warning(f"  Пользователь с email {patient_email} не найден для пациента {patient.id} ({patient.lname} {patient.fname})")
        except Exception as e:
            patients_errors += 1
            print_error(f"  Ошибка при привязке пациента {patient.id}: {str(e)}")
    
    print("\n" + "=" * 60)
    print_success(
        f"\nПривязка завершена!\n\n"
        f"Врачи:\n"
        f"  Привязано: {doctors_linked}\n"
        f"  Без email: {doctors_no_email}\n"
        f"  Пользователь не найден: {doctors_no_user}\n"
        f"  Пропущено (другие причины): {doctors_skipped}\n"
        f"  Ошибок: {doctors_errors}\n\n"
        f"Пациенты:\n"
        f"  Привязано: {patients_linked}\n"
        f"  Без email: {patients_no_email}\n"
        f"  Пользователь не найден: {patients_no_user}\n"
        f"  Пропущено (другие причины): {patients_skipped}\n"
        f"  Ошибок: {patients_errors}"
    )
    print("=" * 60 + "\n")
    
    if doctors_no_user > 0 or patients_no_user > 0:
        print_warning(
            f"\n💡 Подсказка: {doctors_no_user + patients_no_user} записей не привязаны, так как пользователи с их email не найдены.\n"
            f"   Возможно, нужно создать пользователей или проверить соответствие email.\n"
            f"   Для подробного вывода используйте флаг --verbose"
        )
    
    if dry_run:
        print_warning("\nЭто был dry-run. Для применения изменений запустите команду без --dry-run")
    
    return doctors_errors == 0 and patients_errors == 0


def delete_managers(dry_run=False):
    """Удаление менеджеров"""
    print_header("Удаление менеджеров")
    
    User = get_user_model()
    managers = User.objects.filter(role='manager')
    count = managers.count()
    
    if count == 0:
        print_success("Пользователей с ролью manager не найдено в базе данных")
        return True
    
    if dry_run:
        print_warning(f"Будет удалено пользователей с ролью manager: {count}")
        for manager in managers:
            print(f"  - {manager.username} ({manager.email})")
        return True
    
    manager_list = list(managers.values_list('username', 'email'))
    deleted_count, _ = managers.delete()
    
    print_success(f"Удалено пользователей с ролью manager: {deleted_count}")
    for username, email in manager_list:
        print(f"  - {username} ({email})")
    
    return True


def rehash_passwords(dry_run=False, limit=0):
    """Перехэширование паролей"""
    print_header("Перехэширование паролей")
    
    User = get_user_model()
    known_prefixes = ('pbkdf2_', 'argon2', 'bcrypt', 'bcrypt_sha256', 'sha1$', 'md5$')
    
    qs = User.objects.all()
    changed = 0
    checked = 0
    
    for user in qs:
        pw = (user.password or '')
        checked += 1
        
        is_hashed = False
        if '$' in pw:
            prefix = pw.split('$', 1)[0]
            for alg in known_prefixes:
                if prefix.startswith(alg):
                    is_hashed = True
                    break
        
        if not is_hashed:
            print_warning(f'User {user.pk} ({user.email}) appears to have a non-hashed password: "{pw[:30]}..."')
            if dry_run:
                continue
            raw = pw
            try:
                user.set_password(raw)
                user.save()
                changed += 1
                print_success(f'  Re-hashed password for user {user.pk} ({user.email})')
            except Exception as e:
                print_error(f'  Failed to re-hash for user {user.pk}: {e}')
        
        if limit and changed >= limit:
            break
    
    print(f'Checked {checked} users; re-hashed {changed} users (dry-run={dry_run}).')
    return True


def create_profiles(verbose=False, dry_run=False):
    """Создание профилей (Doctor/Patient) для пользователей, у которых их нет"""
    print_header("Создание профилей для пользователей")
    
    User = get_user_model()
    
    if dry_run:
        print_warning("Режим dry-run: изменения не будут применены\n")
    
    doctors_created = 0
    doctors_skipped = 0
    doctors_errors = 0
    
    patients_created = 0
    patients_skipped = 0
    patients_errors = 0
    
    # Создание профилей врачей
    print("Создание профилей врачей...\n")
    doctor_users = User.objects.filter(role='doctor')
    total_doctors = doctor_users.count()
    print(f"Найдено пользователей с ролью doctor: {total_doctors}\n")
    
    for user in doctor_users:
        if hasattr(user, 'doctor_profile'):
            doctors_skipped += 1
            if verbose:
                print_warning(f"  Пользователь {user.email} уже имеет профиль врача")
            continue
        
        existing_doctor = Doctor.objects.filter(email__iexact=user.email).first()
        if existing_doctor:
            if not dry_run:
                existing_doctor.user = user
                existing_doctor.save(update_fields=['user'])
            doctors_created += 1
            print_success(f"  Привязан существующий врач {existing_doctor.lname} {existing_doctor.fname} к пользователю {user.email}")
        else:
            try:
                if not dry_run:
                    username_parts = user.username.split('.')
                    if len(username_parts) >= 2:
                        lname = username_parts[0].capitalize()
                        fname = username_parts[1].capitalize()
                    else:
                        lname = user.username.capitalize()
                        fname = "Имя"
                    
                    specialization = Specialization.objects.first()
                    if not specialization:
                        print_error(f"  Нет доступных специализаций. Создайте хотя бы одну специализацию.")
                        doctors_errors += 1
                        continue
                    
                    Doctor.objects.create(
                        fname=fname,
                        lname=lname,
                        bdate='1980-01-01',
                        email=user.email,
                        phone_number=user.phone[:11] if user.phone else None,
                        specialization=specialization,
                        user=user
                    )
                    doctors_created += 1
                    print_success(f"  Создан профиль врача для пользователя {user.email} ({lname} {fname})")
                else:
                    doctors_created += 1
                    print_success(f"  [DRY-RUN] Будет создан профиль врача для пользователя {user.email}")
            except Exception as e:
                doctors_errors += 1
                print_error(f"  Ошибка при создании профиля врача для {user.email}: {e}")
    
    # Создание профилей пациентов
    print("\nСоздание профилей пациентов...\n")
    patient_users = User.objects.filter(role='patient')
    total_patients = patient_users.count()
    print(f"Найдено пользователей с ролью patient: {total_patients}\n")
    
    for user in patient_users:
        if hasattr(user, 'patient_profile'):
            patients_skipped += 1
            if verbose:
                print_warning(f"  Пользователь {user.email} уже имеет профиль пациента")
            continue
        
        existing_patient = Patient.objects.filter(email__iexact=user.email).first()
        if existing_patient:
            if not dry_run:
                existing_patient.user = user
                existing_patient.save(update_fields=['user'])
            patients_created += 1
            print_success(f"  Привязан существующий пациент {existing_patient.lname} {existing_patient.fname} к пользователю {user.email}")
        else:
            try:
                if not dry_run:
                    username_parts = user.username.split('.')
                    if len(username_parts) >= 2:
                        lname = username_parts[0].capitalize()
                        fname = username_parts[1].capitalize()
                    else:
                        lname = user.username.capitalize()
                        fname = "Имя"
                    
                    snils = ''.join([str(random.randint(0, 9)) for _ in range(11)])
                    oms = ''.join([str(random.randint(0, 9)) for _ in range(16)])
                    
                    while Patient.objects.filter(snils=snils).exists():
                        snils = ''.join([str(random.randint(0, 9)) for _ in range(11)])
                    while Patient.objects.filter(oms=oms).exists():
                        oms = ''.join([str(random.randint(0, 9)) for _ in range(16)])
                    
                    Patient.objects.create(
                        fname=fname,
                        lname=lname,
                        bdate='1990-01-01',
                        email=user.email,
                        phone_number=user.phone[:11] if user.phone else None,
                        snils=snils,
                        oms=oms,
                        user=user
                    )
                    patients_created += 1
                    print_success(f"  Создан профиль пациента для пользователя {user.email} ({lname} {fname})")
                else:
                    patients_created += 1
                    print_success(f"  [DRY-RUN] Будет создан профиль пациента для пользователя {user.email}")
            except Exception as e:
                patients_errors += 1
                print_error(f"  Ошибка при создании профиля пациента для {user.email}: {e}")
    
    print("\n" + "=" * 60)
    print_success(
        f"\nСоздание профилей завершено!\n\n"
        f"Врачи:\n"
        f"  Создано/привязано: {doctors_created}\n"
        f"  Пропущено (уже есть): {doctors_skipped}\n"
        f"  Ошибок: {doctors_errors}\n\n"
        f"Пациенты:\n"
        f"  Создано/привязано: {patients_created}\n"
        f"  Пропущено (уже есть): {patients_skipped}\n"
        f"  Ошибок: {patients_errors}"
    )
    print("=" * 60 + "\n")
    
    if dry_run:
        print_warning("Это был dry-run. Для применения изменений запустите команду без --dry-run\n")
    
    return doctors_errors == 0 and patients_errors == 0


def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Универсальный скрипт для управления базой данных ClinicSirius',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Основные действия
    parser.add_argument('--clear', action='store_true',
                       help='Очистить базу данных')
    parser.add_argument('--init', action='store_true',
                       help='Инициализировать базу данных из database_init.sql')
    parser.add_argument('--admins', action='store_true',
                       help='Создать администраторов')
    parser.add_argument('--link-profiles', action='store_true',
                       help='Привязать профили врачей и пациентов к пользователям')
    parser.add_argument('--delete-managers', action='store_true',
                       help='Удалить всех менеджеров')
    parser.add_argument('--rehash-passwords', action='store_true',
                       help='Перехэшировать пароли пользователей')
    parser.add_argument('--create-profiles', action='store_true',
                       help='Создать профили (Doctor/Patient) для пользователей, у которых их нет')
    
    # Комбинированные действия
    parser.add_argument('--full', action='store_true',
                       help='Полная инициализация: clear + init + admins + link-profiles (с автоматическим созданием пользователей)')
    
    # Опции для clear
    parser.add_argument('--confirm', action='store_true',
                       help='Подтвердить очистку базы данных (требуется для --clear)')
    
    # Опции для link-profiles
    parser.add_argument('--verbose', action='store_true',
                       help='Подробный вывод (для link-profiles)')
    parser.add_argument('--create-users', action='store_true',
                       help='Создавать пользователей, если их нет (для link-profiles)')
    
    # Опции для dry-run
    parser.add_argument('--dry-run', action='store_true',
                       help='Режим тестирования без применения изменений')
    
    # Опции для rehash-passwords
    parser.add_argument('--limit', type=int, default=0,
                       help='Ограничить количество пользователей для обработки (для rehash-passwords, 0 = все)')
    
    args = parser.parse_args()
    
    # Если нет аргументов, показываем справку
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    success = True
    
    # Полная инициализация
    if args.full:
        print_header("Полная инициализация базы данных")
        steps = ["очистка", "инициализация", "создание админов", "привязка профилей"]
        if args.create_profiles:
            steps.append("создание профилей")
        print(f"Выполняется: {' → '.join(steps)}\n")
        
        if not args.confirm:
            print_warning("Для полной инициализации требуется подтверждение очистки!")
            print("Используйте флаг --confirm для подтверждения")
            return
        
        success = clear_database(confirm=True) and success
        if success:
            success = init_database() and success
        if success:
            success = create_admins() and success
        if success:
            # В полной инициализации всегда создаем пользователей, если их нет
            success = link_profiles(
                verbose=args.verbose,
                create_users=True,  # Автоматически создаем пользователей в --full
                dry_run=args.dry_run
            ) and success
        if success and args.create_profiles:
            success = create_profiles(verbose=args.verbose, dry_run=args.dry_run) and success
        
        if success:
            print_header("Полная инициализация завершена успешно!")
        else:
            print_error("Полная инициализация завершена с ошибками")
        return
    
    # Отдельные действия
    if args.clear:
        success = clear_database(confirm=args.confirm) and success
    
    if args.init:
        success = init_database() and success
    
    if args.admins:
        success = create_admins() and success
    
    if args.link_profiles:
        success = link_profiles(
            verbose=args.verbose,
            create_users=args.create_users,
            dry_run=args.dry_run
        ) and success
    
    if args.delete_managers:
        success = delete_managers(dry_run=args.dry_run) and success
    
    if args.rehash_passwords:
        success = rehash_passwords(dry_run=args.dry_run, limit=args.limit) and success
    
    if args.create_profiles:
        success = create_profiles(verbose=args.verbose, dry_run=args.dry_run) and success
    
    # Если ничего не было выполнено
    if not any([args.clear, args.init, args.admins, args.link_profiles, 
                args.delete_managers, args.rehash_passwords, args.create_profiles, args.full]):
        parser.print_help()
        return
    
    if success:
        print("\n" + "=" * 60)
        print_success("Все операции выполнены успешно!")
        print("=" * 60 + "\n")
    else:
        print("\n" + "=" * 60)
        print_error("Некоторые операции завершились с ошибками")
        print("=" * 60 + "\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
