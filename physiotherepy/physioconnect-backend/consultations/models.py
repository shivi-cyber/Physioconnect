from django.db import models


class ConsultationNote(models.Model):
    """SOAP-format notes, one per appointment."""
    appointment = models.OneToOneField('appointments.Appointment', on_delete=models.CASCADE, related_name='consultation_note')
    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.PROTECT)

    subjective = models.TextField(blank=True, help_text="Patient's own description of symptoms")
    objective = models.TextField(blank=True, help_text="Doctor's clinical observations/measurements")
    assessment = models.TextField(blank=True, help_text="Doctor's diagnosis/interpretation")
    plan = models.TextField(blank=True, help_text="Treatment plan going forward")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notes — {self.appointment}"


class ExerciseLibrary(models.Model):
    """Reusable catalog of exercises doctors can assign to patients."""
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    image = models.ImageField(upload_to='exercise_images/', null=True, blank=True)
    body_region = models.CharField(max_length=100, blank=True, help_text="e.g. 'lower back', 'knee', 'shoulder'")

    def __str__(self):
        return self.name


class ExercisePlan(models.Model):
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='exercise_plans')
    appointment = models.ForeignKey(
        'appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exercise_plans',
        help_text="Nullable — a plan can be updated outside a specific visit."
    )
    created_by = models.ForeignKey('doctors.Doctor', on_delete=models.PROTECT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Exercise plan for {self.patient} ({self.created_at.date()})"


class ExercisePlanItem(models.Model):
    exercise_plan = models.ForeignKey(ExercisePlan, on_delete=models.CASCADE, related_name='items')
    exercise = models.ForeignKey(ExerciseLibrary, on_delete=models.PROTECT)
    sets = models.PositiveIntegerField(default=3)
    reps = models.PositiveIntegerField(default=10)
    frequency_per_week = models.PositiveIntegerField(default=3)
    custom_instructions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.exercise} — {self.sets}x{self.reps}, {self.frequency_per_week}/wk"
