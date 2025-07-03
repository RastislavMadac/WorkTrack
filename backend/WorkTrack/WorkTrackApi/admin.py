from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Employees, TypeShift,Attendance, PlannedShifts

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
    list_display = ('user', 'date', 'type_shift', 'custom_start', 'custom_end')
    list_filter = ('user', 'type_shift')
    search_fields = ('user__username', 'note')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Zavolaj logiku nočnej smeny po uložení záznamu
        obj.handle_night_shift()

@admin.register(PlannedShifts)
class PlannedShiftsAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'type_shift', 'custom_start', 'custom_end','note', 'is_changed', 'change_reason')
    list_filter = ('user', 'type_shift')
    