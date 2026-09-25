from django.contrib import admin

from apps.programs.models import Program, ProgramDomain


class ProgramDomainInline(admin.TabularInline):
    model = ProgramDomain
    extra = 1


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "allow_self_enrolment", "created_at")
    list_filter = ("is_active", "allow_self_enrolment")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProgramDomainInline,)


@admin.register(ProgramDomain)
class ProgramDomainAdmin(admin.ModelAdmin):
    list_display = ("host", "program", "is_primary")
    search_fields = ("host",)
