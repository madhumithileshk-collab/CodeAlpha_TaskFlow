from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role_title', 'phone', 'created_at')
    search_fields = ('user__username', 'user__email', 'role_title')
    list_filter = ('role_title', 'created_at')
