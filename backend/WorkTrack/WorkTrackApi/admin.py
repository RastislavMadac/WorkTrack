from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Employees, TypeShift,Attendance, PlannedShifts, CalendarDay

@admin.register(Employees)
class EmployeesAdmin(UserAdmin):
    model = Employees

    fieldsets = (
        (None, {"fields": ("username", "password")}),
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

    list_display = ('username', 'email', 'first_name', 'last_name', 'personal_number', 'role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'personal_number')
    ordering = ('username',)

@admin.register(TypeShift)
class TypeShiftAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            "fields": ("nameShift", "start_time", "end_time", "duration_time"),
            "description": _("Zadaj údaje o smene"),
        }),
    )
    list_display = ("nameShift", "start_time", "end_time", "duration_time")
    search_fields = ("nameShift",)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'type_shift', 'custom_start', 'custom_end', 'note', 'exchanged_with')
    list_filter = ('user', 'type_shift','exchanged_with')
    search_fields = ('user__username', 'note')

    def save_model(self, request, obj, form, change):
    # Zaokrúhli custom_start a custom_end pred uložením
        if obj.custom_start:
            obj.custom_start = obj.round_to_nearest_half_hour(obj.custom_start)
        if obj.custom_end:
            obj.custom_end = obj.round_to_nearest_half_hour(obj.custom_end)

        # Ulož objekt
        super().save_model(request, obj, form, change)

        print("Volám handle_night_shift()")
        obj.handle_night_shift()

        print("Volám handle_any_shift_time()")
        Attendance.handle_any_shift_time()

        print("Volam")

        # Ak je nastavené exchanged_with, spusti výmenu smien
        if obj.exchanged_with:
            obj.exchange_shift(obj.exchanged_with)
    

@admin.register(PlannedShifts)
class PlannedShiftsAdmin(admin.ModelAdmin):
    exclude = ('custom_start', 'custom_end')
    list_display = ('user', 'date', 'type_shift', 'custom_start', 'custom_end','note', 'transferred', 'is_changed', 'change_reason')
    list_filter = ('user', 'type_shift')

@admin.register(CalendarDay)
class CalendarDayAdmin(admin.ModelAdmin):
    list_display = ("date", "day", "is_weekend", "is_holiday", "holiday_name")
    list_filter = ("is_weekend", "is_holiday")
    search_fields = ("day", "holiday_name")