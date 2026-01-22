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

# class PlannedShiftsSerializer(serializers.ModelSerializer):
  
#     custom_start = serializers.TimeField(required=False, allow_null=True)
#     custom_end = serializers.TimeField(required=False, allow_null=True)

#  # Nové polia pre frontend
#     shortname = serializers.CharField(source='type_shift.shortName', read_only=True)
#     duration = serializers.SerializerMethodField()
#     class Meta:
#         model = PlannedShifts
#         fields = '__all__'
#         read_only_fields = ['calendar_day']

    

#     def get_duration(self, obj):
#         from datetime import datetime, timedelta

#         # 1️⃣ Ak je zadaný custom_start/custom_end → spočítame podľa nich
#         if obj.custom_start and obj.custom_end:
#             start = datetime.combine(datetime.today(), obj.custom_start)
#             end = datetime.combine(datetime.today(), obj.custom_end)
#             if end < start:
#                 end += timedelta(days=1)  # smena cez polnoc
#             delta = end - start
#             hours, remainder = divmod(delta.seconds, 3600)
#             minutes, _ = divmod(remainder, 60)
#             return f"{hours:02d}:{minutes:02d}"

#         # 2️⃣ Inak použijeme duration_time z DB (napr. 7.5 → 07:30)
#         if obj.duration_time:
#             try:
#                 hours_float = float(obj.duration_time)      # 7.5
#                 minutes = int(hours_float * 60)             # 450
#                 h = minutes // 60                           # 7
#                 m = minutes % 60                            # 30
#                 return f"{h:02d}:{m:02d}"                   # "07:30"
#             except Exception:
#                 return None

#         return None
    


#     def to_internal_value(self, data):
#         # Ak chýba custom_start alebo je null, doplníme z type_shift
#         if ('custom_start' not in data or data['custom_start'] in [None, '']):
#             type_shift_id = data.get('type_shift')
#             if type_shift_id:
#                 ts = TypeShift.objects.filter(id=type_shift_id).first()
#                 if ts and ts.start_time:
#                     data['custom_start'] = ts.start_time.isoformat()

#         if ('custom_end' not in data or data['custom_end'] in [None, '']):
#             type_shift_id = data.get('type_shift')
#             if type_shift_id:
#                 ts = TypeShift.objects.filter(id=type_shift_id).first()
#                 if ts and ts.end_time:
#                     data['custom_end'] = ts.end_time.isoformat()

#         return super().to_internal_value(data)

#     def validate(self, data):
#         user = data.get('user') or getattr(self.instance, 'user', None)
#         type_shift = data.get('type_shift') or getattr(self.instance, 'type_shift', None)
#         custom_start = data.get('custom_start')
#         custom_end = data.get('custom_end')

#         if not user:
#             raise ValidationError("Používateľ musí byť zadaný.")

#         # Tu môžeš mať ďalšie validácie
#         # Napr. kontrola rolí a povolení pri editácii

#         return data

#     def create(self, validated_data):
#         date = validated_data.get('date')
#         if date and not validated_data.get('calendar_day'):
#             try:
#                 validated_data['calendar_day'] = CalendarDay.objects.get(date=date)
#             except CalendarDay.DoesNotExist:
#                 raise ValidationError(f"Pre dátum {date} neexistuje CalendarDay.")
#         return super().create(validated_data)

#     def update(self, instance, validated_data):
#         date = validated_data.get('date', instance.date)
#         if date and not validated_data.get('calendar_day', instance.calendar_day):
#             try:
#                 validated_data['calendar_day'] = CalendarDay.objects.get(date=date)
#             except CalendarDay.DoesNotExist:
#                 raise ValidationError(f"Pre dátum {date} neexistuje CalendarDay.")
#         return super().update(instance, validated_data)
#NOTE - nEW
class PlannedShiftsSerializer(serializers.ModelSerializer):
    

    # Polia pre frontend (aby si nemusel robiť lookupy navyše)
    shift_name = serializers.CharField(source='type_shift.nameShift', read_only=True)
    short_name = serializers.CharField(source='type_shift.shortName', read_only=True)
    
    # Vypočítané trvanie pre zobrazenie
    duration = serializers.SerializerMethodField()

    class Meta:
        model = PlannedShifts
        fields = '__all__'
        read_only_fields = ['calendar_day']
        extra_kwargs = {
                    'custom_start': {'required': False, 'allow_null': True},
                    'custom_end': {'required': False, 'allow_null': True},
                }
        

    def validate(self, data):
        # 1. Validácia zaokrúhlenia (toto funguje)
        for field in ['custom_start', 'custom_end']:
            time_val = data.get(field)
            if time_val:
                if time_val.minute not in [0, 30] or time_val.second != 0:
                    raise serializers.ValidationError({
                        field: f"Čas v poli {field} musí byť zaokrúhlený na celú hodinu alebo polhodinu."
                    })

       
        
        # 2. Príprava dát
        user = data.get('user')
        shift_date = data.get('date')
        type_shift = data.get('type_shift')
        start_time = data.get('custom_start')
        end_time = data.get('custom_end')

        # Doplnenie časov z type_shift
        if type_shift:
            if not start_time: start_time = type_shift.start_time
            if not end_time: end_time = type_shift.end_time


        # 3. KONTROLA PREKRÝVANIA
        if user and shift_date and start_time and end_time:
            new_start = datetime.combine(shift_date, start_time)
            new_end = datetime.combine(shift_date, end_time)
            if new_end <= new_start:
                new_end += timedelta(days=1)

            check_start = shift_date - timedelta(days=1)
            check_end = shift_date + timedelta(days=1)


            # Hľadáme v DB
            existing_shifts = PlannedShifts.objects.filter(
                user=user,
                date__range=(check_start, check_end),
                hidden=False
            )
            
            # Vylúčenie samého seba pri update
            if self.instance:
                existing_shifts = existing_shifts.exclude(pk=self.instance.pk)

         

            for shift in existing_shifts:
                s_start = shift.custom_start or (shift.type_shift.start_time if shift.type_shift else None)
                s_end = shift.custom_end or (shift.type_shift.end_time if shift.type_shift else None)
                
              

                if s_start and s_end:
                    ex_start = datetime.combine(shift.date, s_start)
                    ex_end = datetime.combine(shift.date, s_end)
                    if ex_end <= ex_start:
                        ex_end += timedelta(days=1)

                    # Porovnanie intervalov
                    # (StartA < EndB) and (EndA > StartB)
                    overlap = new_start < ex_end and new_end > ex_start
                 

                    if overlap:
                        conflict_name = shift.type_shift.nameShift if shift.type_shift else "Iná smena"
                        time_range = f"{s_start}-{s_end}"
                       
                        
                        raise serializers.ValidationError({
                            "non_field_errors": [
                                f"Konflikt: Zamestnanec už má smenu '{conflict_name}' v čase {time_range} (Dátum: {shift.date})."
                            ]
                        })
       
        return data
   
    def get_duration(self, obj):
        from datetime import datetime, timedelta
        # 1. Ak má custom časy
        if obj.custom_start and obj.custom_end:
            start = datetime.combine(datetime.today(), obj.custom_start)
            end = datetime.combine(datetime.today(), obj.custom_end)
            if end < start:
                end += timedelta(days=1)
            delta = end - start
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}"
        
        # 2. Inak berie z typu smeny
        if obj.type_shift and obj.type_shift.duration_time:
             # Predpokladáme, že duration_time je Decimal alebo string
             return str(obj.type_shift.duration_time)
        return None

    
    
class EmployeesSerializer(serializers.ModelSerializer):
    planned_shifts = PlannedShiftsSerializer(many=True, read_only=True)
    class Meta:
        model = Employees
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'personal_number', 'role','is_active', 'planned_shifts',]


class CalendarDaySerializers(serializers.ModelSerializer):
    class Meta:
        model = CalendarDay
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=Employees.objects.all(), required=False
    )
    planned_shift = serializers.PrimaryKeyRelatedField(
        queryset=PlannedShifts.objects.filter(hidden=False), required=False
    )

    class Meta:
        model = Attendance
        fields = '__all__'
        extra_kwargs = {
            'date': {'required': False, 'allow_null': True},
        }

    def to_time(self, value):
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return parse_time(value)
        return None

    def validate_user(self, value):
        request_user = self.context['request'].user
        if request_user.role == 'worker' and value and value != request_user:
            raise serializers.ValidationError("Nemáte oprávnenie nastaviť iného používateľa.")
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        planned_shift = attrs.get('planned_shift') or (instance.planned_shift if instance else None)
        custom_start = attrs.get('custom_start') or (instance.custom_start if instance else None)
        custom_end = attrs.get('custom_end') or (instance.custom_end if instance else None)

      

        if not attrs.get("date") and planned_shift:
            attrs["date"] = planned_shift.date
        if not attrs.get("date"):
            attrs["date"] = dt_date.today()

        return attrs

    def create(self, validated_data):
        planned_shift = validated_data.get('planned_shift')

        input_custom_start = self.to_time(self.initial_data.get('custom_start'))
        input_custom_end = self.to_time(self.initial_data.get('custom_end'))

        if planned_shift:
            if input_custom_start and input_custom_start != planned_shift.custom_start:
                validated_data['custom_start'] = input_custom_start
            else:
                validated_data['custom_start'] = planned_shift.custom_start

            if input_custom_end and input_custom_end != planned_shift.custom_end:
                validated_data['custom_end'] = input_custom_end
            else:
                validated_data['custom_end'] = planned_shift.custom_end

            validated_data['type_shift'] = planned_shift.type_shift
            validated_data['calendar_day'] = planned_shift.calendar_day

        return Attendance.objects.create(**validated_data)

    def update(self, instance, validated_data):
        planned_shift = instance.planned_shift

        # Ak v PATCH príde custom_start a existuje planned_shift → uprav aj ju
        if 'custom_start' in validated_data and planned_shift:
            planned_shift.custom_start = validated_data['custom_start']
            planned_shift.save(update_fields=['custom_start'])

        # Rovnaké pre custom_end
        if 'custom_end' in validated_data and planned_shift:
            planned_shift.custom_end = validated_data['custom_end']
            planned_shift.save(update_fields=['custom_end'])

        # Aktualizácia samotného Attendance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
