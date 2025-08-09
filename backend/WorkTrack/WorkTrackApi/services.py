from datetime import datetime, date, timedelta,time
from calendar import monthrange
from WorkTrackApi.models import CalendarDay, Attendance
from django.db.models import Q

def get_previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    else:
        return year, month - 1

def calculate_working_fund(year: int, month: int, hours_per_day: float = 8.0) -> float:
    # Získaj všetky dni v mesiaci
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    days = CalendarDay.objects.filter(date__range=(start_date, end_date))
    
    # Počítaj len tie dni, ktoré nie sú víkend ani sviatok
    working_days = days.filter(is_weekend=False, is_holiday=False).count()
    
    # Fond = pracovné dni × pracovné hodiny denne
    return working_days * hours_per_day

fond = calculate_working_fund(2025, 7)
print(f"Fond za júl 2025: {fond} hodín")



def calculate_worked_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__range=(start_date, end_date)
    )
    
    total_seconds = 0
    for att in attendances:
        # Použij custom_start/custom_end ak sú, inak z plánovanej smeny
        start_time = att.custom_start
        end_time = att.custom_end
        
        if start_time is None or end_time is None:
            # ak chýbajú custom časy, použijeme type_shift časy
            if att.type_shift:
                start_time = att.type_shift.start_time
                end_time = att.type_shift.end_time
        
        if start_time and end_time:
            start_dt = datetime.combine(att.date, start_time)
            end_dt = datetime.combine(att.date, end_time)
            if end_dt < start_dt:
                # nočná služba alebo prechod cez polnoc
                end_dt += timedelta(days=1)
            
            duration = (end_dt - start_dt).total_seconds()
            total_seconds += duration

    return total_seconds / 3600

test=calculate_worked_hours(1, 2025, 7)
print(f"Odpracovane hodiny za júl {test} hodín")

def compare_worked_time_working_fund(employee_id: int, year: int, month: int):
    # Fond pracovného času (napr. z CalendarDay)
    v1 = calculate_working_fund(year, month)

    # Odpracované hodiny (napr. z Attendance)
    v2 = calculate_worked_hours(employee_id, year, month)

    rozdiel = v2 - v1
    return {
        "fond": v1,
        "odpracovane": v2,
        "rozdiel": rozdiel
       }

result = compare_worked_time_working_fund(1, 2025, 7)
print(f"Fond: {result['fond']} h")
print(f"Odpracované: {result['odpracovane']} h")
print(f"Rozdiel: {result['rozdiel']:+.2f} h")

#Odpracovane hodiny za sobotu aj za nedelu
def calculate_saturday_sunday_hours(employee_id: int, year: int, month: int) -> dict:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    # Získaj všetky víkendové dni z kalendára
    weekend_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_weekend=True
    )

    # Rozdeľ dátumy na soboty a nedele
    saturdays = [day.date for day in weekend_days if day.date.weekday() == 5]
    sundays = [day.date for day in weekend_days if day.date.weekday() == 6]

    # Načítaj dochádzku v týchto dátumoch
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

            # Priradíme podľa dňa
            if att.date in saturdays:
                saturday_seconds += duration
            elif att.date in sundays:
                sunday_seconds += duration

    return {
        "saturday_hours": saturday_seconds / 3600,
        "sunday_hours": sunday_seconds / 3600
    }
result = calculate_saturday_sunday_hours(1, 2025, 7)
print(f"Odpracované hodiny za júl 2025:")
print(f"  - Sobota: {result['saturday_hours']:.2f} hodín")
print(f"  - Nedeľa: {result['sunday_hours']:.2f} hodín")



# odpracovane hodiny za výkend
def calculate_weekend_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    # Vyber víkendové dni z kalendára pre daný mesiac
    weekend_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_weekend=True
    ).values_list('date', flat=True)

    # Záznamy dochádzky iba na víkendové dni
    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__in=weekend_days
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

    return {"weekend hours": total_seconds / 3600}  # hodiny

vikend_hodiny = calculate_weekend_hours(1, 2025, 7)
print(f"Odpracované víkendové hodiny za júl 2025: {vikend_hodiny['weekend hours']:.2f} hodín")


# odpracovane hodiny za sviatok
def calculate_holiday_hours(employee_id: int, year: int, month: int) -> float:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    # Vyber sviatkove dni z kalendára pre daný mesiac
    holiday_days = CalendarDay.objects.filter(
        date__range=(start_date, end_date),
        is_holiday=True
    ).values_list('date', flat=True)

    # Záznamy dochádzky iba na víkendové dni
    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__in=holiday_days
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

    return {"holiday hours": total_seconds / 3600}  # hodiny

sviatky_hodiny = calculate_holiday_hours(1, 2025, 7)
print(f"Odpracované sviatkové hodiny za júl 2025: {sviatky_hodiny['holiday hours']:.2f} hodín")


def calculate_transferred_hours(employee_id: int, year: int, month: int) -> float:
    # Získame všetky mesiace od nástupu zamestnanca po mesiac pred aktuálnym
    from .models import Attendance  # prispôsob si podľa umiestnenia modelov

    # Získaj prvý dochádzkový záznam daného zamestnanca
    first_attendance = Attendance.objects.filter(
      user_id=employee_id
    ).order_by("date").first()

    if not first_attendance:
        # Zamestnanec nemá žiadne záznamy => nič sa neprenáša
        return 0.0

    start_year = first_attendance.date.year
    start_month = first_attendance.date.month

    # Limituj koniec na predchádzajúci mesiac
    prev_year, prev_month = get_previous_month(year, month)

    prenesene = 0.0

    y, m = start_year, start_month

    while (y, m) <= (prev_year, prev_month):
        fond = calculate_working_fund(y, m)
        odpracovane = calculate_worked_hours(employee_id, y, m) or 0.0
        rozdiel = odpracovane - fond
        prenesene += rozdiel
        y, m = get_next_month(y, m)  # pomocná funkcia, viď nižšie

    return prenesene

def get_next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1



def calculate_total_hours_with_transfer(employee_id: int, year: int, month: int) -> dict:
    prenesene = calculate_transferred_hours(employee_id, year, month) or 0.0
    aktualne = calculate_worked_hours(employee_id, year, month) or 0.0

    spolu = prenesene + aktualne

    return {
        "prenesené_hodiny": prenesene,
        "odpracované_aktuálny_mesiac": aktualne,
        "spolu": spolu
    }
print("spustam: calculate_total_hours_with_transfer")
vysledok = calculate_total_hours_with_transfer(1, 2025, 7)
print(f"Prenesené: {vysledok['prenesené_hodiny']:.2f} h")
print(f"Odpracované tento mesiac: {vysledok['odpracované_aktuálny_mesiac']:.2f} h")
print(f"Spolu: {vysledok['spolu']:.2f} h")



def calculate_night_shift_hours(employee_id: int, year: int, month: int) -> float:
    from collections import defaultdict

    total_night_hours = 0.0

    # Načítame všetky dochádzky v rozšírenom rozsahu (aj deň pred mesiacom a deň po ňom)
    start_date = date(year, month, 1) - timedelta(days=1)
    end_date = date(year, month, monthrange(year, month)[1]) + timedelta(days=1)

    attendances = Attendance.objects.filter(
        user_id=employee_id,
        date__range=(start_date, end_date)
    ).order_by('date', 'custom_start')

    # Zoskupenie podľa dátumu začiatku nočnej smeny (21:00 predchádzajúceho dňa)
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
            start = att.custom_start
            end = att.custom_end

            if not start or not end:
                if att.type_shift:
                    start = start or att.type_shift.start_time
                    end = end or att.type_shift.end_time

            if start and end:
                start_dt = datetime.combine(att.date, start)
                end_dt = datetime.combine(att.date, end)

                if end_dt < start_dt:
                    end_dt += timedelta(days=1)

                duration = (end_dt - start_dt).total_seconds()
                total_seconds += duration

                # Rozdeľ podľa dňa (a teda aj podľa mesiaca)
                current = start_dt
                while current < end_dt:
                    next_hour = min(end_dt, current + timedelta(hours=1))
                    hour_duration = (next_hour - current).total_seconds()
                    per_day_seconds[current.date()] += hour_duration
                    current = next_hour

        # Ak je to úplná nočná smena
        if total_seconds >= 12 * 3600:
            for day, secs in per_day_seconds.items():
                if day.month == month and day.year == year:
                    # Pridáme iba tie hodiny, ktoré patria do daného mesiaca
                    # Pomerný podiel z 8 hodín
                    portion = secs / total_seconds
                    total_night_hours += 8.0 * portion

    return round(total_night_hours, 2)

nočne_hodiny = calculate_night_shift_hours(employee_id=1, year=2025, month=8)
print(f"Odpracované nočné hodiny za júl 2025: {nočne_hodiny:.2f} h")
