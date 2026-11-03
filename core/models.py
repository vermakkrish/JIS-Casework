import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone

class User(AbstractUser):
    class Role(models.TextChoices):
        REGISTRAR = 'REGISTRAR', 'Registrar'
        JUDGE = 'JUDGE', 'Judge'
        LAWYER = 'LAWYER', 'Lawyer'
    role = models.CharField(max_length=12, choices=Role.choices)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(role__in=['REGISTRAR','JUDGE','LAWYER']), name='valid_user_role')]
    def __str__(self):
        return self.name

class Case(models.Model):
    class Status(models.TextChoices):
        REGISTERED = 'REGISTERED', 'Registered'
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        CLOSED = 'CLOSED', 'Closed'
    class Kind(models.TextChoices):
        CIVIL = 'CIVIL', 'Civil'
        CRIMINAL = 'CRIMINAL', 'Criminal'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cin = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    claimant = models.CharField(max_length=120)
    respondent = models.CharField(max_length=120)
    description = models.TextField(max_length=5000)
    filed_on = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REGISTERED, db_index=True)
    judge = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assigned_cases')
    registrar = models.ForeignKey(User, on_delete=models.PROTECT, related_name='registered_cases')
    lawyers = models.ManyToManyField(User, through='Representation', through_fields=('case','lawyer'), related_name='represented_cases')
    created_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['judge','status']), models.Index(fields=['filed_on'])]
        constraints = [models.CheckConstraint(condition=Q(kind__in=['CIVIL','CRIMINAL']), name='valid_case_kind'),
            models.CheckConstraint(condition=Q(status__in=['REGISTERED','PENDING','IN_PROGRESS','CLOSED']),name='valid_case_status'),
            models.CheckConstraint(condition=(Q(status='CLOSED',closed_at__isnull=False)|(~Q(status='CLOSED')&Q(closed_at__isnull=True))),name='closure_timestamp')]

class Representation(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='representations')
    lawyer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='representations')
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    assigned_at = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['case','lawyer'],name='unique_representation')]

class Hearing(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        RESCHEDULED = 'RESCHEDULED', 'Rescheduled'
        ADJOURNED = 'ADJOURNED', 'Adjourned'
        COMPLETED = 'COMPLETED', 'Completed'
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name='hearings')
    judge = models.ForeignKey(User, on_delete=models.PROTECT, related_name='hearings')
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    summary = models.TextField(max_length=10000, blank=True)
    summary_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['created_at','pk']
        constraints = [models.UniqueConstraint(fields=['judge','starts_at'],condition=Q(status__in=['SCHEDULED','RESCHEDULED']),name='unique_judge_slot'),
            models.UniqueConstraint(fields=['case'],condition=Q(status__in=['SCHEDULED','RESCHEDULED']),name='one_booked_hearing_per_case'),
            models.CheckConstraint(condition=Q(status__in=['SCHEDULED','RESCHEDULED','ADJOURNED','COMPLETED']),name='valid_hearing_status'),
            models.CheckConstraint(condition=(Q(status='ADJOURNED',starts_at__isnull=True)|(~Q(status='ADJOURNED')&Q(starts_at__isnull=False))),name='valid_hearing_time'),
            models.CheckConstraint(condition=(Q(status='COMPLETED',completed_at__isnull=False,summary_by__isnull=False)&~Q(summary=''))|(~Q(status='COMPLETED')&Q(completed_at__isnull=True,summary_by__isnull=True,summary='')),name='valid_hearing_summary')]

class HearingChange(models.Model):
    hearing = models.ForeignKey(Hearing, on_delete=models.PROTECT, related_name='changes')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    old_status = models.CharField(max_length=16, blank=True)
    new_status = models.CharField(max_length=16)
    old_time = models.DateTimeField(null=True)
    new_time = models.DateTimeField(null=True)
    reason = models.TextField(max_length=1000)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ['created_at','pk']

class Judgment(models.Model):
    case = models.OneToOneField(Case, on_delete=models.PROTECT, related_name='judgment')
    judge = models.ForeignKey(User, on_delete=models.PROTECT)
    verdict = models.CharField(max_length=200)
    summary = models.TextField(max_length=10000)
    created_at = models.DateTimeField(default=timezone.now)

class AuditEvent(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, null=True, related_name='events')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    detail = models.TextField(max_length=3000)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-created_at','-pk']

class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
