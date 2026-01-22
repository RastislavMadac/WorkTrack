from datetime import datetime, date, timedelta, time
from calendar import monthrange
from collections import defaultdict
from django.db.models import Q, Sum
from .models import CalendarDay, Attendance, PlannedShifts

# ==========================================
# POMOCNÉ FUNKCIE (Dátumy)
# ==========================================

def get_previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    else:
        return year, month - 1

def get_next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1

# ==========================================
# PÔVODNÉ FUNKCIE (Pre Attendance/Dochádzku)
# ==========================================

def calculate_working_fund(year: int, month: int, hours_per_day: float = 8.0) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    days = CalendarDay.objects.filter(date__range=(start_date, end_date))
    working_days = days.filter(is_weekend=False, is_holiday=False).count()
    
    return working_days * hours_per_day

def calculate_worked_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__range=(start_date, end_date)
    )
    
    total_seconds = 0
    for att in attendances:
        start_time = att.custom_start
        end_time = att.custom_end
        
        if start_time is None or end_time is None:
            if att.type_shift:
                start_time = att.type_shift.start_time
                end_time = att.type_shift.end_time
        
        if start_time and end_time:
            start_dt = datetime.combine(att.date, start_time)
            end_dt = datetime.combine(att.date, end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            
            duration = (end_dt - start_dt).total_seconds()
            total_seconds += duration

    return total_seconds / 3600

def compare_worked_time_working_fund(employee_id: int, year: int, month: int):
    v1 = calculate_working_fund(year, month)
    v2 = calculate_worked_hours(employee_id, year, month)
    rozdiel = v2 - v1
    return {
        "fond": v1,
        "odpracovane": v2,
        "rozdiel": rozdiel
    }

def calculate_saturday_sunday_hours(employee_id: int, year: int, month: int) -> dict:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    weekend_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_weekend=True
    )

    saturdays = [day.date for day in weekend_days if day.date.weekday() == 5]
    sundays = [day.date for day in weekend_days if day.date.weekday() == 6]

    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__in=saturdays + sundays
    )

    saturday_seconds = 0
    sunday_seconds = 0

    for att in attendances:
        start_time = att.custom_start
        end_time = att.custom_end

        if start_time is None or end_time is None:
            if att.type_shift:
                start_time = att.type_shift.start_time
                end_time = att.type_shift.end_time

        if start_time and end_time:
            start_dt = datetime.combine(att.date, start_time)
            end_dt = datetime.combine(att.date, end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)

            duration = (end_dt - start_dt).total_seconds()

            if att.date in saturdays:
                saturday_seconds += duration
            elif att.date in sundays:
                sunday_seconds += duration

    return {
        "saturday_hours": saturday_seconds / 3600,
        "sunday_hours": sunday_seconds / 3600
    }

def calculate_weekend_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    weekend_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_weekend=True
    ).values_list('date', flat=True)

    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__in=weekend_days
    )

    total_seconds = 0
    for att in attendances:
        start_time = att.custom_start or (att.type_shift.start_time if att.type_shift else None)
        end_time = att.custom_end or (att.type_shift.end_time if att.type_shift else None)

        if start_time and end_time:
            start_dt = datetime.combine(att.date, start_time)
            end_dt = datetime.combine(att.date, end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            total_seconds += (end_dt - start_dt).total_seconds()

    return {"weekend hours": total_seconds / 3600}

def calculate_holiday_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    holiday_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_holiday=True
    ).values_list('date', flat=True)

    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__in=holiday_days
    )

    total_seconds = 0
    for att in attendances:
        start_time = att.custom_start or (att.type_shift.start_time if att.type_shift else None)
        end_time = att.custom_end or (att.type_shift.end_time if att.type_shift else None)

        if start_time and end_time:
            start_dt = datetime.combine(att.date, start_time)
            end_dt = datetime.combine(att.date, end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            total_seconds += (end_dt - start_dt).total_seconds()

    return {"holiday hours": total_seconds / 3600}

def calculate_transferred_hours(employee_id: int, year: int, month: int) -> float:
    first_attendance = Attendance.objects.filter(user_id=employee_id).order_by("date").first()
    if not first_attendance:
        return 0.0

    start_year = first_attendance.date.year
    start_month = first_attendance.date.month
    prev_year, prev_month = get_previous_month(year, month)

    prenesene = 0.0
    y, m = start_year, start_month

    while (y, m) <= (prev_year, prev_month):
        fond = calculate_working_fund(y, m)
        odpracovane = calculate_worked_hours(employee_id, y, m) or 0.0
        rozdiel = odpracovane - fond
        prenesene += rozdiel
        y, m = get_next_month(y, m)

    return prenesene

def calculate_total_hours_with_transfer(employee_id: int, year: int, month: int) -> dict:
    prenesene = calculate_transferred_hours(employee_id, year, month) or 0.0
    aktualne = calculate_worked_hours(employee_id, year, month) or 0.0
    spolu = prenesene + aktualne
    return {
        "prenesené_hodiny": prenesene,
        "odpracované_aktuálny_mesiac": aktualne,
        "spolu": spolu
    }

def calculate_night_shift_hours(employee_id: int, year: int, month: int) -> float:
    total_night_hours = 0.0
    start_date = date(year, month, 1) - timedelta(days=1)
    end_date = date(year, month, monthrange(year, month)[1]) + timedelta(days=1)

    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__range=(start_date, end_date)
    ).order_by('date', 'custom_start')

    grouped = defaultdict(list)
    for att in attendances:
        shift_date = att.date
        if att.custom_start and att.custom_start < time(12, 0):
            shift_date -= timedelta(days=1)
        grouped[shift_date].append(att)

    for shift_start_date, shift_attendances in grouped.items():
        total_seconds = 0
        per_day_seconds = defaultdict(float)

        for att in shift_attendances:
            start = att.custom_start or (att.type_shift.start_time if att.type_shift else None)
            end = att.custom_end or (att.type_shift.end_time if att.type_shift else None)

            if start and end:
                start_dt = datetime.combine(att.date, start)
                end_dt = datetime.combine(att.date, end)
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)

                duration = (end_dt - start_dt).total_seconds()
                total_seconds += duration
                
                # Rozdelenie podľa hodín pre presnosť
                current = start_dt
                while current < end_dt:
                    next_hour = min(end_dt, current + timedelta(hours=1))
                    hour_duration = (next_hour - current).total_seconds()
                    per_day_seconds[current.date()] += hour_duration
                    current = next_hour

        if total_seconds >= 12 * 3600:
            for day, secs in per_day_seconds.items():
                if day.month == month and day.year == year:
                    portion = secs / total_seconds
                    total_night_hours += 8.0 * portion

    return round(total_night_hours, 2)

# ==========================================
# NOVÉ FUNKCIE (Pre PlannedShifts/Plánovač)
# ==========================================
#NOTE - nEW
def get_planned_monthly_summary(user_id: int, year: int, month: int) -> dict:
    """
    Vypočíta sumár naplánovaných hodín pre daný mesiac (Fond, Odpracované, Víkendy, Nočné).
    Rieši prechody cez polnoc aj prechody cez mesiace.
    """
    start_date = date(year, month, 1)
    days_in_month = monthrange(year, month)[1]
    end_date = date(year, month, days_in_month)
    
    search_start = start_date - timedelta(days=1)
    search_end = end_date + timedelta(days=1)

    shifts = PlannedShifts.objects.filter(
        user_id=user_id,
        date__range=(search_start, search_end),
        hidden=False
    ).select_related('type_shift', 'calendar_day')

    stats = {
        "odpracovane_hodiny": 0.0,
        "nocne_hodiny": 0.0,      # NS
        "vikendove_hodiny": 0.0,  # SN
        "sviatkove_hodiny": 0.0,  # Sviatky
        "dovolenka_hodiny": 0.0,  # D
        "fond": 0.0,
        "rozdiel": 0.0
    }

    for shift in shifts:
        if not shift.type_shift:
            continue

        s_start = shift.custom_start or shift.type_shift.start_time
        s_end = shift.custom_end or shift.type_shift.end_time
        
        # Ak chýbajú časy (napr. ID 22 bez času), skúsime použiť duration_time
        if not s_start or not s_end:
            if shift.type_shift.duration_time:
                try:
                    dur = float(shift.type_shift.duration_time)
                    if shift.date.month == month and shift.date.year == year:
                        stats["odpracovane_hodiny"] += dur
                        if shift.type_shift.shortName == 'D' or shift.type_shift.id == 21:
                            stats["dovolenka_hodiny"] += dur
                except:
                    pass
            continue

        # Výpočet s presnými časmi
        start_dt = datetime.combine(shift.date, s_start)
        end_dt = datetime.combine(shift.date, s_end)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        total_duration_seconds = (end_dt - start_dt).total_seconds()
        
        current = start_dt
        while current < end_dt:
            end_of_day = datetime.combine(current.date(), time.max)
            next_step = min(end_dt, end_of_day + timedelta(seconds=1)) 
            interval_seconds = (next_step - current).total_seconds()
            
            if current.month == month and current.year == year:
                hours_value = interval_seconds / 3600.0
                stats["odpracovane_hodiny"] += hours_value

                if current.weekday() in [5, 6]: 
                    stats["vikendove_hodiny"] += hours_value

                try:
                    c_day = CalendarDay.objects.get(date=current.date())
                    if c_day.is_holiday:
                        stats["sviatkove_hodiny"] += hours_value
                except CalendarDay.DoesNotExist:
                    pass

                if shift.type_shift.id == 20 or shift.type_shift.shortName == 'Ns':
                    if total_duration_seconds >= 12 * 3600:
                        portion = interval_seconds / total_duration_seconds
                        stats["nocne_hodiny"] += 8.0 * portion
                    else:
                        stats["nocne_hodiny"] += hours_value
                
                if shift.type_shift.id == 21 or shift.type_shift.shortName == 'D':
                    stats["dovolenka_hodiny"] += hours_value

            current = next_step

    working_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_weekend=False, 
        is_holiday=False
    ).count()
    stats["fond"] = working_days * 8.0 
    stats["rozdiel"] = stats["odpracovane_hodiny"] - stats["fond"]

    for k, v in stats.items():
        stats[k] = round(v, 2)

    return stats
#NOTE - nEW
def copy_monthly_plan(source_year, source_month, target_year, target_month, user_id=None):
    """
    Skopíruje plán smien.
    - Ak je user_id zadané: kopíruje len jedného človeka.
    - Ak user_id=None: kopíruje VŠETKÝCH zamestnancov naraz.
    """
    
    # 1. Filtrovanie zdrojových smien
    filters = {
        'date__year': source_year,
        'date__month': source_month,
        'hidden': False
    }
    
    # Ak user_id nie je None (ani 0, ani prázdny string), pridáme ho do filtra
    if user_id:
        filters['user_id'] = user_id
        
    source_shifts = PlannedShifts.objects.filter(**filters).select_related('type_shift')
    
    # Ak nie je čo kopírovať, končíme
    if not source_shifts.exists():
        return {"created": 0, "skipped": 0, "message": "V zdrojovom mesiaci nie sú žiadne smeny."}

    new_shifts = []
    skipped_count = 0
    _, days_in_target = monthrange(target_year, target_month)

    # 2. OPTIMALIZÁCIA: Načítame CalendarDay pre cieľový mesiac naraz
    # Aby sme nerobili query v cykle (N+1 problém)
    start_target = date(target_year, target_month, 1)
    end_target = date(target_year, target_month, days_in_target)
    
    calendar_days = CalendarDay.objects.filter(date__range=(start_target, end_target))
    # Vytvoríme mapu: { datum: objekt_dna } pre rýchle vyhľadávanie
    calendar_map = {day.date: day for day in calendar_days}

    # 3. Iterácia a vytváranie kópií
    for shift in source_shifts:
        day_num = shift.date.day
        
        # Ošetrenie: 31. deň do 30-dňového mesiaca neskopírujeme
        if day_num > days_in_target:
            skipped_count += 1
            continue
            
        target_date = date(target_year, target_month, day_num)
        
        # Rýchle vytiahnutie z mapy (bez DB query)
        c_day = calendar_map.get(target_date)

        new_shift = PlannedShifts(
            user=shift.user,          # Použije Usera zo zdrojovej smeny
            date=target_date,
            type_shift=shift.type_shift,
            custom_start=shift.custom_start,
            custom_end=shift.custom_end,
            note=shift.note,
            calendar_day=c_day
        )
        new_shifts.append(new_shift)

    # 4. Hromadné uloženie do DB (jeden SQL príkaz)
    if new_shifts:
        PlannedShifts.objects.bulk_create(new_shifts)
        
    return {
        "created": len(new_shifts),
        "skipped": skipped_count
    }