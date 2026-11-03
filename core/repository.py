"""Persistence boundary. ORM queries and transaction locking live here."""
from django.db import transaction
from django.db.models import Q, F
from .models import User, Case, Hearing, Representation, Judgment, AuditEvent, HearingChange, LoginThrottle

atomic = transaction.atomic

def visible_cases(user):
    qs = Case.objects.select_related('judge','registrar')
    if not user.is_active:
        return qs.none()
    if user.role == User.Role.JUDGE:
        return qs.filter(judge=user)
    if user.role == User.Role.LAWYER:
        return qs.filter(lawyers=user)
    return qs if user.role == User.Role.REGISTRAR else qs.none()

def lock_case(pk):
    return Case.objects.select_for_update().get(pk=pk)

def lock_users(ids):
    return {u.pk: u for u in User.objects.select_for_update().filter(pk__in=ids).order_by('pk')}

def people(role=None, active=True):
    qs = User.objects.order_by('name')
    if role:
        qs = qs.filter(role=role)
    if active is not None:
        qs = qs.filter(is_active=active)
    return qs

def create_case(**data):
    return Case.objects.create(**data)

def set_lawyers(case, lawyers, actor):
    Representation.objects.filter(case=case).exclude(lawyer__in=lawyers).delete()
    for lawyer in lawyers:
        Representation.objects.get_or_create(case=case,lawyer=lawyer,defaults={'assigned_by':actor})

def booked(case=None, judge=None):
    qs = Hearing.objects.filter(status__in=['SCHEDULED','RESCHEDULED'])
    if case is not None: qs = qs.filter(case=case)
    if judge is not None: qs = qs.filter(judge=judge)
    return qs

def audit(actor, action, detail, case=None):
    return AuditEvent.objects.create(actor=actor,action=action,detail=detail,case=case)

def history(hearing, actor, old_status, old_time, reason):
    return HearingChange.objects.create(hearing=hearing,actor=actor,old_status=old_status,
        old_time=old_time,new_status=hearing.status,new_time=hearing.starts_at,reason=reason)

def create_hearing(**data):
    return Hearing.objects.create(**data)

def create_judgment(**data):
    return Judgment.objects.create(**data)

def create_user(**data):
    return User.objects.create_user(**data)

def throttle_attempt(key, now):
    from datetime import timedelta
    row, _ = LoginThrottle.objects.get_or_create(key=key, defaults={'expires_at':now+timedelta(minutes=15)})
    LoginThrottle.objects.filter(key=key,expires_at__lte=now).update(attempts=0,expires_at=now+timedelta(minutes=15))
    LoginThrottle.objects.filter(key=key).update(attempts=F('attempts')+1)
    row.refresh_from_db()
    return row.attempts
