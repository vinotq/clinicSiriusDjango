-- =====================================
-- 1. Удаление всех таблиц
-- =====================================
drop table if exists scheduling_recipe cascade;
drop table if exists scheduling_diagnosis cascade;
drop table if exists scheduling_appointment cascade;
drop table if exists scheduling_appointmentschedule cascade;
drop table if exists scheduling_room cascade;
drop table if exists staff_doctor cascade;
drop table if exists staff_specialization cascade;
drop table if exists patients_patientgroup cascade;
drop table if exists patients_patient cascade;

-- =====================================
-- 2. Вставка данных
-- =====================================

-- Специализации
insert into staff_specialization (name, description) values
('Терапевт', 'Общая терапия'),
('Хирург', 'Хирургические операции'),
('Офтальмолог', 'Лечение заболеваний глаз'),
('Кардиолог', 'Лечение заболеваний сердца'),
('Невролог', 'Лечение заболеваний нервной системы'),
('Педиатр', 'Лечение детей'),
('Дерматолог', 'Лечение заболеваний кожи'),
('Психиатр', 'Лечение психических расстройств'),
('Ортопед', 'Лечение опорно-двигательного аппарата'),
('Эндокринолог', 'Лечение эндокринных заболеваний')
on conflict (name) do nothing;

-- Комнаты
insert into scheduling_room (room_number)
select lpad(i::text, 3, '0')
from generate_series(1, 10) as s(i)
on conflict (room_number) do nothing;

-- Вставка пациентов
insert into patients_patient (fname, lname, tname, bdate, phone_number, email, snils, oms)
values
('Анна', 'Иванова', 'Сергеевна', '1970-06-12', '79101112233', 'anna.ivanova@mail.ru', '22534889136', '2937656342538330'),
('Иван', 'Иванов', 'Алексеевич', '1973-03-24', '79212223344', 'ivan.petrov@mail.ru', '47281677872', '6992323181472724'),
('Елена', 'Смирнова', 'Игоревна', '1978-10-01', '79031234567', 'elena.smirnova@mail.ru', '40633174362', '7304303106090224'),
('Олег', 'Кузнецов', 'Владимирович', '1982-11-15', '79503334455', 'oleg.kuznetsov@mail.ru', '94495478352', '7116418693558009'),
('Мария', 'Иванова', 'Ивановна', '1995-07-07', '79124445566', 'maria.sokolova@mail.ru', '11536670589', '2461530457094005'),
('Сергей', 'Попов', 'Петрович', '1988-09-19', '79253334466', 'sergey.popov@mail.ru', '44234287408', '5716770141276107'),
('Ирина', 'Лебедева', 'Олеговна', '1975-12-01', '79087776655', 'irina.lebedeva@mail.ru', '07850285836', '7065112381456136'),
('Дмитрий', 'Новиков', 'Сергеевич', '1981-02-14', '79151112255', 'dmitriy.novikov@mail.ru', '91613490579', '6490886469977132'),
('Алексей', 'Смирнов', 'Владимирович', '2000-04-18', '79261114455', 'alexey.morozov@mail.ru', '28089895153', '3628167985235921'),
('Светлана', 'Волкова', 'Павловна', '1989-01-23', '79153336644', 'svetlana.volkova@mail.ru', '74622981730', '9770275779207932'),
('Татьяна', 'Федорова', 'Александровна', '1973-08-09', '79097773322', 'tatyana.fedorova@mail.ru', '14140228126', '6127946579243022'),
('Андрей', 'Михайлов', 'Евгеньевич', '1991-05-27', '79251117788', 'andrey.mikhailov@mail.ru', '98320351329', '3174163955367198'),
('Кирилл', 'Борисов', 'Павлович', '1987-09-02', '79186667755', 'kirill.borisov@mail.ru', '44341833797', '4048422244690048'),
('Екатерина', 'Андреева', 'Сергеевна', '1996-03-03', '79214446655', 'ekaterina.andreeva@mail.ru', '23966893349', '8153837726246914'),
('Владимир', 'Смирнов', 'Олегович', '1984-04-30', '79052223344', 'vladimir.pavlov@mail.ru', '90032128559', '5589858412903584'),
('Юлия', 'Макарова', 'Алексеевна', '1988-12-12', '79217778899', 'yulia.makarova@mail.ru', '46400698643', '9723938296824806'),
('Михаил', 'Николаев', 'Иванович', '1993-06-01', '79152223311', 'mikhail.nikolaev@mail.ru', '49530139156', '7986181027388660'),
('Виктория', 'Иванова', 'Дмитриевна', '1997-10-21', '79263337711', 'victoria.orlova@mail.ru', '28101785281', '8421360258609306'),
('Павел', 'Орлов', 'Иванович', '1986-07-18', '79096663322', 'pavel.kiselev@mail.ru', '89726183623', '6475193569810514'),
('Алина', 'Тихонова', 'Михайловна', '1994-02-14', '79101119900', 'alina.tikhonova@mail.ru', '42994168655', '9872731276306947')
on conflict (snils) do nothing;

-- Вставка связей пациентов
insert into patients_patientgroup (parent_id, child_id)
select p1.id, p2.id
from patients_patient p1, patients_patient p2
where (p1.snils = '22534889136' and p2.snils = '47281677872')
   or (p1.snils = '22534889136' and p2.snils = '11536670589')
   or (p1.snils = '22534889136' and p2.snils = '28101785281')
   or (p1.snils = '40633174362' and p2.snils = '91613490579')
   or (p1.snils = '40633174362' and p2.snils = '23966893349')
on conflict (parent_id, child_id) do nothing;

-- Вставка врачей
insert into staff_doctor (fname, lname, tname, bdate, phone_number, email, specialization_id)
select 
    d.fname, d.lname, d.tname, d.bdate::date, d.phone_number, d.email, s.id
from (values
    ('Игорь', 'Семенов', 'Павлович', '1978-04-12', '79051112233', 'igor.semenov@clinic.ru', 'Терапевт'),
    ('Евгения', 'Сидорова', 'Александровна', '1983-06-23', '79163334455', 'evgenia.sidorova@clinic.ru', 'Хирург'),
    ('Валерий', 'Козлов', 'Сергеевич', '1975-02-09', '79217775522', 'valery.kozlov@clinic.ru', 'Офтальмолог'),
    ('Марина', 'Савина', 'Олеговна', '1988-09-19', '79091119922', 'marina.savina@clinic.ru', 'Кардиолог'),
    ('Олег', 'Рыбаков', 'Иванович', '1980-12-02', '79123337755', 'oleg.rybakov@clinic.ru', 'Невролог'),
    ('Татьяна', 'Галкина', 'Викторовна', '1984-07-10', '79267778899', 'tatyana.galkina@clinic.ru', 'Педиатр'),
    ('Александр', 'Крылов', 'Андреевич', '1976-11-17', '79052223311', 'alexandr.krylov@clinic.ru', 'Дерматолог'),
    ('Ирина', 'Шестакова', 'Петровна', '1989-03-14', '79212221100', 'irina.shestakova@clinic.ru', 'Психиатр'),
    ('Петр', 'Виноградов', 'Сергеевич', '1982-05-08', '79089997755', 'petr.vinogradov@clinic.ru', 'Ортопед'),
    ('Юлия', 'Морозова', 'Федоровна', '1990-10-20', '79177775533', 'yulia.morozova@clinic.ru', 'Эндокринолог')
) as d(fname, lname, tname, bdate, phone_number, email, spec_name)
join staff_specialization s on s.name = d.spec_name
on conflict do nothing;

-- Диагнозы
insert into scheduling_diagnosis (name) values
('ОРВИ'),
('Грипп'),
('Гастрит'),
('Мигрень'),
('Артрит'),
('Сахарный диабет'),
('Гипертония'),
('Пневмония'),
('Невроз'),
('Дерматит'),
('Здоров')
on conflict (name) do nothing;

-- Генерация расписания врачей
with time_params as (
    select
        d.id as doctor_id,
        (trunc(random()*10)+1)::int as room_num,
        gs_day.d as day_offset,
        gs_hour.h as hour_offset,
        gs_slot.s as slot_offset
    from staff_doctor d
    cross join generate_series(0,6) as gs_day(d)  
    cross join generate_series(0,12) as gs_hour(h)  -- 0-12 = 13 часов, итого 7+12=19 часов (последний слот 19:40-20:00)
    cross join generate_series(0,2) as gs_slot(s)  
),
base_date as (
    -- Получаем начало дня в локальном часовом поясе (Europe/Moscow)
    select date_trunc('day', (current_timestamp AT TIME ZONE 'Europe/Moscow')) as start_date_local
),
slots as (
    select
        tp.doctor_id,
        tp.room_num,
        -- Создаем время в локальном часовом поясе (Europe/Moscow), начиная с 7:00
        -- Затем конвертируем в UTC для хранения (Django с USE_TZ=True ожидает UTC в базе)
        ((bd.start_date_local + tp.day_offset * interval '1 day' +
        (7 + tp.hour_offset) * interval '1 hour' +
        tp.slot_offset * interval '20 minutes') AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC' as time_from
    from time_params tp
    cross join base_date bd
    where extract(dow from bd.start_date_local + tp.day_offset * interval '1 day') not in (0,6)  -- Только рабочие дни
)
insert into scheduling_appointmentschedule (doctor_id, room_id, time_from, time_to)
select 
    s.doctor_id, 
    r.id as room_id,
    s.time_from, 
    s.time_from + interval '20 minutes' as time_to
from slots s
join scheduling_room r on lpad(s.room_num::text, 3, '0') = r.room_number
where s.time_from >= ((date_trunc('day', (current_timestamp AT TIME ZONE 'Europe/Moscow')) AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC')
  and s.time_from < (((date_trunc('day', (current_timestamp AT TIME ZONE 'Europe/Moscow')) + interval '7 days') AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC')
  and not exists (
    select 1 from scheduling_appointmentschedule aps
    where aps.doctor_id = s.doctor_id
      and aps.room_id = r.id
      and aps.time_from = s.time_from
      and aps.time_to = s.time_from + interval '20 minutes'
  )
order by s.doctor_id, s.time_from;

-- Генерация приёмов для разных пациентов
-- Для прошлых дат (до сегодня) - статус 'completed', для будущих - 'booked'
insert into scheduling_appointment (patient_id, doctor_id, date, status, slot_id)
with appointments_to_create as (
select
        aps.id as slot_id,
    aps.doctor_id,
        aps.time_from,
        case 
            when aps.time_from < ((current_timestamp AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC') then 'completed'
            else 'booked'
        end as appointment_status
    from scheduling_appointmentschedule aps
    where aps.time_from >= ((date_trunc('day', (current_timestamp AT TIME ZONE 'Europe/Moscow')) AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC')
      and aps.time_from < (((date_trunc('day', (current_timestamp AT TIME ZONE 'Europe/Moscow')) + interval '7 days') AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC')
      and not exists (select 1 from scheduling_appointment a where a.slot_id = aps.id)
    order by random()
    limit 150  
),
patient_assignments as (
    select 
        atc.*,
        (row_number() over ()) % (select count(*) from patients_patient) + 1 as patient_idx
    from appointments_to_create atc
),
patients_with_idx as (
    select 
        id as patient_id,
        row_number() over (order by id) as idx
    from patients_patient
)
select
    p.patient_id,
    pa.doctor_id,
    pa.time_from as date,
    pa.appointment_status as status,
    pa.slot_id
from patient_assignments pa
join patients_with_idx p on p.idx = pa.patient_idx
on conflict (patient_id, doctor_id, date) do nothing;

-- Генерация рецептов только для завершенных приемов (статус 'completed')
with completed_appointments as (
    select a.id as appointment_id, a.date as appointment_date, row_number() over (order by a.id) as row_num
    from scheduling_appointment a
    where a.status = 'completed'
),
diagnosis_with_recipies as (
    select id, name, row_number() over () as row_num
    from scheduling_diagnosis
    order by random()
)
insert into scheduling_recipe (appointment_id, diagnosis_id, complaints, recommendations, created_at, updated_at)
select 
    a.appointment_id, 
    d.id as diagnosis_id,
    case d.name
        when 'ОРВИ' then 'Насморк, кашель, повышенная температура.'
        when 'Грипп' then 'Сильная слабость, ломота в теле, высокая температура.'
        when 'Гастрит' then 'Боли в желудке, изжога, тошнота после еды.'
        when 'Мигрень' then 'Сильная головная боль, чувствительность к свету и звукам.'
        when 'Артрит' then 'Боль и скованность в суставах, особенно по утрам.'
        when 'Сахарный диабет' then 'Жажда, частое мочеиспускание, утомляемость.'
        when 'Гипертония' then 'Головная боль, шум в ушах, повышенное давление.'
        when 'Пневмония' then 'Кашель с мокротой, одышка, высокая температура.'
        when 'Невроз' then 'Тревожность, раздражительность, проблемы со сном.'
        when 'Дерматит' then 'Зуд, покраснение и шелушение кожи.'
        when 'Здоров' then 'Жалоб нет, профилактический осмотр.'
        else 'Жалобы не указаны.'
    end as complaints,
    case d.name
        when 'ОРВИ' then 'Принимать противовирусные препараты, соблюдать режим, много пить.'
        when 'Грипп' then 'Постельный режим, противовирусные средства, обильное питьё.'
        when 'Гастрит' then 'Соблюдать диету, избегать острых блюд, принимать назначенные препараты.'
        when 'Мигрень' then 'Избегать стрессов, приём болеутоляющих по необходимости.'
        when 'Артрит' then 'Упражнения на суставы, соблюдать рекомендации врача, принимать препараты.'
        when 'Сахарный диабет' then 'Контролировать сахар, соблюдать диету, регулярные анализы.'
        when 'Гипертония' then 'Контроль давления, принимать препараты, избегать стрессов.'
        when 'Пневмония' then 'Принимать антибиотики, постельный режим, контроль температуры.'
        when 'Невроз' then 'Психологические консультации, избегать стрессов, приём назначенных препаратов.'
        when 'Дерматит' then 'Использовать назначенные мази, соблюдать гигиену, избегать аллергенов.'
        when 'Здоров' then 'Профилактический осмотр, вести здоровый образ жизни.'
        else 'Следовать рекомендациям врача.'
    end as recommendations,
    a.appointment_date as created_at,
    a.appointment_date as updated_at
from completed_appointments a
join diagnosis_with_recipies d on (a.row_num - 1) % (select count(*) from scheduling_diagnosis) + 1 = d.row_num
on conflict (appointment_id) do nothing;

-- =====================================
-- 3. Отчетные представления
-- =====================================

-- 1. Цельный отчет со всеми сущностями
create or replace view view_full_appointment_report as
select
    a.id as appointment_id,
    a.date as appointment_date,
    a.status as appointment_status,
    
    p.id as patient_id,
    p.lname || ' ' || p.fname || coalesce(' ' || p.tname, '') as patient_fullname,
    p.phone_number as patient_phone,
    p.email as patient_email,
    
    d.id as doctor_id,
    d.lname || ' ' || d.fname || coalesce(' ' || d.tname, '') as doctor_fullname, 
    s.name as specialization,
    d.phone_number as doctor_phone,
    d.email as doctor_email,
    
    r.room_number,
    rec.complaints,
    
    diag.name as diagnosis,
    rec.recommendations
from scheduling_appointment a
join patients_patient p on a.patient_id = p.id
join staff_doctor d on a.doctor_id = d.id
join staff_specialization s on d.specialization_id = s.id
left join scheduling_appointmentschedule aps on aps.id = a.slot_id
left join scheduling_room r on aps.room_id = r.id
left join scheduling_recipe rec on rec.appointment_id = a.id
left join scheduling_diagnosis diag on rec.diagnosis_id = diag.id;

-- 2. Пациенты, родительские аккаунты и их "дети"
create or replace view view_patient_family as
select 
    p1.lname || ' ' || p1.fname || coalesce(' ' || p1.tname, '') as parent_fullname,
    p2.lname || ' ' || p2.fname || coalesce(' ' || p2.tname, '') as child_fullname
from patients_patientgroup pg
    join patients_patient p1 on pg.parent_id = p1.id
    join patients_patient p2 on pg.child_id = p2.id;

-- 3. Статистика Специальность - Кол-во Пациентов
create or replace view view_specialization_patient_count as
select
    d.lname || ' ' || d.fname || coalesce(' ' || d.tname, '') as doctor_fullname,
    s.name as specialization,
    coalesce(count(distinct a.patient_id), 0) as patient_count
from staff_doctor d
    join staff_specialization s on d.specialization_id = s.id
    left join scheduling_appointment a on a.doctor_id = d.id
group by d.id, d.lname, d.fname, d.tname, s.id, s.name
order by patient_count desc;

-- 4. Топ самых частых пациентов по посещениям
create or replace view view_ten_top_frequent_patients as
select 
    p.id as patient_id,
    p.lname || ' ' || p.fname || coalesce(' ' || p.tname, '') as patient_fullname,
    count(a.id) as visit_count
from scheduling_appointment a
    join patients_patient p on a.patient_id = p.id
group by p.id, p.lname, p.fname, p.tname
order by visit_count desc
limit 10;

-- =====================================
-- 4. Функции
-- =====================================

-- 1. Ближайшее свободное окно врача
create or replace function get_nearest_free_appointment_for_doctor(doctor_id int)
returns timestamp with time zone
language plpgsql
as $$
declare
    nearest_time timestamp with time zone;
begin
    select time_from
    into nearest_time
    from scheduling_appointmentschedule aps
    where aps.doctor_id = doctor_id
      and not exists (
          select 1 from scheduling_appointment a
          where a.slot_id = aps.id
      ) 
      and time_from > (now() AT TIME ZONE 'UTC')
    order by time_from
    limit 1;

    return nearest_time;
end;
$$;

-- 2. Универсальная функция получения ФИО 
create or replace function get_fullname(entity_table text, entity_id int)
returns text
language plpgsql
as $$
declare
    result text;
    query text;
    id_column text;
begin
    if entity_table = 'patient' then
        id_column := 'id';
        query := format(
            'select lname || '' '' || fname || '' '' || coalesce(tname, '''')
             from patients_patient
             where id = $1'
        );
    elsif entity_table = 'doctor' then
        id_column := 'id';
        query := format(
            'select lname || '' '' || fname || '' '' || coalesce(tname, '''')
             from staff_doctor
             where id = $1'
        );
    else
        raise exception 'Таблица % не поддерживается. Разрешено: patient, doctor', entity_table;
    end if;

    execute query into result using entity_id;

    if result is null then
        raise exception 'Запись с id % в таблице % не найдена', entity_id, entity_table;
    end if;

    return trim(result);
end;
$$;

-- =====================================
-- 5. История данных (Дельта-подход)
-- =====================================
-- История пациентов
create table if not exists patients_patient_history(
    id serial primary key,
    patient_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function patients_patient_history_func_trg()
    returns trigger 
    language plpgsql
as 
$$
declare
    col text;
    old_v text;
    new_v text;
begin
    if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into patients_patient_history(patient_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into patients_patient_history(patient_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;
        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into patients_patient_history(patient_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;

end; 
$$;

drop trigger if exists patients_patient_history_trg on patients_patient;
create trigger patients_patient_history_trg
after insert or update or delete on patients_patient
for each row
execute function patients_patient_history_func_trg(
    'fname', 'lname', 'tname', 'bdate', 'phone_number', 'email', 'snils', 'oms'
);

-- История групп пациентов
create table if not exists patients_patientgroup_history(
    id serial primary key,
    patient_group_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function patients_patientgroup_history_func_trg()
    returns trigger
    language plpgsql
as
$$
declare
    col text;
    old_v text;
    new_v text;
begin
   if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into patients_patientgroup_history(patient_group_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into patients_patientgroup_history(patient_group_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;

        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into patients_patientgroup_history(patient_group_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;
end;
$$;

drop trigger if exists patients_patientgroup_history_trg on patients_patientgroup;
create trigger patients_patientgroup_history_trg
after insert or update or delete on patients_patientgroup
for each row
execute function patients_patientgroup_history_func_trg(
    'parent_id', 'child_id'
);

-- История врачей
create table if not exists staff_doctor_history (
    id serial primary key,
    doctor_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function staff_doctor_history_func_trg()
    returns trigger
    language plpgsql
as
$$
declare
    col text;
    old_v text;
    new_v text;
begin
    if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into staff_doctor_history(doctor_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into staff_doctor_history(doctor_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;
        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into staff_doctor_history(doctor_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;

end;
$$;

drop trigger if exists staff_doctor_history_trg on staff_doctor;
create trigger staff_doctor_history_trg
after insert or update or delete on staff_doctor
for each row
execute function staff_doctor_history_func_trg(
    'fname', 'lname', 'tname', 'bdate', 'phone_number', 'email', 'specialization_id'
);

-- История расписания
create table if not exists scheduling_appointmentschedule_history (
    id serial primary key,
    ap_sch_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function scheduling_appointmentschedule_history_func_trg()
    returns trigger
    language plpgsql
as
$$
declare
    col text;
    old_v text;
    new_v text;
begin
    if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into scheduling_appointmentschedule_history(ap_sch_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into scheduling_appointmentschedule_history(ap_sch_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;
        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into scheduling_appointmentschedule_history(ap_sch_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;

end;
$$;

drop trigger if exists scheduling_appointmentschedule_history_trg on scheduling_appointmentschedule;
create trigger scheduling_appointmentschedule_history_trg
after insert or update or delete on scheduling_appointmentschedule
for each row
execute function scheduling_appointmentschedule_history_func_trg(
    'doctor_id', 'room_id', 'time_from', 'time_to'
);

-- История приемов
create table if not exists scheduling_appointment_history (
    id serial primary key,
    ap_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function scheduling_appointment_history_func_trg()
    returns trigger
    language plpgsql
as
$$
declare
    col text;
    old_v text;
    new_v text;
begin
    if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into scheduling_appointment_history(ap_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into scheduling_appointment_history(ap_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;
        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into scheduling_appointment_history(ap_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;

end;
$$;

drop trigger if exists scheduling_appointment_history_trg on scheduling_appointment;
create trigger scheduling_appointment_history_trg
after insert or update or delete on scheduling_appointment
for each row
execute function scheduling_appointment_history_func_trg(
    'patient_id', 'doctor_id', 'date', 'status', 'slot_id'
);

-- История рецептов
create table if not exists scheduling_recipe_history (
    id serial primary key,
    recipe_id int,
    field_name varchar(50),
    old_val text,
    new_val text,
    changed_at timestamp with time zone default current_timestamp,
    changed_by varchar(50) default current_user, 
    changer_role varchar(25) default current_role
);

create or replace function scheduling_recipe_history_func_trg()
    returns trigger
    language plpgsql
as
$$
declare
    col text;
    old_v text;
    new_v text;
begin
    if tg_op = 'INSERT' then
        foreach col in array tg_argv loop
            new_v := to_jsonb(NEW.*)->>col;
            insert into scheduling_recipe_history(recipe_id, field_name, old_val, new_val)
            values (NEW.id, col, null, new_v);
        end loop;
        return NEW;
    end if;

    if tg_op = 'UPDATE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            new_v := to_jsonb(NEW.*)->>col;

            if old_v is distinct from new_v then
                insert into scheduling_recipe_history(recipe_id, field_name, old_val, new_val)
                values (NEW.id, col, old_v, new_v);
            end if;
        end loop;
        return NEW;
    end if;

    if tg_op = 'DELETE' then
        foreach col in array tg_argv loop
            old_v := to_jsonb(OLD.*)->>col;
            insert into scheduling_recipe_history(recipe_id, field_name, old_val, new_val)
            values (OLD.id, col, old_v, null);
        end loop;
        return OLD;
    end if;

end;
$$;

drop trigger if exists scheduling_recipe_history_trg on scheduling_recipe;
create trigger scheduling_recipe_history_trg
after insert or update or delete on scheduling_recipe
for each row
execute function scheduling_recipe_history_func_trg(
    'appointment_id', 'diagnosis_id', 'complaints', 'recommendations', 'next_appointment_slot_id', 'referral_doctor_id', 'referral_slot_id'
);

-- =====================================
-- 6. Роли и права доступа
-- =====================================

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'patient') then
        create role patient;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'doctor') then
        create role doctor;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'manager') then
        create role manager;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'admin') then
        create role admin;
    end if;
end
$$;

-- 1. Права для роли Пациент
grant select on patients_patient to patient;
grant select on scheduling_appointment to patient;
grant select on scheduling_recipe to patient;
grant select on scheduling_diagnosis to patient;

-- 2. Права для роли Доктор
grant select, update on staff_doctor to doctor;
grant select, insert, update on scheduling_appointment to doctor;
grant select, insert, update on scheduling_recipe to doctor;
grant select on patients_patient to doctor;
grant select on scheduling_diagnosis to doctor;
grant select, insert, update, delete on scheduling_appointmentschedule to doctor;

-- 3. Права для роли Менеджер
grant select, insert, update, delete on patients_patient to manager;
grant select, insert, update, delete on scheduling_appointmentschedule to manager;
grant select, insert, update, delete on scheduling_room to manager;
grant select, insert, update, delete on staff_doctor to manager;
grant select on scheduling_appointment to manager;
grant select on scheduling_recipe to manager;
grant select on scheduling_diagnosis to manager;

-- 4. Права для роли Администратор 
grant all privileges on all tables in schema public to admin;
grant all privileges on all sequences in schema public to admin;
grant all privileges on all functions in schema public to admin;
grant all privileges on all procedures in schema public to admin;

