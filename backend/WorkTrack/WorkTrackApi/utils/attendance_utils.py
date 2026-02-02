from datetime import datetime, timedelta, time
from django.core.exceptions import ValidationError

# ==========================================
# ZÁKLADNÉ UTILITY
# ==========================================

def round_to_nearest_half_hour(t: time) -> time:
    dt = datetime.combine(datetime.today(), t)
    minute = dt.minute
    down = minute % 30
    up = 30 - down
    if down < up:
        dt_rounded = dt - timedelta(minutes=down)
    else:
        dt_rounded = dt + timedelta(minutes=up)
    return dt_rounded.time()

def create_attendance_from_planned_shift(user, date, planned_shift_id):
    from WorkTrackApi.models import PlannedShifts, Attendance
    planned_shift = PlannedShifts.objects.filter(
        id=planned_shift_id,
        user=user,
        date=date,
        hidden=False,
    ).first()

    if not planned_shift:
        return None

    attendance = Attendance.objects.create(
        user=user,
        date=planned_shift.date,
        custom_start=planned_shift.custom_start,
        custom_end=planned_shift.custom_end,
        type_shift=planned_shift.type_shift,
        planned_shift=planned_shift,
        note=planned_shift.note or "Vytvorená dochádzka na základe plánovanej smeny",
    )
    return attendance

def prevziat_smenu_logic(request_user, target_shift_id, user_id=None, note=None):
    from WorkTrackApi.models import PlannedShifts, Attendance, Employees
    try:
        target_shift = PlannedShifts.objects.get(pk=target_shift_id)
    except PlannedShifts.DoesNotExist:
        return None, "Plánovaná smena neexistuje."

    if request_user.role in ['admin', 'manager'] and user_id:
        try:
            user_to_assign = Employees.objects.get(pk=user_id)
        except Employees.DoesNotExist:
            return None, "Používateľ neexistuje."
    else:
        user_to_assign = request_user

    attendance = Attendance.objects.create(
        user=user_to_assign,
        date=target_shift.date,
        type_shift=target_shift.type_shift,
        custom_start=target_shift.custom_start,
        custom_end=target_shift.custom_end,
        note=note or f"Preberám smenu od {target_shift.user}",
    )
    exchange_shift_logic(attendance, target_shift)
    return attendance, None

def exchange_shift_logic(attendance, target_shift):
    from WorkTrackApi.models import PlannedShifts
    if not target_shift:
        raise ValidationError("Nebola vybraná smena na výmenu.")
    if attendance.user == target_shift.user:
        raise ValidationError("Nemôžeš si vymeniť smenu sám so sebou.")
    if attendance.date != target_shift.date or attendance.type_shift != target_shift.type_shift:
        raise ValidationError("Smena na výmenu musí byť rovnakého typu a dňa.")

    new_shift = PlannedShifts.objects.create(
        user=attendance.user,
        date=attendance.date,
        type_shift=attendance.type_shift,
        custom_start=attendance.custom_start,
        custom_end=attendance.custom_end,
        transferred=True,
        is_changed=True,
        note=f"Pozor Výmena smeny s {target_shift.user} – treba zadať dôvod"
    )
    target_shift.hidden = True
    target_shift.save(update_fields=["hidden"])
    attendance.exchanged_with = new_shift
    attendance.save()
    print(f"🔁 Výmena smeny: {attendance.user} ↔ {target_shift.user}")

# ==========================================
# NOČNÉ SMENY
# ==========================================

def split_night_planned_shift(planned_shift):
    from WorkTrackApi.models import PlannedShifts
    if not (planned_shift.type_shift and planned_shift.type_shift.id == 20):
        return

    start = planned_shift.custom_start
    end = planned_shift.custom_end
    midnight = time(0, 0)
    
    if end == midnight:
        return

    planned_shift.custom_end = midnight
    planned_shift.save(update_fields=['custom_end'])
    print(f"✂️ Plánovaná smena {planned_shift.id} skrátená do polnoci.")

    next_day = planned_shift.date + timedelta(days=1)
    exists = PlannedShifts.objects.filter(
        user=planned_shift.user,
        date=next_day,
        custom_start=midnight,
        type_shift=planned_shift.type_shift,
        hidden=False
    ).exists()

    if not exists:
        PlannedShifts.objects.create(
            user=planned_shift.user,
            date=next_day,
            custom_start=midnight,
            custom_end=end,
            type_shift=planned_shift.type_shift,
            calendar_day=None,
            note=f"{planned_shift.note} (pokračovanie)",
            transferred=planned_shift.transferred,
            is_changed=planned_shift.is_changed,
            hidden=False
        )
        print(f"➕ Vytvorená druhá časť plánu na {next_day}")

def handle_night_shift(attendance):
    from WorkTrackApi.models import Attendance, PlannedShifts
    
    # 1. Kontrola typu smeny
    if not (attendance.type_shift and attendance.type_shift.id == 20):
        return

    midnight = time(0, 0)
    start = attendance.custom_start
    end = attendance.custom_end

    # 2. Zistíme, či smena prechádza cez polnoc
    if start > end or end == midnight:
        
        real_end_time = end 
        
        # A) Orezať prvú časť
        if end != midnight:
            print(f"✂️ Delím dochádzku {attendance.id} (pôvodne do {end}) na polnoc.")
            attendance.custom_end = midnight
            attendance.save(update_fields=['custom_end'])
        
        # B) Druhá časť
        next_day = attendance.date + timedelta(days=1)
        
        if Attendance.objects.filter(user=attendance.user, date=next_day, custom_start=midnight).exists():
            return

        next_part_plan = PlannedShifts.objects.filter(
            user=attendance.user, date=next_day, type_shift=attendance.type_shift,
            custom_start=midnight, hidden=False, transferred=False 
        ).first()

        new_att = None
        if next_part_plan:
            print(f"🔗 Automaticky preklápam druhú časť nočnej smeny (ID plánu: {next_part_plan.id})")
            final_end = real_end_time if real_end_time != midnight else next_part_plan.custom_end
            new_att = Attendance.objects.create(
                user=attendance.user, date=next_day, type_shift=attendance.type_shift,
                planned_shift=next_part_plan, custom_start=next_part_plan.custom_start,
                custom_end=final_end, note="Pokračovanie nočnej smeny (podľa plánu)"
            )
        else:
            print("⚠️ Nenájdený plán pre 2. časť, vytváram voľný Attendance.")
            final_end = real_end_time if real_end_time != midnight else time(9, 0)
            new_att = Attendance.objects.create(
                user=attendance.user, date=next_day, type_shift=attendance.type_shift,
                custom_start=midnight, custom_end=final_end, note="Pokračovanie nočnej smeny (bez plánu)"
            )

        # C) Kontrola nadčasov na druhej časti
        if new_att:
            handle_end_shift_time(new_att)

# ==========================================
# RIEŠENIE ČASOV (Skorší príchod / Neskorší odchod)
# ==========================================

# WorkTrackApi/utils/attendance_utils.py

def handle_start_shift_time(attendance_instance):
    from WorkTrackApi.models import PlannedShifts, Attendance, TypeShift, ChangeReason

    # Nájdeme plánovanú smenu prepojenú s touto dochádzkou
    planned_shift = attendance_instance.planned_shift
    if not planned_shift: return 

    # Časy z dochádzky (realita) a plánu
    real_start = attendance_instance.custom_start
    plan_start = planned_shift.custom_start

    if not (real_start and plan_start): return

    # --- SCENÁR A: SKORŠÍ PRÍCHOD (Nadčas) -> NOVÁ SMENA ---
    if real_start < plan_start:
        print(f"🟢 Skorší príchod: Vytváram Inú činnosť (Extra)")

        try:
            type_shift_extra = TypeShift.objects.get(id=22) # Iná činnosť
        except TypeShift.DoesNotExist: return

        # Zoberieme dôvod z pôvodného plánu (ak bol nastavený v serializeri) alebo default
        reason = planned_shift.change_reason 

        # Prevencia duplicít
        if PlannedShifts.objects.filter(
            user=attendance_instance.user, date=attendance_instance.date,
            custom_start=real_start, custom_end=plan_start,
            type_shift=type_shift_extra
        ).exists(): return

        # 1. Vytvoríme EXTRA PLÁN (Typ 22)
        extra_plan = PlannedShifts.objects.create(
            user=attendance_instance.user, date=attendance_instance.date,
            custom_start=real_start, custom_end=plan_start,
            type_shift=type_shift_extra, transferred=True, is_changed=True,
            change_reason=reason, approval_status='pending',
            note="Automaticky: Skorší príchod",
            calendar_day=planned_shift.calendar_day,
        )
        
        # 2. Vytvoríme EXTRA DOCHÁDZKU k tomu plánu
        Attendance.objects.create(
            user=attendance_instance.user, date=attendance_instance.date,
            planned_shift=extra_plan, custom_start=real_start, custom_end=plan_start,
            type_shift=type_shift_extra, note="Auto: Skorší príchod",
            calendar_day=extra_plan.calendar_day,
        )
        
        # 3. Pôvodnú dochádzku zarovnáme na plán (aby sa neprekrývala)
        # Poznámka: Pôvodný plán nemeníme, lebo ten platí od svojho začiatku
        attendance_instance.custom_start = plan_start
        attendance_instance.save(update_fields=['custom_start'])

    # --- SCENÁR B: NESKORÝ PRÍCHOD (Meškanie) -> ÚPRAVA PLÁNU ---
    elif real_start > plan_start:
        print(f"🔻 Neskorý príchod: Krátim pôvodný plán")
        
        # Tu len potvrdíme zmeny v pláne
        planned_shift.custom_start = real_start
        planned_shift.is_changed = True
        # change_reason už bol nastavený v serializeri, tu ho len potvrdíme ak treba
        if not planned_shift.change_reason:
             # Fallback ak by nebol (napr. ID 9)
             pass 
        
        planned_shift.note = (planned_shift.note or "") + " (Krátené pre meškanie)"
        planned_shift.save(update_fields=['custom_start', 'is_changed', 'note'])


def handle_end_shift_time(attendance_instance):
    from WorkTrackApi.models import PlannedShifts, Attendance, TypeShift

    planned_shift = attendance_instance.planned_shift
    if not planned_shift: return 

    real_end = attendance_instance.custom_end
    plan_end = planned_shift.custom_end

    if not (real_end and plan_end): return

    # --- SCENÁR A: NESKORŠÍ ODCHOD (Nadčas) -> NOVÁ SMENA ---
    if real_end > plan_end:
        print(f"🟢 Neskorší odchod: Vytváram Inú činnosť (Extra)")
        try: type_shift_extra = TypeShift.objects.get(id=22)
        except: return

        reason = planned_shift.change_reason

        if PlannedShifts.objects.filter(
            user=attendance_instance.user, date=attendance_instance.date,
            custom_start=plan_end, custom_end=real_end, type_shift=type_shift_extra
        ).exists(): return

        extra_plan = PlannedShifts.objects.create(
            user=attendance_instance.user, date=attendance_instance.date,
            custom_start=plan_end, custom_end=real_end,
            type_shift=type_shift_extra, transferred=True, is_changed=True,
            change_reason=reason, approval_status='pending',
            note="Automaticky: Neskorší odchod",
            calendar_day=planned_shift.calendar_day,
        )

        Attendance.objects.create(
            user=attendance_instance.user, date=attendance_instance.date,
            planned_shift=extra_plan, custom_start=plan_end, custom_end=real_end,
            type_shift=type_shift_extra, note="Auto: Neskorší odchod",
            calendar_day=extra_plan.calendar_day,
        )

        attendance_instance.custom_end = plan_end
        attendance_instance.save(update_fields=['custom_end'])

    # --- SCENÁR B: SKORŠÍ ODCHOD (Útek) -> ÚPRAVA PLÁNU ---
    elif real_end < plan_end:
        print(f"🔻 Skorší odchod: Krátim pôvodný plán")
        planned_shift.custom_end = real_end
        planned_shift.is_changed = True
        planned_shift.note = (planned_shift.note or "") + " (Krátené pre odchod)"
        planned_shift.save(update_fields=['custom_end', 'is_changed', 'note'])
def handle_any_shift_time(attendance_instance):
    handle_start_shift_time(attendance_instance)
    handle_end_shift_time(attendance_instance)