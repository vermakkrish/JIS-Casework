"""Application rules. Every consequential write is authorized and atomic."""
import hashlib
import secrets
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from . import repository as repo
from .models import User, Case, Hearing

IST = ZoneInfo('Asia/Kolkata')

def require(user, role):
    if not user.is_authenticated or not user.is_active or user.role != role:
        raise PermissionDenied('This action is not available to your role.')

def active_users(actor, ids=()):
    users = repo.lock_users([actor.pk,*ids])
    if actor.pk not in users or not users[actor.pk].is_active:
        raise PermissionDenied('Your access has been deactivated.')
    return users

def opened(case, version):
    if case.status == Case.Status.CLOSED:
        raise ValidationError('This case is closed. Its record can no longer be changed.')
    if case.version != version:
        raise ValidationError('This case changed while you were working. Reload the page and try again.')

def assignment_people(users, judge_id, lawyer_ids):
    judge = users.get(judge_id)
    if not judge or not judge.is_active or judge.role != User.Role.JUDGE:
        raise ValidationError('Choose an active Judge.')
    lawyers = [users.get(pk) for pk in lawyer_ids]
    if not lawyers or any(not u or not u.is_active or u.role != User.Role.LAWYER for u in lawyers):
        raise ValidationError('Choose at least one active Lawyer.')
    return judge, lawyers

def get_case(user, pk):
    try:
        return repo.visible_cases(user).get(pk=pk)
    except Case.DoesNotExist:
        raise Http404('Case not found or not available to your account.')

def search(user, data):
    qs = repo.visible_cases(user)
    q = data.get('q','').strip()[:180]
    if q:
        qs = qs.filter(Q(cin__icontains=q)|Q(title__icontains=q)|Q(claimant__icontains=q)|Q(respondent__icontains=q))
    if data.get('status')=='OPEN': qs = qs.exclude(status='CLOSED')
    elif data.get('status'): qs = qs.filter(status=data['status'])
    if data.get('kind'): qs = qs.filter(kind=data['kind'])
    if data.get('from_date'): qs = qs.filter(filed_on__gte=data['from_date'])
    if data.get('to_date'): qs = qs.filter(filed_on__lte=data['to_date'])
    return qs

def case_options():
    return repo.people(User.Role.JUDGE), repo.people(User.Role.LAWYER)

def clean_text(value, label, low, high):
    if not isinstance(value,str) or not low <= len(value.strip()) <= high:
        raise ValidationError(f'{label} must contain {low}–{high} characters.')
    return value.strip()

def register_case(actor, data):
    require(actor, User.Role.REGISTRAR)
    values = {k:clean_text(data[k],k.replace('_',' ').title(),2 if k!='description' else 10,n)
              for k,n in [('title',180),('claimant',120),('respondent',120),('description',5000)]}
    if data['kind'] not in Case.Kind.values or data['filed_on'] > timezone.localdate():
        raise ValidationError('Choose a valid case type and a filing date no later than today.')
    for attempt in range(5):
        try:
            with repo.atomic():
                ids = [u.pk for u in data['lawyers']]
                users = active_users(actor,[data['judge'].pk,*ids])
                judge,lawyers = assignment_people(users,data['judge'].pk,ids)
                case = repo.create_case(**values,kind=data['kind'],filed_on=data['filed_on'],judge=judge,
                    registrar=actor,cin=f'JIS-{timezone.localdate().year}-{secrets.token_hex(6).upper()}')
                repo.set_lawyers(case,lawyers,actor)
                repo.audit(actor,'Case registered',f'{case.cin} registered; Judge {judge.name}; Lawyers: '+', '.join(u.name for u in lawyers),case)
                return case
        except IntegrityError:
            if attempt == 4: raise ValidationError('Unable to allocate a case number. Please try again.')

def slot(value):
    if not value or timezone.is_naive(value):
        raise ValidationError('Choose a hearing date and time in Asia/Kolkata.')
    local = value.astimezone(IST)
    if local <= timezone.now() or local.weekday()>4 or local.hour not in range(9,17) or local.minute or local.second:
        raise ValidationError('Choose a future weekday slot, on the hour from 09:00 to 16:00 IST.')
    return local

def slots_for(case, day, exclude=None):
    occupied = repo.booked(judge=case.judge).exclude(pk=exclude).filter(starts_at__date=day)
    busy = {h.starts_at.astimezone(IST).hour for h in occupied}
    return [{'value':f'{hour:02}:00','label':f'{hour:02}:00–{hour+1:02}:00',
             'available':day.weekday()<5 and hour not in busy and datetime.combine(day,time(hour),IST)>timezone.now()} for hour in range(9,17)]

def bump(case):
    case.version += 1
    case.save()

def schedule(actor, pk, version, starts_at):
    require(actor,User.Role.REGISTRAR)
    starts_at=slot(starts_at)
    try:
        with repo.atomic():
            case=repo.lock_case(pk); opened(case,version)
            users=active_users(actor,[case.judge_id])
            if not users[case.judge_id].is_active: raise ValidationError('Assign an active Judge first.')
            if repo.booked(case=case).exists(): raise ValidationError('This case already has a booked hearing. Change that hearing instead.')
            hearing=repo.create_hearing(case=case,judge=case.judge,starts_at=starts_at)
            repo.history(hearing,actor,'',None,'Initial schedule')
            if case.status==Case.Status.REGISTERED: case.status=Case.Status.PENDING
            bump(case)
            repo.audit(actor,'Hearing scheduled',f'Hearing #{hearing.pk} · {starts_at:%d %b %Y, %H:%M} IST',case)
            return hearing
    except IntegrityError:
        raise ValidationError('That Judge or case already has a booking for this slot. Choose another time.')

def change_hearing(actor,pk,hearing_id,version,action,reason,starts_at=None):
    require(actor,User.Role.REGISTRAR)
    reason=clean_text(reason,'Reason',5,1000)
    if action not in ['reschedule','adjourn']: raise ValidationError('Unknown hearing action.')
    if action=='reschedule': starts_at=slot(starts_at)
    try:
        with repo.atomic():
            case=repo.lock_case(pk); opened(case,version)
            users=active_users(actor,[case.judge_id])
            h=case.hearings.get(pk=hearing_id)
            if h.status==Hearing.Status.COMPLETED or (action=='adjourn' and h.status==Hearing.Status.ADJOURNED):
                raise ValidationError('This hearing cannot make that transition.')
            if action=='reschedule' and not users[case.judge_id].is_active:
                raise ValidationError('Assign an active Judge first.')
            old_status,old_time=h.status,h.starts_at
            if action=='reschedule' and starts_at==old_time: raise ValidationError('Choose a different slot.')
            h.status=Hearing.Status.RESCHEDULED if action=='reschedule' else Hearing.Status.ADJOURNED
            h.starts_at=starts_at if action=='reschedule' else None
            h.judge=case.judge; h.save()
            repo.history(h,actor,old_status,old_time,reason); bump(case)
            repo.audit(actor,'Hearing '+('rescheduled' if action=='reschedule' else 'adjourned'),f'Hearing #{h.pk} · {reason}',case)
            return h
    except IntegrityError:
        raise ValidationError('That Judge or case already has a booked hearing. Choose another slot or adjourn it first.')

def record_summary(actor,pk,hearing_id,version,summary):
    require(actor,User.Role.JUDGE)
    summary=clean_text(summary,'Hearing summary',10,10000)
    with repo.atomic():
        case=repo.lock_case(pk); opened(case,version); active_users(actor)
        if case.judge_id!=actor.pk: raise PermissionDenied
        h=case.hearings.get(pk=hearing_id)
        if h.status not in [Hearing.Status.SCHEDULED,Hearing.Status.RESCHEDULED] or h.starts_at>timezone.now():
            raise ValidationError('Only a booked hearing whose start time has passed can be completed.')
        old_status,old_time=h.status,h.starts_at
        h.status=Hearing.Status.COMPLETED; h.summary=summary; h.summary_by=actor; h.completed_at=timezone.now(); h.save()
        repo.history(h,actor,old_status,old_time,'Hearing completed and summary recorded')
        case.status=Case.Status.IN_PROGRESS; bump(case)
        repo.audit(actor,'Hearing completed',f'Hearing #{h.pk} · summary recorded by {actor.name}',case)
        return h

def record_judgment(actor,pk,version,verdict,summary):
    require(actor,User.Role.JUDGE)
    verdict=clean_text(verdict,'Verdict',3,200); summary=clean_text(summary,'Judgment summary',10,10000)
    with repo.atomic():
        case=repo.lock_case(pk); opened(case,version); active_users(actor)
        if case.judge_id!=actor.pk: raise PermissionDenied
        if repo.booked(case=case).exists(): raise ValidationError('Complete or adjourn every booked hearing before closing this case.')
        judgment=repo.create_judgment(case=case,judge=actor,verdict=verdict,summary=summary)
        # The DB trigger closes the case as part of this very INSERT, including outside this service.
        case.refresh_from_db()
        repo.audit(actor,'Judgment recorded · case closed',verdict,case)
        return judgment

def update_assignments(actor,pk,version,judge,lawyers,reason):
    require(actor,User.Role.REGISTRAR); reason=clean_text(reason,'Reason',5,1000)
    try:
        with repo.atomic():
            case=repo.lock_case(pk); opened(case,version)
            ids=[u.pk for u in lawyers]
            users=active_users(actor,[case.judge_id,judge.pk,*ids])
            judge,lawyers=assignment_people(users,judge.pk,ids)
            old=f'Judge {case.judge.name}; Lawyers: '+', '.join(case.lawyers.values_list('name',flat=True))
            for h in repo.booked(case=case):
                h.judge=judge; h.save()
            case.judge=judge
            repo.set_lawyers(case,lawyers,actor); bump(case)
            repo.audit(actor,'Assignments updated',old+' → Judge '+judge.name+'; Lawyers: '+', '.join(u.name for u in lawyers)+'. Reason: '+reason,case)
    except IntegrityError:
        raise ValidationError('The new Judge has a conflicting hearing. Reschedule or adjourn this case’s booking first.')

def create_account(actor,data):
    require(actor,User.Role.REGISTRAR)
    if data['role'] not in [User.Role.JUDGE,User.Role.LAWYER]: raise PermissionDenied
    email=data['email'].strip().lower()
    user=User(username=email,email=email,name=data['name'],role=data['role'])
    validate_password(data['password'],user)
    try:
        with repo.atomic():
            active_users(actor)
            u=repo.create_user(username=email,email=email,name=clean_text(data['name'],'Name',2,100),role=data['role'],password=data['password'])
            repo.audit(actor,'Account created',f'{u.name} · {u.get_role_display()} · {u.email}')
            return u
    except IntegrityError:
        raise ValidationError('An account with this email already exists, including inactive accounts.')

def deactivate(actor,pk,reason):
    require(actor,User.Role.REGISTRAR); reason=clean_text(reason,'Reason',5,1000)
    with repo.atomic():
        users=active_users(actor,[pk]); user=users.get(pk)
        if not user or user.role==User.Role.REGISTRAR: raise PermissionDenied
        if not user.is_active: raise ValidationError('This account is already inactive.')
        if user.role==User.Role.JUDGE and user.assigned_cases.exclude(status=Case.Status.CLOSED).exists():
            raise ValidationError('Reassign this Judge’s open cases before deactivating the account.')
        user.is_active=False; user.save(update_fields=['is_active'])
        repo.audit(actor,'Account deactivated',f'{user.name} · {user.email} · {reason}')

def allow_login(email,ip):
    now=timezone.now()
    limits=[('email:'+email.lower(),10),('ip:'+ip,50)]
    with repo.atomic():
        counts=[(repo.throttle_attempt(hashlib.sha256(key.encode()).hexdigest(),now),limit) for key,limit in limits]
    return all(count<=limit for count,limit in counts)

def dashboard(user):
    qs=repo.visible_cases(user)
    return {'total':qs.count(),'open_count':qs.exclude(status='CLOSED').count(),'closed_count':qs.filter(status='CLOSED').count(),
        'upcoming':Hearing.objects.filter(case__in=qs,status__in=['SCHEDULED','RESCHEDULED'],starts_at__gte=timezone.now()).select_related('case','judge').order_by('starts_at')[:6],
        'recent_cases':qs[:5],'events':repo.AuditEvent.objects.filter(case__in=qs).select_related('case','actor')[:6],
        'awaiting':Hearing.objects.filter(case__in=qs,status__in=['SCHEDULED','RESCHEDULED'],starts_at__lte=timezone.now()).select_related('case')[:6]}

def agenda(user,day):
    return Hearing.objects.filter(case__in=repo.visible_cases(user),starts_at__date=day).select_related('case','judge').order_by('starts_at')

def accounts(user):
    require(user,User.Role.REGISTRAR)
    return repo.people(active=None),repo.AuditEvent.objects.filter(case__isnull=True).select_related('actor')[:12]
