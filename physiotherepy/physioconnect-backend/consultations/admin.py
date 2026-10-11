from django.contrib import admin
from .models import ConsultationNote, ExerciseLibrary, ExercisePlan, ExercisePlanItem


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'doctor', 'created_at')


@admin.register(ExerciseLibrary)
class ExerciseLibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'body_region')
    search_fields = ('name', 'body_region')


class ExercisePlanItemInline(admin.TabularInline):
    model = ExercisePlanItem
    extra = 1


@admin.register(ExercisePlan)
class ExercisePlanAdmin(admin.ModelAdmin):
    list_display = ('patient', 'created_by', 'created_at')
    inlines = [ExercisePlanItemInline]
