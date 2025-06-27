from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Employees, TypeShift

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