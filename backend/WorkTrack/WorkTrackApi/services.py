from datetime import date, timedelta, datetime, time
from calendar import monthrange
from WorkTrackApi.models import CalendarDay, Attendance, Employees, PlannedShifts
from django.db.models import Sum

NON_WORKING_SHIFT_IDS = [21, 23]
STANDARD_WORK_HOURS = 7.0  # <--- Vaša konštanta pre fond

# ==========================================
# 1. POMOCNÉ FUNKCIE
# ==========================================

def get_previous_month(year, month):
    if month == 1: return year - 1, 12
    return year, month - 1

def get_next_month(year, month):
    if month == 12: return year + 1, 1
    return year, month + 1

def _calculate_night_overlap(range_start, range_end):
    """
    ŠPECIÁLNA FUNKCIA PRE NOČNÚ (Fix pre ID 800 - 10h bug).
    Kontroluje prienik s blokmi 22:00 - 06:00(+1) pre každý dotknutý deň.
    """
    total_seconds = 0.0
    check_date = range_start.date() - timedelta(days=1)
    end_date = range_end.date()

    while check_date <= end_date:
        night_start = datetime.combine(check_date, time(22, 0))
        night_end = datetime.combine(check_date + timedelta(days=1), time(6, 0))

        overlap_start = max(range_start, night_start)
        overlap_end = min(range_end, night_end)

        if overlap_start < overlap_end:
            total_seconds += (overlap_end - overlap_start).total_seconds()

        check_date += timedelta(days=1)

    return total_seconds

def _get_duration(att):
    """Vypočíta trvanie (čas vs fixné) pre ATTENDANCE."""
    CALCULATE_BY_TIME_IDS = [20, 22] 
    
    if att.type_shift and att.type_shift.id in CALCULATE_BY_TIME_IDS:
        if att.custom_start and att.custom_end:
            s = datetime.combine(att.date, att.custom_start)
            e = datetime.combine(att.date, att.custom_end)
            if e < s: e += timedelta(days=1)
            if att.custom_end == time(0, 0) and s == e: e += timedelta(days=1)
            return (e - s).total_seconds() / 3600.0

    if att.type_shift and att.type_shift.duration_time:
        return float(att.type_shift.duration_time)

    if att.custom_start and att.custom_end:
        s = datetime.combine(att.date, att.custom_start)
        e = datetime.combine(att.date, att.custom_end)
        if e < s: e += timedelta(days=1)
        if att.custom_end == time(0, 0) and s == e: e += timedelta(days=1)
        return (e - s).total_seconds() / 3600.0
    return 0.0

# ==========================================
# 2. VÝPOČET FONDU
# ==========================================

def calculate_working_fund(year, month):
    days = monthrange(year, month)[1]
    hours = 0.0
    holidays = {h[0] for h in CalendarDay.get_slovak_holidays(year)}
    
    for day in range(1, days + 1):
        d = date(year, month, day)
        if d.weekday() < 5 and d not in holidays: 
            hours += STANDARD_WORK_HOURS
            
    return hours

def calculate_paid_holiday_credit(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    holidays = CalendarDay.get_slovak_holidays(year)
    credit = 0.0
    
    for h_date, _ in holidays:
        if start <= h_date <= end and h_date.weekday() < 5:
            if not Attendance.objects.filter(user_id=employee_id, date=h_date).exists():
                credit += STANDARD_WORK_HOURS
                
    return credit

# ==========================================
# 3. VÝPOČTY ODRACOVANÝCH HODÍN (Attendance)
# ==========================================

def calculate_worked_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    atts = Attendance.objects.filter(user_id=employee_id, date__range=(start, end)).distinct()
    return round(sum(_get_duration(a) for a in atts), 2)

def calculate_night_shift_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    atts = Attendance.objects.filter(user_id=employee_id, date__range=(start, end)).distinct()
    
    total_seconds = 0.0
    for att in atts:
        if not (att.custom_start and att.custom_end): continue
        s = datetime.combine(att.date, att.custom_start)
        e = datetime.combine(att.date, att.custom_end)
        if e < s: e += timedelta(days=1)
        if att.custom_end == time(0, 0) and s == e: e += timedelta(days=1)
        
        total_seconds += _calculate_night_overlap(s, e)
        
    return round(total_seconds / 3600.0, 2)

def calculate_saturday_sunday_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    atts = Attendance.objects.filter(user_id=employee_id, date__range=(start, end)).distinct()
    
    sat, sun = 0.0, 0.0
    
    for att in atts:
        if att.type_shift and att.type_shift.id in NON_WORKING_SHIFT_IDS:
            continue

        if not (att.custom_start and att.custom_end): continue
        
        s, e = datetime.combine(att.date, att.custom_start), datetime.combine(att.date, att.custom_end)
        if e < s: e += timedelta(days=1)
        
        curr = s
        while curr < e:
            next_mid = datetime.combine(curr.date() + timedelta(days=1), time.min)
            seg_end = min(e, next_mid)
            dur = (seg_end - curr).total_seconds()
            
            if curr.weekday() == 5: sat += dur
            elif curr.weekday() == 6: sun += dur
            
            curr = seg_end
            
    return {"saturday_hours": round(sat/3600, 2), "sunday_hours": round(sun/3600, 2)}

def calculate_weekend_hours(employee_id, year, month):
    d = calculate_saturday_sunday_hours(employee_id, year, month)
    return d["saturday_hours"] + d["sunday_hours"]

def calculate_holiday_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    holidays = {h[0] for h in CalendarDay.get_slovak_holidays(year)}
    atts = Attendance.objects.filter(user_id=employee_id, date__range=(start, end)).distinct()
    
    sec = 0.0
    for att in atts:
        if att.type_shift and att.type_shift.id in NON_WORKING_SHIFT_IDS:
            continue

        if not (att.custom_start and att.custom_end): continue
        
        s, e = datetime.combine(att.date, att.custom_start), datetime.combine(att.date, att.custom_end)
        if e < s: e += timedelta(days=1)
        
        curr = s
        while curr < e:
            next_mid = datetime.combine(curr.date() + timedelta(days=1), time.min)
            seg_end = min(e, next_mid)
            
            if curr.date() in holidays: 
                sec += (seg_end - curr).total_seconds()
                
            curr = seg_end
            
    return {"holiday_hours": round(sec/3600, 2)}


# ==========================================
# 3.1. VÝPOČTY Z PLÁNU (PlannedShifts)
# ==========================================

def calculate_planned_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    plans = PlannedShifts.objects.filter(
        user_id=employee_id, 
        date__range=(start, end),
        hidden=False
    ).select_related('type_shift') 
    
    return round(sum(_get_duration(p) for p in plans), 2)

def calculate_planned_night_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    plans = PlannedShifts.objects.filter(
        user_id=employee_id, 
        date__range=(start, end),
        hidden=False
    ).select_related('type_shift')
    
    total_seconds = 0.0
    for p in plans:
        if not (p.custom_start and p.custom_end): continue
        
        s = datetime.combine(p.date, p.custom_start)
        e = datetime.combine(p.date, p.custom_end)
        if e < s: e += timedelta(days=1)
        if p.custom_end == time(0, 0) and s == e: e += timedelta(days=1)
        
        total_seconds += _calculate_night_overlap(s, e)
        
    return round(total_seconds / 3600.0, 2)

def calculate_planned_weekend_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    plans = PlannedShifts.objects.filter(
        user_id=employee_id, 
        date__range=(start, end),
        hidden=False
    ).select_related('type_shift')
    
    sat, sun = 0.0, 0.0
    for p in plans:
        if p.type_shift and p.type_shift.id in NON_WORKING_SHIFT_IDS:
            continue
        if not (p.custom_start and p.custom_end): continue
        
        s, e = datetime.combine(p.date, p.custom_start), datetime.combine(p.date, p.custom_end)
        if e < s: e += timedelta(days=1)
        
        curr = s
        while curr < e:
            next_mid = datetime.combine(curr.date() + timedelta(days=1), time.min)
            seg_end = min(e, next_mid)
            dur = (seg_end - curr).total_seconds()
            
            if curr.weekday() == 5: sat += dur
            elif curr.weekday() == 6: sun += dur
            
            curr = seg_end
            
    return {
        "saturday_hours": round(sat/3600, 2), 
        "sunday_hours": round(sun/3600, 2),
        "total_weekend": round((sat + sun)/3600, 2)
    }

def calculate_planned_holiday_hours(employee_id, year, month):
    start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
    holidays = {h[0] for h in CalendarDay.get_slovak_holidays(year)}
    
    plans = PlannedShifts.objects.filter(
        user_id=employee_id, 
        date__range=(start, end),
        hidden=False
    ).select_related('type_shift')
    
    sec = 0.0
    for p in plans:
        if p.type_shift and p.type_shift.id in NON_WORKING_SHIFT_IDS:
            continue
        if not (p.custom_start and p.custom_end): continue
        
        s, e = datetime.combine(p.date, p.custom_start), datetime.combine(p.date, p.custom_end)
        if e < s: e += timedelta(days=1)
        
        curr = s
        while curr < e:
            next_mid = datetime.combine(curr.date() + timedelta(days=1), time.min)
            seg_end = min(e, next_mid)
            if curr.date() in holidays: 
                sec += (seg_end - curr).total_seconds()
            curr = seg_end
            
    return {"holiday_hours": round(sec/3600, 2)}

# ==========================================
# 4. SALDÁ A FINAL REPORT (OPRAVENÉ)
# ==========================================

def get_balances_up_to(target_year, target_month):
    """
    Vypočíta saldo pre každého zamestnanca k 1. dňu zadaného mesiaca/roka.
    OPRAVA: Používa 'user=emp' pre PlannedShifts a bezpečne ráta trvanie.
    """
    employees = Employees.objects.filter(is_active=True)
    balances = {}
    
    # Dátum zlomu (všetko PRED týmto dátumom sa ráta do histórie)
    cutoff_date = date(target_year, target_month, 1)

    for emp in employees:
        try:
            # 1. Počiatočný vklad
            current_balance = float(emp.initial_hours_balance or 0)

            # 2. Sčítame VŠETKY smeny PRED týmto dátumom
            # Používame user=emp (nie employee=emp) a hidden=False
            shifts = PlannedShifts.objects.filter(
                user=emp,
                date__lt=cutoff_date,
                hidden=False
            )

            total_worked_hours = 0.0
            visited_months = set()

            for s in shifts:
                # Manuálny výpočet trvania, keďže PlannedShifts nemusí mať 'duration' pole
                # alebo spoliehanie sa na _get_duration ak funguje pre Plan
                
                # Tu použijeme priamy výpočet z časov pre istotu:
                hours = 0.0
                if s.custom_start and s.custom_end:
                    start = datetime.combine(s.date, s.custom_start)
                    end = datetime.combine(s.date, s.custom_end)
                    
                    # Prechod cez polnoc
                    if end < start: end += timedelta(days=1)
                    if s.custom_end == time(0,0) and start != end: end += timedelta(days=1)
                    
                    diff = (end - start).total_seconds() / 3600.0
                    hours = diff
                
                # Prípadne, ak máte definované trvanie v type smeny:
                elif s.type_shift and s.type_shift.duration_time:
                     hours = float(s.type_shift.duration_time)
                
                total_worked_hours += hours
                
                # Zapamätáme si mesiac pre odčítanie fondu
                visited_months.add((s.date.year, s.date.month))

            # 3. Odčítame fondy za mesiace, kde mal zamestnanec aktivitu
            total_fund_hours = 0.0
            for (y, m) in visited_months:
                fund = calculate_working_fund(y, m)
                total_fund_hours += fund

            # Výsledok
            final_balance = current_balance + total_worked_hours - total_fund_hours
            balances[emp.id] = round(final_balance, 2)
            
        except Exception as e:
            print(f"Chyba pri výpočte salda pre {emp}: {e}")
            balances[emp.id] = 0

    return balances

# Staršie funkcie pre reporty (môžete ponechať)
def compare_worked_time_working_fund(employee_id, year, month):
    fund = calculate_working_fund(year, month)
    worked = calculate_worked_hours(employee_id, year, month)
    return {"working_fund": fund, "worked_hours": worked, "difference": round(worked - fund, 2)}

def calculate_transferred_hours(employee_id, year, month):
    # Táto funkcia ráta prenos z Attendance (dochádzky), 
    # zatiaľ čo get_balances_up_to ráta z PlannedShifts (plánu).
    # Záleží, čo chcete zobrazovať v plánovači. 
    # Pre plánovač zvyčajne chceme vidieť saldo z PLÁNU.
    try:
        emp = Employees.objects.get(id=employee_id)
        bal = float(emp.initial_hours_balance or 0)
    except: return 0.0
    
    first = Attendance.objects.filter(user_id=employee_id).order_by("date").first()
    if not first: return bal
    y, m = first.date.year, first.date.month
    if (y > year) or (y == year and m >= month): return bal
    
    curr_y, curr_m = y, m
    while (curr_y < year) or (curr_y == year and curr_m < month):
        f = calculate_working_fund(curr_y, curr_m)
        w = calculate_worked_hours(employee_id, curr_y, curr_m)
        c = calculate_paid_holiday_credit(employee_id, curr_y, curr_m)
        bal += (w + c) - f
        curr_y, curr_m = get_next_month(curr_y, curr_m)
    return round(bal, 2)

def calculate_total_hours_with_transfer(employee_id, year, month):
    fund = calculate_working_fund(year, month)
    worked = calculate_worked_hours(employee_id, year, month)
    credit = calculate_paid_holiday_credit(employee_id, year, month)
    
    wd = calculate_saturday_sunday_hours(employee_id, year, month)
    hd = calculate_holiday_hours(employee_id, year, month)
    nh = calculate_night_shift_hours(employee_id, year, month)

    curr_total = worked + credit
    diff = curr_total - fund
    transf = calculate_transferred_hours(employee_id, year, month)

    return {
        "year": year, "month": month, "working_fund": fund,
        "current_month_worked": worked, "holiday_credit": credit,
        "details": {
            "saturday_hours": wd["saturday_hours"],
            "sunday_hours": wd["sunday_hours"],
            "worked_on_holiday_hours": hd["holiday_hours"],
            "night_shift_hours": nh,
        },
        "current_month_total": curr_total,
        "current_month_diff": round(diff, 2),
        "transferred_hours": transf,
        "total_balance": round(transf + diff, 2)
    }

# ==========================================
# 5. KOPÍROVANIE PLÁNU
# ==========================================
def copy_monthly_plan(user, source_year, source_month, target_year, target_month):
    source_start = date(source_year, source_month, 1)
    source_end = date(source_year, source_month, monthrange(source_year, source_month)[1])
    
    source_shifts = PlannedShifts.objects.filter(
        user=user, 
        date__range=(source_start, source_end), 
        hidden=False
    )
    
    created_count = 0
    
    for shift in source_shifts:
        try:
            new_date = date(target_year, target_month, shift.date.day)
            
            if not PlannedShifts.objects.filter(user=user, date=new_date).exists():
                PlannedShifts.objects.create(
                    user=user,
                    date=new_date,
                    type_shift=shift.type_shift,
                    custom_start=shift.custom_start,
                    custom_end=shift.custom_end,
                    note=shift.note,
                    calendar_day=shift.calendar_day
                )
                created_count += 1
                
        except ValueError:
            pass
            
    return created_count

def get_planned_monthly_summary(user_id, year, month):
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    
    plans = PlannedShifts.objects.filter(
        user_id=user_id, 
        date__range=(start_date, end_date),
        hidden=False  
    )
    
    total_hours = 0.0
    
    for p in plans:
        if p.custom_start and p.custom_end:
            s = datetime.combine(p.date, p.custom_start)
            e = datetime.combine(p.date, p.custom_end)
            
            if e < s: e += timedelta(days=1)
            if p.custom_end == time(0, 0) and s != e: e += timedelta(days=1)
            
            total_hours += (e - s).total_seconds() / 3600.0
            
    return {"planned_hours": round(total_hours, 2)}