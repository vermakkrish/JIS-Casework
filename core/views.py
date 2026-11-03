from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from . import services as svc
from . import forms
from .models import User, Hearing

def sign_in(request):
    if request.user.is_authenticated: return redirect('dashboard')
    form=forms.LoginForm(request,data=request.POST or None)
    throttled=False
    if request.method=='POST':
        throttled=not svc.allow_login(request.POST.get('username','')[:254],request.META.get('REMOTE_ADDR','unknown'))
        if throttled:
            form=forms.LoginForm(request)
        elif form.is_valid():
            login(request,form.get_user()); return redirect('dashboard')
    return render(request,'login.html',{'form':form,'throttled':throttled},status=429 if throttled else 200)

@require_POST
def sign_out(request):
    logout(request); return redirect('login')

@login_required
def dashboard(request):
    return render(request,'dashboard.html',{'active':'dashboard',**svc.dashboard(request.user)})

@login_required
def cases(request):
    form=forms.SearchForm(request.GET)
    valid=form.is_valid()
    qs=svc.search(request.user,form.cleaned_data if valid else {})
    if not valid: qs=qs.none()
    page=Paginator(qs,15).get_page(request.GET.get('page'))
    params=request.GET.copy(); params.pop('page',None)
    return render(request,'cases.html',{'active':'cases','form':form,'page':page,'query':params.urlencode()})

@login_required
def case_detail(request,pk):
    case=svc.get_case(request.user,pk)
    hearings=case.hearings.select_related('judge','summary_by').prefetch_related('changes__actor')
    return render(request,'case_detail.html',{'active':'cases','case':case,'hearings':hearings,'now':timezone.now(),
        'events':case.events.select_related('actor'),'lawyers':case.lawyers.all(),
        'booked':any(h.status in ['SCHEDULED','RESCHEDULED'] for h in hearings)})

def form_page(request,form,title,subtitle,button,back,**extra):
    return render(request,'form.html',{'form':form,'title':title,'subtitle':subtitle,'button':button,'back':back,**extra},status=422 if request.method=='POST' and form.errors else 200)

@login_required
def case_new(request):
    svc.require(request.user,User.Role.REGISTRAR)
    judges,lawyers=svc.case_options()
    form=forms.CaseForm(request.POST or None,judges=judges,lawyers=lawyers,initial={'filed_on':timezone.localdate()})
    if request.method=='POST' and form.is_valid():
        try:
            case=svc.register_case(request.user,form.cleaned_data)
            messages.success(request,f'Case registered successfully · {case.cin}')
            return redirect('case_detail',pk=case.pk)
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,'Register a case','Create a clear record and assign the people responsible for it.','Register case',reverse('cases'),active='cases')

@login_required
def assignments(request,pk):
    svc.require(request.user,User.Role.REGISTRAR); case=svc.get_case(request.user,pk)
    judges,lawyers=svc.case_options()
    form=forms.AssignmentForm(request.POST or None,judges=judges,lawyers=lawyers,initial={'version':case.version,'judge':case.judge,'lawyers':case.lawyers.all()})
    if request.method=='POST' and form.is_valid():
        try:
            d=form.cleaned_data; svc.update_assignments(request.user,pk,d['version'],d['judge'],d['lawyers'],d['reason'])
            messages.success(request,'Assignments updated. The change is preserved in the case timeline.')
            return redirect('case_detail',pk=pk)
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,'Update assignments',case.title,'Save assignments',reverse('case_detail',args=[pk]),case=case,active='cases')

@login_required
def hearing_action(request,pk,action,hearing_id=None):
    svc.require(request.user,User.Role.JUDGE if action=='summary' else User.Role.REGISTRAR)
    case=svc.get_case(request.user,pk)
    h=None
    if hearing_id:
        try: h=case.hearings.get(pk=hearing_id)
        except Hearing.DoesNotExist: raise Http404
    specs={'schedule':(forms.ScheduleForm,'Schedule a hearing','Save hearing'),
           'reschedule':(forms.RescheduleForm,'Reschedule hearing','Confirm reschedule'),
           'adjourn':(forms.AdjournForm,'Adjourn hearing','Confirm adjournment'),
           'summary':(forms.SummaryForm,'Record hearing summary','Complete hearing')}
    if action not in specs: raise Http404
    cls,title,button=specs[action]
    form=cls(request.POST or None,initial={'version':case.version})
    if request.method=='POST' and form.is_valid():
        try:
            d=form.cleaned_data
            if action=='schedule': svc.schedule(request.user,pk,d['version'],d['starts_at'])
            elif action=='summary': svc.record_summary(request.user,pk,hearing_id,d['version'],d['summary'])
            else: svc.change_hearing(request.user,pk,hearing_id,d['version'],action,d['reason'],d.get('starts_at'))
            messages.success(request,{'schedule':'Hearing scheduled.','reschedule':'Hearing rescheduled. Previous schedule retained.','adjourn':'Hearing adjourned. The slot has been released.','summary':'Summary saved and hearing completed.'}[action])
            return redirect('case_detail',pk=pk)
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,title,case.title,button,reverse('case_detail',args=[pk]),case=case,hearing=h,active='agenda',
        slot_url=reverse('slots',args=[pk])+(f'?exclude={hearing_id}' if hearing_id else '') if action in ['schedule','reschedule'] else None)

@login_required
@require_GET
def slots(request,pk):
    svc.require(request.user,User.Role.REGISTRAR); case=svc.get_case(request.user,pk)
    form=forms.DayForm(request.GET)
    if not form.is_valid(): return JsonResponse({'error':'Choose a valid date.'},status=400)
    exclude=request.GET.get('exclude')
    if exclude and (not exclude.isdigit() or not case.hearings.filter(pk=exclude).exists()): raise Http404
    return JsonResponse({'slots':svc.slots_for(case,form.cleaned_data['day'],exclude)})

@login_required
def judgment(request,pk):
    svc.require(request.user,User.Role.JUDGE); case=svc.get_case(request.user,pk)
    form=forms.JudgmentForm(request.POST or None,initial={'version':case.version})
    if request.method=='POST' and form.is_valid():
        try:
            d=form.cleaned_data; svc.record_judgment(request.user,pk,d['version'],d['verdict'],d['summary'])
            messages.success(request,'Judgment recorded and case closed. The complete record remains available.')
            return redirect('case_detail',pk=pk)
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,'Record judgment & close case','This is a single, final action. Complete or adjourn all booked hearings first.','Record judgment & close',reverse('case_detail',args=[pk]),case=case,active='cases',consequential=True)

@login_required
def agenda(request):
    form=forms.DayForm(request.GET or None,initial={'day':timezone.localdate()})
    day=timezone.localdate()
    if form.is_bound and form.is_valid(): day=form.cleaned_data['day']
    hearings=svc.agenda(request.user,day) if not form.errors else []
    return render(request,'agenda.html',{'active':'agenda','form':form,'day':day,'hearings':hearings,'previous':day-timedelta(days=1),'next':day+timedelta(days=1)})

@login_required
def accounts(request):
    users,events=svc.accounts(request.user)
    return render(request,'accounts.html',{'active':'accounts','users':users,'events':events})

@login_required
def account_new(request):
    svc.require(request.user,User.Role.REGISTRAR)
    form=forms.AccountForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            u=svc.create_account(request.user,form.cleaned_data)
            messages.success(request,f'{u.get_role_display()} account created for {u.name}. Share the password securely.')
            return redirect('accounts')
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,'Create an account','Give a Judge or Lawyer access to their assigned work.','Create account',reverse('accounts'),active='accounts')

@login_required
def account_deactivate(request,pk):
    users,_=svc.accounts(request.user)
    try: user=users.get(pk=pk)
    except User.DoesNotExist: raise Http404
    form=forms.DeactivateForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            svc.deactivate(request.user,pk,form.cleaned_data['reason'])
            messages.success(request,f'Access removed for {user.name}. Historical records are preserved.')
            return redirect('accounts')
        except ValidationError as e: form.add_error(None,e)
    return form_page(request,form,'Deactivate account',f'{user.name} · {user.email}. Existing sessions lose access immediately.','Deactivate account',reverse('accounts'),active='accounts',consequential=True)

@login_required
def guide(request): return render(request,'guide.html',{'active':'guide'})

def health(request):
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT 1')
    except Exception: return JsonResponse({'status':'unavailable'},status=503)
    return JsonResponse({'status':'ok'})
