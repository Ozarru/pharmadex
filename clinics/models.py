from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from pharmadex.tenant import TenantManager
from base.models import PharmacyModel


class ClinicalService(PharmacyModel):
    """
    Catalog of clinical services offered by the pharmacy/clinic.
    """

    objects = TenantManager()

    SERVICE_TYPE_CHOICES = [
        ("consultation", _("Consultation")),
        ("injection", _("Injection")),
        ("procedure", _("Procedure")),
        ("minor_surgery", _("Minor Surgery (e.g. Suturing)")),
        ("test", _("Diagnostic Test")),
        ("nursing", _("Nursing Care")),
        ("follow_up", _("Follow Up")),
        ("other", _("Other")),
    ]

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name")
    )

    code = models.CharField(
        max_length=50,
        verbose_name=_("Code")
    )

    service_type = models.CharField(
        max_length=30,
        choices=SERVICE_TYPE_CHOICES,
        default="other",
        verbose_name=_("Service Type")
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Unit Price")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )

    model_icon = "fa-solid fa-stethoscope"

    class Meta:
        verbose_name = _("Clinical Service")
        verbose_name_plural = _("Clinical Services")
        ordering = ("name",)

    def __str__(self):
        return self.name


class ClinicalEncounter(PharmacyModel):
    """
    Represents a patient clinical visit/session.
    """

    objects = TenantManager()

    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("in_progress", _("In Progress")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
    ]

    encounter_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Encounter Number")
    )

    patient = models.ForeignKey(
        "organizations.Customer",
        on_delete=models.PROTECT,
        related_name="clinical_encounters",
        verbose_name=_("Patient")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name=_("Status")
    )

    chief_complaint = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Chief Complaint")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Clinical Notes")
    )

    encounter_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Encounter Date")
    )

    model_icon = "fa-solid fa-user-doctor"

    class Meta:
        verbose_name = _("Clinical Encounter")
        verbose_name_plural = _("Clinical Encounters")
        ordering = ("-encounter_date",)

    def __str__(self):
        return self.encounter_number


class PatientVital(PharmacyModel):
    """
    Patient vital signs recorded during encounter.
    """

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="patient_vitals",
        verbose_name=_("Clinical Encounter")
    )

    temperature = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
        verbose_name=_("Temperature (°C)")
    )

    systolic_bp = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Systolic Blood Pressure")
    )

    diastolic_bp = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Diastolic Blood Pressure")
    )

    pulse_rate = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Pulse Rate")
    )

    respiratory_rate = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Respiratory Rate")
    )

    oxygen_saturation = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Oxygen Saturation (%)")
    )

    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Weight (kg)")
    )

    height = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Height (cm)")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Recorded At")
    )

    model_icon = "fa-solid fa-heart-pulse"

    class Meta:
        verbose_name = _("Vital")
        verbose_name_plural = _("Vitals")
        ordering = ("-recorded_at",)

    def __str__(self):
        return f"{self.encounter} - Vitals"


class Injection(PharmacyModel):
    """
    Records administered injections.
    """

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="injections",
        verbose_name=_("Clinical Encounter")
    )

    product = models.ForeignKey(
        "pharmacies.Product",
        on_delete=models.PROTECT,
        related_name="injections",
        verbose_name=_("Medication")
    )

    dosage = models.CharField(
        max_length=255,
        verbose_name=_("Dosage")
    )

    route = models.CharField(
        max_length=100,
        verbose_name=_("Administration Route")
    )

    site = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Injection Site")
    )

    administered_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Administered At")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-syringe"

    class Meta:
        verbose_name = _("Injection")
        verbose_name_plural = _("Injections")
        ordering = ("-administered_at",)

    def __str__(self):
        return f"{self.product}"


class NursingNote(PharmacyModel):
    """
    Nursing observations and notes.
    """

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="nursing_notes",
        verbose_name=_("Clinical Encounter")
    )

    note = models.TextField(
        verbose_name=_("Note")
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Recorded At")
    )

    model_icon = "fa-solid fa-notes-medical"

    class Meta:
        verbose_name = _("Nursing Note")
        verbose_name_plural = _("Nursing Notes")
        ordering = ("-recorded_at",)

    def __str__(self):
        return f"Nursing Note #{self.id}"


class Procedure(PharmacyModel):
    """
    Clinical procedures performed during encounter.
    """

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="procedures",
        verbose_name=_("Clinical Encounter")
    )

    service = models.ForeignKey(
        "ClinicalService",
        on_delete=models.PROTECT,
        related_name="procedures",
        verbose_name=_("Clinical Service")
    )

    procedure_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Procedure Date")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Procedure Notes")
    )

    model_icon = "fa-solid fa-scissors"

    class Meta:
        verbose_name = _("Procedure")
        verbose_name_plural = _("Procedures")
        ordering = ("-procedure_date",)

    def __str__(self):
        return f"{self.service}"


class Diagnosis(PharmacyModel):
    """
    Patient diagnosis during encounter.
    """

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="diagnoses",
        verbose_name=_("Clinical Encounter")
    )

    diagnosis = models.CharField(
        max_length=255,
        verbose_name=_("Diagnosis")
    )

    icd_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("ICD Code")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    diagnosed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Diagnosed At")
    )

    model_icon = "fa-solid fa-disease"

    class Meta:
        verbose_name = _("Diagnosis")
        verbose_name_plural = _("Diagnoses")
        ordering = ("-diagnosed_at",)

    def __str__(self):
        return self.diagnosis


class FollowUp(PharmacyModel):
    """
    Follow-up appointments or reviews.
    """

    STATUS_CHOICES = [
        ("scheduled", _("Scheduled")),
        ("completed", _("Completed")),
        ("missed", _("Missed")),
        ("cancelled", _("Cancelled")),
    ]

    encounter = models.ForeignKey(
        "ClinicalEncounter",
        on_delete=models.CASCADE,
        related_name="follow_ups",
        verbose_name=_("Clinical Encounter")
    )

    follow_up_date = models.DateTimeField(
        verbose_name=_("Follow Up Date")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
        verbose_name=_("Status")
    )

    reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Reason")
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    model_icon = "fa-solid fa-calendar-check"

    class Meta:
        verbose_name = _("Follow Up")
        verbose_name_plural = _("Follow Ups")
        ordering = ("-follow_up_date",)

    def __str__(self):
        return f"Follow Up - {self.encounter}"