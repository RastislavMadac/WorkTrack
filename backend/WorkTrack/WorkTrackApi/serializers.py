from rest_framework import serializers
from .models import Employees, TypeShift,Attendance, PlannedShifts,ChangeReason,CalendarDay
from.utils.attendance_utils import create_attendance_from_planned_shift
from datetime import date as dt_date, datetime, timedelta
from django.core.exceptions import ValidationError
from datetime import time
from django.utils.dateparse import parse_time





class TypeShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeShift
        fields = ['id', 'nameShift', 'start_time', 'end_time', 'duration_time','shortName']

class ChangeReasonSerializers(serializers.ModelSerializer):
    class Meta:
        model = ChangeReason
        fields = '__all__'




class PlannedShiftsSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source='type_shift.nameShift', read_only=True)
    short_name = serializers.CharField(source='type_shift.shortName', read_only=True)
    duration = serializers.SerializerMethodField()
# Pre čítanie: Vrátime celý objekt (názov, popis)
    change_reason_details = ChangeReasonSerializers(source='change_reason', read_only=True)
    
    # Pre zápis: Akceptujeme ID
    change_reason_id = serializers.PrimaryKeyRelatedField(
        queryset=ChangeReason.objects.all(), 
        source='change_reason', 
        write_only=True,
        required=False, 
        allow_null=True
    )
    class Meta:
        model = PlannedShifts
        fields = '__all__'
        read_only_fields = ['calendar_day']
        extra_kwargs = {
            'custom_start': {'required': False, 'allow_null': True},
            'custom_end': {'required': False, 'allow_null': True},
        }
        
    def validate(self, data):
        type_shift = data.get('type_shift')
        if not type_shift and self.instance:
            type_shift = self.instance.type_shift

        # --- STRICT MODE LOGIKA ---
        if type_shift:
            if type_shift.id != 22:
                # Pre bežné smeny NATVRDO nastavíme časy z číselníka
                data['custom_start'] = type_shift.start_time
                data['custom_end'] = type_shift.end_time
            else:
                # Pre ID 22 kontrolujeme zaokrúhlenie
                for field in ['custom_start', 'custom_end']:
                    time_val = data.get(field)
                    if time_val:
                        if time_val.minute not in [0, 30] or time_val.second != 0:
                            raise serializers.ValidationError({
                                field: f"Čas v poli {field} musí byť zaokrúhlený na celú hodinu alebo polhodinu."
                            })
        # --------------------------

        # Kontrola prekrývania (Logic Conflict) - skrátená verzia pre prehľadnosť
        user = data.get('user') or (self.instance.user if self.instance else None)
        shift_date = data.get('date') or (self.instance.date if self.instance else None)
        start_time = data.get('custom_start')
        end_time = data.get('custom_end')

        if user and shift_date and start_time and end_time:
            # ... tu ostáva tvoja pôvodná logika kontroly prekrývania ...
            pass 
        
        return data

    def get_duration(self, obj):
        # Vždy vrátiť HH:MM
        start_t = obj.custom_start or (obj.type_shift.start_time if obj.type_shift else None)
        end_t = obj.custom_end or (obj.type_shift.end_time if obj.type_shift else None)

        if start_t and end_t:
            d = datetime.today().date()
            start = datetime.combine(d, start_t)
            end = datetime.combine(d, end_t)
            if end < start: end += timedelta(days=1)
            delta = end - start
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}"
            
        if obj.type_shift and obj.type_shift.duration_time:
            return str(obj.type_shift.duration_time)
        return None
    def validate_user(self, value):
            """
            Nedovolí priradiť smenu zamestnancovi, ktorý má active=False.
            """
            # Ak vytvárame nový záznam a užívateľ je neaktívny -> CHYBA
            if not value.is_active:
                raise serializers.ValidationError(f"Zamestnanec {value} je neaktívny. Nemožno mu naplánovať smenu.")
            
            return value


class EmployeesSerializer(serializers.ModelSerializer):
    planned_shifts = PlannedShiftsSerializer(many=True, read_only=True)
    class Meta:
        model = Employees
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'personal_number', 'role','is_active', 'planned_shifts','initial_hours_balance', 'planned_shifts']


class CalendarDaySerializers(serializers.ModelSerializer):
    class Meta:
        model = CalendarDay
        fields = '__all__'



class AttendanceSerializer(serializers.ModelSerializer):
    change_reason_id = serializers.PrimaryKeyRelatedField(
        queryset=ChangeReason.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=Employees.objects.all(), required=False
    )
    
    # 1. ZMENA: QuerySet musí byť .all(), aby sme našli aj skryté (hidden=True) smeny
    planned_shift = serializers.PrimaryKeyRelatedField(
        queryset=PlannedShifts.objects.all(), 
        required=False, 
        allow_null=True
    )

    class Meta:
        model = Attendance
        fields = '__all__'
        extra_kwargs = {
            'date': {'required': False, 'allow_null': True},
        }

    def to_time(self, value):
        if isinstance(value, time): return value
        if isinstance(value, str): 
            parsed = parse_time(value)
            return parsed if parsed else None
        return None

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        planned_shift = attrs.get('planned_shift') or (instance.planned_shift if instance else None)
        change_reason = attrs.get('change_reason_id')
        
        input_start = self.to_time(self.initial_data.get('custom_start'))
        input_end = self.to_time(self.initial_data.get('custom_end'))

        # --- VALIDÁCIA ---

        if planned_shift:
            # 2. ZMENA: Ak je smena skrytá (skript ju označil ako absenciu), 
            # zamestnanec MUSÍ zadať dôvod, prečo to zapisuje neskoro.
            if planned_shift.hidden and not change_reason:
                raise serializers.ValidationError({
                    "change_reason_id": "Táto smena bola uzavretá ako chýbajúca. Musíte zadať dôvod dodatočného zápisu (napr. 'Zabudol som')."
                })

            # Validácia zmeny časov
            p_start = planned_shift.custom_start
            p_end = planned_shift.custom_end
            start_changed = input_start is not None and input_start != p_start
            end_changed = input_end is not None and input_end != p_end

            if (start_changed or end_changed) and not change_reason:
                raise serializers.ValidationError({
                    "change_reason_id": f"Čas sa nezhoduje s plánom. Musíte zadať dôvod."
                })
            
            # Strict mode dátumov
            attrs['date'] = planned_shift.date
            if not attrs.get('user'): attrs['user'] = planned_shift.user
        
        elif not instance and not planned_shift:
            if not change_reason:
                raise serializers.ValidationError({
                    "change_reason_id": "Vytvárate smenu mimo plánu. Musíte zadať dôvod."
                })
            if not attrs.get("date"): attrs["date"] = dt_date.today()

        return attrs

    def create(self, validated_data):
        planned_shift = validated_data.get('planned_shift')
        change_reason = validated_data.pop('change_reason_id', None)

        input_start = self.to_time(self.initial_data.get('custom_start'))
        input_end = self.to_time(self.initial_data.get('custom_end'))

        # --- SCENÁR A: MÁME PLÁNOVANÚ SMENU ---
        if planned_shift:
            
            # 3. ZMENA: LOGIKA "OŽIVENIA" (RECOVERY)
            # Ak bola smena hidden (absencia), ale teraz vytvárame dochádzku -> vrátime ju do hry.
            if planned_shift.hidden:
                print(f"🔄 Oživujem skrytú smenu ID {planned_shift.id}")
                planned_shift.hidden = False       # Už nie je skrytá (bude sa rátať)
                planned_shift.is_changed = True    # Bola zmenená (dodatočný zápis)
                planned_shift.approval_status = 'pending' # Manažér to musí schváliť
                
                if change_reason:
                    planned_shift.change_reason = change_reason
                
                planned_shift.note = (planned_shift.note or "") + " (Dodatočný zápis zamestnancom)"
                planned_shift.save()

            # Zvyšok logiky pre zmenu časov (Meškanie atď.)
            is_start_diff = input_start is not None and input_start != planned_shift.custom_start
            is_end_diff = input_end is not None and input_end != planned_shift.custom_end

            if (is_start_diff or is_end_diff) and change_reason:
                planned_shift.is_changed = True
                planned_shift.change_reason = change_reason
                planned_shift.approval_status = 'pending'
                # Ak sme ju práve neodkryli (nebola hidden), tak ju savneme tu
                if not planned_shift.hidden: 
                    planned_shift.save()

            # Nastavenie dát pre Attendance
            validated_data['custom_start'] = input_start if input_start else planned_shift.custom_start
            validated_data['custom_end'] = input_end if input_end else planned_shift.custom_end
            validated_data['type_shift'] = planned_shift.type_shift
            validated_data['calendar_day'] = planned_shift.calendar_day

            return Attendance.objects.create(**validated_data)

        # --- SCENÁR B: BEZ PLÁNU (Shadow Plan) ---
        else:
            # (Tento kód ostáva rovnaký ako predtým)
            user = validated_data.get('user')
            date_obj = validated_data.get('date')
            type_shift = validated_data.get('type_shift')
            if not type_shift:
                 try: type_shift = TypeShift.objects.get(id=22) 
                 except: raise serializers.ValidationError({"type_shift": "Chýba typ smeny."})

            calendar_day = CalendarDay.objects.filter(date=date_obj).first()

            new_shadow_plan = PlannedShifts.objects.create(
                user=user, date=date_obj, type_shift=type_shift,
                custom_start=input_start, custom_end=input_end,
                is_changed=True, transferred=True, 
                change_reason=change_reason,
                approval_status='pending',
                note="Automaticky vytvorené (Mimo plánu)",
                calendar_day=calendar_day
            )

            validated_data['planned_shift'] = new_shadow_plan
            validated_data['custom_start'] = input_start
            validated_data['custom_end'] = input_end
            validated_data['type_shift'] = type_shift
            validated_data['calendar_day'] = calendar_day

            return Attendance.objects.create(**validated_data)





class RosterItemSerializer(serializers.Serializer):
    """
    Tento serializer reprezentuje jednu bunku v Exceli (jeden deň pre jedného človeka).
    """
    user_id = serializers.IntegerField()
    date = serializers.DateField()
    type_shift_id = serializers.IntegerField(required=False, allow_null=True)
    custom_start = serializers.TimeField(required=False, allow_null=True)
    custom_end = serializers.TimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)

class BulkRosterSerializer(serializers.Serializer):
    """
    Tento serializer prijme zoznam všetkých smien na uloženie.
    """
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    shifts = RosterItemSerializer(many=True)
#end        