from datetime import date, timedelta, datetime, time
from calendar import monthrange
from WorkTrackApi.models import CalendarDay, Attendance, Employees, PlannedShifts
from django.db.models import Sum
from dateutil.relativedelta import relativedelta

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

def _calculate_night_overlap(range_start, range_end, limit_start=None, limit_end=None):
    """
    ŠPECIÁLNA FUNKCIA PRE NOČNÚ.
    Kontroluje prienik s blokmi 22:00 - 06:00(+1) pre každý dotknutý deň.
    Upravené: Ak sú zadané limit_start a limit_end, oreže výpočet len na tento interval (pre správne rozdelenie mesiacov).
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
            # Aplikácia limitov (napr. orezať na hranice mesiaca)
            valid_start = overlap_start
            valid_end = overlap_end
            
            if limit_start:
                valid_start = max(valid_start, limit_start)
            if limit_end:
                valid_end = min(valid_end, limit_end)
            
            if valid_start < valid_end:
                total_seconds += (valid_end - valid_start).total_seconds()

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
    # Definujeme presné hranice mesiaca (od 1.dňa 00:00 do 1.dňa ďalšieho mesiaca 00:00)
    month_start_dt = datetime(year, month, 1)
    if month == 12:
        next_month_start_dt = datetime(year + 1, 1, 1)
    else:
        next_month_start_dt = datetime(year, month + 1, 1)
    
    # Hľadáme smeny, ktoré začínajú v mesiaci ALEBO deň pred (kvôli prechodu cez polnoc na 1. deň)
    query_start = (month_start_dt - timedelta(days=1)).date()
    query_end = (next_month_start_dt - timedelta(days=1)).date()

    atts = Attendance.objects.filter(user_id=employee_id, date__range=(query_start, query_end)).distinct()
    
    total_seconds = 0.0
    for att in atts:
        if not (att.custom_start and att.custom_end): continue
        s = datetime.combine(att.date, att.custom_start)
        e = datetime.combine(att.date, att.custom_end)
        if e < s: e += timedelta(days=1)
        if att.custom_end == time(0, 0) and s == e: e += timedelta(days=1)
        
        # Voláme s limitmi pre aktuálny mesiac - toto zabezpečí rozdelenie 2h / 6h
        total_seconds += _calculate_night_overlap(s, e, limit_start=month_start_dt, limit_end=next_month_start_dt)
        
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
# WorkTrackApi/services.py

def calculate_month_data(user, year, month):
    """
    Vypočíta presné dáta (worked, fund, diff...) pre jeden konkrétny mesiac.
    OPRAVENÉ: Robustný výpočet sviatkov (cez prienik časov).
    """
    # 1. Fond
    fund = calculate_working_fund(year, month)

    # Definujeme hranice mesiaca
    month_start = datetime(year, month, 1)
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    # 2. Načítame smeny (aj z predchádzajúceho dňa kvôli prechodom)
    q_start = (month_start - timedelta(days=1)).date()
    q_end = (next_month - timedelta(days=1)).date()

    shifts = PlannedShifts.objects.filter(
        user=user,
        date__range=(q_start, q_end),
        hidden=False
    ).select_related('type_shift')

    # 3. Načítame zoznam sviatkov v relevantnom rozsahu
    holidays_dates = list(CalendarDay.objects.filter(
        date__range=(q_start, q_end),
        is_holiday=True
    ).values_list('date', flat=True))

    worked_hours = 0.0
    night_hours = 0.0
    weekend_hours = 0.0
    holiday_hours = 0.0

    for s in shifts:
        duration = 0.0
        start_dt = None
        end_dt = None

        # A. Výpočet časov začiatku a konca
        if s.custom_start and s.custom_end:
            start_dt = datetime.combine(s.date, s.custom_start)
            end_dt = datetime.combine(s.date, s.custom_end)
            if end_dt < start_dt: end_dt += timedelta(days=1)
            elif s.custom_end == time(0,0) and start_dt != end_dt: end_dt += timedelta(days=1)
            duration = (end_dt - start_dt).total_seconds() / 3600.0
            
        elif s.type_shift and s.type_shift.duration_time:
            duration = float(s.type_shift.duration_time)
            # Ak nemáme presné časy (custom_start), nevieme presne určiť prienik so sviatkom/nocou.
            # Ak chcete rátat sviatok aj pre fixné smeny, museli by sme predpokladať, že sú celé v danom dni.
            if s.date in holidays_dates:
                 holiday_hours += duration

        # B. WORKED & WEEKEND (viazané na začiatok smeny v mesiaci)
        if s.date.month == month and s.date.year == year:
            worked_hours += duration
            if s.date.weekday() >= 5:
                weekend_hours += duration
        
        # C. NOČNÉ (limitované mesiacom)
        if start_dt and end_dt:
            if (s.type_shift and s.type_shift.shortName == 'Ns') or \
               (s.type_shift and 'Nočná' in s.type_shift.nameShift):
                seconds_in_night = _calculate_night_overlap(
                    start_dt, end_dt, limit_start=month_start, limit_end=next_month
                )
                night_hours += (seconds_in_night / 3600.0)

            # D. SVIATKY (Výpočet prieniku)
            # Prejdeme sviatky a zistíme, či smena zasahuje do niektorého z nich
            for h_date in holidays_dates:
                # Interval sviatku (od 00:00 do 24:00)
                h_start = datetime.combine(h_date, time.min)
                h_end = h_start + timedelta(days=1)

                # Prienik intervalov (Smena vs Sviatok)
                # Orežeme začiatok a koniec smeny hranicami sviatku
                overlap_start = max(start_dt, h_start)
                overlap_end = min(end_dt, h_end)

                # Ak je začiatok menší ako koniec, máme prienik
                if overlap_start < overlap_end:
                    # Ešte skontrolujeme, či prienik patrí do aktuálneho mesiaca (pre istotu, aby sme nerátali sviatok z minulého mesiaca do tohto reportu, ak to tak nechcete)
                    # Zvyčajne sa sviatky rátajú tam, kde sa stali.
                    # Ak chcete sviatok zarátať do mesiaca REPORTU, musíme spraviť prienik aj s mesiacom.
                    
                    val_start = max(overlap_start, month_start)
                    val_end = min(overlap_end, next_month)
                    
                    if val_start < val_end:
                        holiday_hours += (val_end - val_start).total_seconds() / 3600.0

    return {
        "fund": fund,
        "worked": round(worked_hours, 2),
        "diff": round(worked_hours - fund, 2),
        "night": round(night_hours, 2),
        "weekend": round(weekend_hours, 2),
        "holiday": round(holiday_hours, 2)
    }
def get_balances_up_to(target_year, target_month):
    """
    Vypočíta saldo k 1. dňu zadaného mesiaca pomocou calculate_month_data.
    """
    employees = Employees.objects.filter(is_active=True)
    balances = {}
    
    cutoff_date = date(target_year, target_month, 1)

    for emp in employees:
        try:
            current_balance = float(emp.initial_hours_balance or 0)

            # Nájdeme prvú smenu
            first_shift = PlannedShifts.objects.filter(
                user=emp, date__lt=cutoff_date, hidden=False
            ).order_by('date').first()

            if not first_shift:
                balances[emp.id] = round(current_balance, 2)
                continue

            # Iterujeme od mesiaca prvej smeny až po mesiac PRED cutoff_date
            cursor_date = date(first_shift.date.year, first_shift.date.month, 1)

            while cursor_date < cutoff_date:
                # 👇 TOTO JE KĽÚČOVÁ ZMENA: Voláme spoločnú funkciu
                month_stats = calculate_month_data(emp, cursor_date.year, cursor_date.month)
                
                # Pripočítame rozdiel (worked - fund) k saldu
                current_balance += month_stats['diff']

                # Posun na ďalší mesiac
                next_month = (cursor_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                cursor_date = next_month

            balances[emp.id] = round(current_balance, 2)
            
        except Exception as e:
            print(f"Error calculating balance for {emp}: {e}")
            balances[emp.id] = 0

    return balances


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

def get_full_monthly_stats(year, month):
    """
    Vráti štatistiky pre Plánovač.
    """
    # 1. Získame históriu (tá už teraz používa opravený výpočet)
    prev_balances = get_balances_up_to(year, month)
    
    employees = Employees.objects.filter(is_active=True)
    stats = []

    for emp in employees:
        # 2. Vypočítame aktuálny mesiac (znova cez spoločnú funkciu)
        month_data = calculate_month_data(emp, year, month)

        prev_balance = prev_balances.get(emp.id, 0.0)
        
        # 3. Spojíme to dokopy
        total_balance = prev_balance + month_data['diff']

        stats.append({
            "user_id": emp.id,
            "prevBalance": round(prev_balance, 2),
            "fund": round(month_data['fund'], 2),
            "worked": round(month_data['worked'], 2),
            "diff": round(month_data['diff'], 2),
            "total": round(total_balance, 2),
            "night": round(month_data['night'], 1),
            "weekend": round(month_data['weekend'], 1),
            "holiday": round(month_data['holiday'], 1)
        })

    return stats
    """
    Vráti kompletnú štatistiku pre tabuľku v Plánovači.
    Kombinuje historický prenos (get_balances_up_to) s aktuálne naplánovanými hodinami.
    """
    # 1. Získame prenos z minulosti (použijeme funkciu, ktorú už máte)
    prev_balances = get_balances_up_to(year, month)

    # 2. Získame fond pre tento mesiac (použijeme funkciu, ktorú už máte)
    fund = calculate_working_fund(year, month) 

    # 3. Zoznam aktívnych zamestnancov
    employees = Employees.objects.filter(is_active=True)
    
    stats = []

    for emp in employees:
        # Odpracované v tomto mesiaci (z PlannedShifts, lebo sme v plánovači)
        shifts = PlannedShifts.objects.filter(
            user=emp,
            date__year=year,
            date__month=month,
            hidden=False
        ).select_related('type_shift') # Optimalizácia

        worked_hours = 0.0
        night_hours = 0.0
        weekend_hours = 0.0
        
        for s in shifts:
            # A. Výpočet trvania smeny (použijeme vašu logiku _get_duration alebo podobnú)
            duration = 0.0
            if s.custom_start and s.custom_end:
                start_dt = datetime.combine(s.date, s.custom_start)
                end_dt = datetime.combine(s.date, s.custom_end)
                
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                elif s.custom_end == time(0,0) and start_dt != end_dt:
                     end_dt += timedelta(days=1)
                
                diff = (end_dt - start_dt).total_seconds() / 3600.0
                duration = diff
            elif s.type_shift and s.type_shift.duration_time:
                 duration = float(s.type_shift.duration_time)

            worked_hours += duration

            # B. Víkendy
            if s.date.weekday() >= 5: # 5=Sobota, 6=Nedeľa
                weekend_hours += duration
            
            # C. Nočné (Tu si upravte podmienku podľa toho, ako označujete nočné)
            # Napríklad kontrola názvu alebo času
            if (s.type_shift and s.type_shift.shortName == 'Ns') or \
               (s.type_shift and 'Nočná' in s.type_shift.nameShift):
                 night_hours += min(duration, 8) 

        # 4. Finálna matematika pre tabuľku
        prev_balance = prev_balances.get(emp.id, 0.0)
        diff = worked_hours - fund
        total_balance = prev_balance + diff

        stats.append({
            "user_id": emp.id,
            "prevBalance": round(prev_balance, 2),
            "fund": round(fund, 2),
            "worked": round(worked_hours, 2),
            "diff": round(diff, 2),
            "total": round(total_balance, 2),
            "night": round(night_hours, 1),
            "weekend": round(weekend_hours, 1),
            "holiday": 0.0 
        })

    return stats


# WorkTrackApi/services.py

from django.db.models import Sum, Q
# ... (ostatné importy)

def get_yearly_report_data(year):
    employees = Employees.objects.filter(is_active=True).order_by('last_name')
    months = range(1, 13)
    
    # 1. HLAVNÁ TABUĽKA (Mesiace x Zamestnanci)
    matrix = {}
    
    for emp in employees:
        emp_data = {}
        
        # Inicializácia sumárneho riadku pre zamestnanca
        total_stats = {
            "so": 0.0, "ne": 0.0, "sv": 0.0, 
            "noc": 0.0, "den": 0.0, "pn": 0.0
        }

        for m in months:
            # Definujeme hranice mesiaca pre výpočet nočnej
            month_start = datetime(year, m, 1)
            if m == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, m + 1, 1)

            # Získame smeny: Hľadáme aj o deň skôr, aby sme zachytili nočnú z prelomu mesiacov
            query_start = (month_start - timedelta(days=1)).date()
            query_end = (next_month - timedelta(days=1)).date()

            shifts = PlannedShifts.objects.filter(
                user=emp, 
                date__range=(query_start, query_end), 
                hidden=False
            ).select_related('type_shift')
            
            stats = {
                "so": 0.0, "ne": 0.0, "sv": 0.0, 
                "noc": 0.0, "den": 0.0, "pn": 0.0
            }
            
            for s in shifts:
                duration = 0.0
                start_dt = None
                end_dt = None

                # A. Výpočet časov
                if s.custom_start and s.custom_end:
                    start_dt = datetime.combine(s.date, s.custom_start)
                    end_dt = datetime.combine(s.date, s.custom_end)
                    if end_dt < start_dt: end_dt += timedelta(days=1)
                    elif s.custom_end == time(0,0) and start_dt != end_dt: end_dt += timedelta(days=1)
                    duration = (end_dt - start_dt).total_seconds() / 3600.0
                elif s.type_shift and s.type_shift.duration_time:
                    duration = float(s.type_shift.duration_time)
                
                # B. Štandardné hodiny (Víkend, Sviatok, Deň)
                # Tieto rátame len vtedy, ak smena patrí do tohto mesiaca DÁTUMOM ZAČIATKU
                if s.date.month == m and s.date.year == year:
                    # Rozdelenie podľa typu dňa
                    wd = s.date.weekday()
                    if wd == 5: stats["so"] += duration
                    elif wd == 6: stats["ne"] += duration
                    
                    # Sviatky
                    is_holiday = CalendarDay.objects.filter(date=s.date, is_holiday=True).exists()
                    if is_holiday:
                        stats["sv"] += duration
                    
                    # Bežné hodiny (Deň)
                    stats["den"] += duration

                    # PN / Dovolenka
                    if s.type_shift_id == 21: # Dovolenka
                         pass 
                    if s.type_shift_id == 23: # PN
                         stats["pn"] += 1 

                # C. Nočné (Špeciálny výpočet s rozdelením)
                if (s.type_shift and s.type_shift.shortName == 'Ns') or \
                   (s.type_shift and 'Nočná' in s.type_shift.nameShift):
                    
                    if start_dt and end_dt:
                        night_seconds = _calculate_night_overlap(
                            start_dt, 
                            end_dt, 
                            limit_start=month_start, 
                            limit_end=next_month
                        )
                        stats["noc"] += (night_seconds / 3600.0)

            # Priebežná sumarizácia do TOTAL
            total_stats["so"] += stats["so"]
            total_stats["ne"] += stats["ne"]
            total_stats["sv"] += stats["sv"]
            total_stats["noc"] += stats["noc"]
            total_stats["den"] += stats["den"]
            total_stats["pn"] += stats["pn"]

            # Zaokrúhlenie mesačných štatistík
            for key in stats:
                stats[key] = round(stats[key], 2)

            emp_data[m] = stats
        
        # Pridanie TOTAL riadku do dát zamestnanca (zaokrúhlený)
        for key in total_stats:
            total_stats[key] = round(total_stats[key], 2)
        
        emp_data["total"] = total_stats  # <--- TU JE NOVÝ RIADOK

        matrix[emp.id] = {
            "name": f"{emp.last_name} {emp.first_name}",
            "data": emp_data
        }

    # 2. SVIATKY (Bez zmeny)
    def get_holidays_summary(target_year):
        holidays = CalendarDay.objects.filter(date__year=target_year, is_holiday=True).order_by('date')
        summary = []
        for h in holidays:
            day_records = []
            for emp in employees:
                shift = PlannedShifts.objects.filter(user=emp, date=h.date, hidden=False).first()
                hours = 0.0
                
                if shift:
                    if shift.custom_start and shift.custom_end:
                        start = datetime.combine(shift.date, shift.custom_start)
                        end = datetime.combine(shift.date, shift.custom_end)
                        if end < start: end += timedelta(days=1)
                        elif shift.custom_end == time(0,0) and start != end: end += timedelta(days=1)
                        hours = (end - start).total_seconds() / 3600.0
                    elif shift.type_shift and shift.type_shift.duration_time:
                         hours = float(shift.type_shift.duration_time)
                
                if hours > 0:
                    day_records.append({"user_id": emp.id, "hours": round(hours, 1)})
            
            summary.append({
                "date": h.date,
                "name": h.holiday_name or "Sviatok", 
                "records": day_records
            })
        return summary

    return {
        "year": year,
        "employees": [{"id": e.id, "name": f"{e.last_name} {e.first_name}"} for e in employees],
        "matrix": matrix,
        "holidays_current": get_holidays_summary(year),
        "holidays_prev": get_holidays_summary(year - 1)
    }