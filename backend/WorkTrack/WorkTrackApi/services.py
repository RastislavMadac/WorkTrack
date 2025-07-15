from datetime import datetime, date, timedelta
from calendar import monthrange
from WorkTrackApi.models import CalendarDay, Attendance
from django.db.models import Q

def calculate_working_fund(year: int, month: int, hours_per_day: float = 8.0) -> float:
    # Získaj všetky dni v mesiaci
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    days = CalendarDay.objects.filter(date__range=(start_date, end_date))
    
    # Počítaj len tie dni, ktoré nie sú víkend ani sviatok
    working_days = days.filter(is_weekend=False, is_holiday=False).count()
    
    # Fond = pracovné dni × pracovné hodiny denne
    return {"worked_fund":working_days * hours_per_day}

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

    return {"worked_hours":total_seconds / 3600}  # vráti odpracované hodiny
test=calculate_worked_hours(1, 2025, 7)
print(f"Odpracovane hodiny za júl {test} hodín")

def compare_worked_time_working_fund(employee_id: int, year: int, month: int):
    # Fond pracovného času (napr. z CalendarDay)
    v1 = calculate_working_fund(year, month)["worked_fund"]

    # Odpracované hodiny (napr. z Attendance)
    v2 = calculate_worked_hours(employee_id, year, month)["worked_hours"]

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
