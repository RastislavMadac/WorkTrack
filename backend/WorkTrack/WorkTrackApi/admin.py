from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Employees, TypeShift,Attendance, PlannedShifts, CalendarDay, ChangeReason
from .utils.attendance_utils import create_attendance_from_planned_shift

@admin.register(Employees)
class EmployeesAdmin(UserAdmin):
    model = Employees
    readonly_fields = ("id",)
    fieldsets = (
        (None, {"fields": ("id","username", "password")}),
        (_("Osobné údaje"), {"fields": ("first_name", "last_name", "email", "personal_number", "role")}),
        (_("Oprávnenia"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Dôležité dátumy"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "password1", "password2",
                "email", "first_name", "last_name", "personal_number", "role"
            ),
        }),
    )

    list_display = ("id",'username', 'email', 'first_name', 'last_name', 'personal_number', 'role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'personal_number')
    ordering = ('username',)



@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'date', 'type_shift', 'custom_start','planned_shift', 'custom_end', 'note', 'exchanged_with')
    list_filter = ('user', 'type_shift','exchanged_with')
    list_display_links = ('id', 'user')
    search_fields = ('user__username', 'note')

    def save_model(self, request, obj, form, change):
        # Zaokrúhli časy, ak sú zadané
        if obj.custom_start:
            obj.custom_start = obj.round_to_nearest_half_hour(obj.custom_start)
        if obj.custom_end:
            obj.custom_end = obj.round_to_nearest_half_hour(obj.custom_end)

        # Ak je to nový záznam a má zvolenú plánovanú smenu, vytvor ho podľa nej
        if not change and obj.planned_shift_id:
            attendance = create_attendance_from_planned_shift(
                
                user=obj.user,
                date=obj.date,
                planned_shift_id=obj.planned_shift_id
            )
            if attendance:
                print("✅ Attendance vytvorený podľa plánovanej smeny.")
                return  # Už sme vytvorili nový záznam, nič ďalšie netreba

        # Inak bežné uloženie
        super().save_model(request, obj, form, change)


@admin.register(PlannedShifts)
class PlannedShiftsAdmin(admin.ModelAdmin):
    
    list_display = ('id','user', 'date', 'type_shift', 'custom_start', 'custom_end','note', 'transferred', 'is_changed','hidden', 'change_reason')
    list_filter = ('user', 'type_shift')
    list_display_links = ('id', 'user')

@admin.register(TypeShift)
class TypeShiftsAdmin(admin.ModelAdmin):
    
    list_display = ('id', 'nameShift', 'start_time', 'end_time', 'duration_time','shortName')
    list_filter = ('id','nameShift')

@admin.register(CalendarDay)
class CalendarDayAdmin(admin.ModelAdmin):
    list_display = ("date", "day", "is_weekend", "is_holiday", "holiday_name")
    list_filter = ("is_weekend", "is_holiday")
    search_fields = ("day", "holiday_name")

@admin.register(ChangeReason)
class ChangeReasonAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "category")
   