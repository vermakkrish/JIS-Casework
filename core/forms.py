from datetime import datetime
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Case, User
from .services import IST

class LoginForm(AuthenticationForm):
    username=forms.EmailField(label='Email address',widget=forms.EmailInput(attrs={'autocomplete':'username','placeholder':'you@example.test'}))
    password=forms.CharField(label='Password',strip=False,widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))
    def clean_username(self): return self.cleaned_data['username'].lower()

class CaseForm(forms.Form):
    title=forms.CharField(max_length=180,min_length=2,label='Case title',help_text='A short, descriptive title. Use fictional information only.')
    kind=forms.ChoiceField(choices=Case.Kind.choices,label='Case type')
    filed_on=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}),label='Filing date')
    claimant=forms.CharField(max_length=120,min_length=2,label='Claimant / initiating party')
    respondent=forms.CharField(max_length=120,min_length=2,label='Respondent / defendant')
    description=forms.CharField(min_length=10,max_length=5000,widget=forms.Textarea(attrs={'rows':4}),label='Case description',help_text='Summarize the matter and any relevant incident context. This is a record, not legal advice.')
    judge=forms.ModelChoiceField(queryset=User.objects.none(),label='Assigned Judge')
    lawyers=forms.ModelMultipleChoiceField(queryset=User.objects.none(),label='Representing Lawyers',widget=forms.CheckboxSelectMultiple,help_text='Only assigned Lawyers can view this case. Select at least one.')
    def __init__(self,*args,judges,lawyers,**kwargs):
        super().__init__(*args,**kwargs); self.fields['judge'].queryset=judges; self.fields['lawyers'].queryset=lawyers
    def clean_filed_on(self):
        value=self.cleaned_data['filed_on']
        if value>timezone.localdate(): raise ValidationError('Filing date cannot be in the future.')
        return value

class VersionForm(forms.Form):
    version=forms.IntegerField(min_value=1,widget=forms.HiddenInput)

class AssignmentForm(VersionForm):
    judge=forms.ModelChoiceField(queryset=User.objects.none(),label='Assigned Judge')
    lawyers=forms.ModelMultipleChoiceField(queryset=User.objects.none(),label='Representing Lawyers',widget=forms.CheckboxSelectMultiple)
    reason=forms.CharField(min_length=5,max_length=1000,widget=forms.Textarea(attrs={'rows':3}),help_text='The previous and new assignments will remain in the timeline.')
    def __init__(self,*args,judges,lawyers,**kwargs):
        super().__init__(*args,**kwargs); self.fields['judge'].queryset=judges; self.fields['lawyers'].queryset=lawyers

class ScheduleForm(VersionForm):
    day=forms.DateField(label='Hearing date',widget=forms.DateInput(attrs={'type':'date','data-slots-date':'true'}))
    hour=forms.ChoiceField(label='One-hour slot · Asia/Kolkata (IST)',choices=[(f'{h:02}:00',f'{h:02}:00–{h+1:02}:00') for h in range(9,17)],widget=forms.Select(attrs={'data-slots-hour':'true'}))
    def clean(self):
        d=super().clean()
        if d.get('day') and d.get('hour'):
            d['starts_at']=datetime.combine(d['day'],datetime.strptime(d['hour'],'%H:%M').time(),IST)
        return d

class RescheduleForm(ScheduleForm):
    reason=forms.CharField(min_length=5,max_length=1000,widget=forms.Textarea(attrs={'rows':3}),label='Reason for rescheduling')

class AdjournForm(VersionForm):
    reason=forms.CharField(min_length=5,max_length=1000,widget=forms.Textarea(attrs={'rows':3}),label='Reason for adjournment',help_text='This releases the current slot. The hearing can be rescheduled later while the case is open.')

class SummaryForm(VersionForm):
    summary=forms.CharField(min_length=10,max_length=10000,widget=forms.Textarea(attrs={'rows':8}),label='Hearing summary',help_text='Record the proceedings accurately. Saving completes this hearing; the summary cannot be edited afterward.')
    confirm=forms.BooleanField(label='I have reviewed this summary and am ready to complete the hearing.')

class JudgmentForm(VersionForm):
    verdict=forms.CharField(min_length=3,max_length=200,label='Verdict / disposition')
    summary=forms.CharField(min_length=10,max_length=10000,widget=forms.Textarea(attrs={'rows':8}),label='Judgment summary')
    confirm=forms.BooleanField(label='I confirm this judgment is final. Saving will close the case permanently.')

class AccountForm(forms.Form):
    name=forms.CharField(min_length=2,max_length=100,label='Full name')
    email=forms.EmailField(label='Email address',help_text='Used for sign-in. No email is sent by this application.')
    role=forms.ChoiceField(choices=[('JUDGE','Judge'),('LAWYER','Lawyer')])
    password=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),min_length=12,max_length=128,strip=False,help_text='At least 12 characters. Share securely with the account holder; ask them to change it after sign-in.')
    password_confirm=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),label='Confirm password',strip=False)
    def clean(self):
        d=super().clean()
        if d.get('password'):
            validate_password(d['password'],User(username=d.get('email',''),email=d.get('email',''),name=d.get('name','')))
            if d['password']!=d.get('password_confirm'): self.add_error('password_confirm','The passwords do not match.')
        return d

class DeactivateForm(forms.Form):
    reason=forms.CharField(min_length=5,max_length=1000,widget=forms.Textarea(attrs={'rows':3}))
    confirm=forms.BooleanField(label='Remove sign-in access now and preserve historical attribution.')

class SearchForm(forms.Form):
    q=forms.CharField(required=False,max_length=180,label='Search',widget=forms.TextInput(attrs={'placeholder':'CIN, case title or party name…','type':'search'}))
    status=forms.ChoiceField(required=False,choices=[('','All statuses'),('OPEN','All open cases'),*Case.Status.choices])
    kind=forms.ChoiceField(required=False,choices=[('','All types'),*Case.Kind.choices],label='Type')
    from_date=forms.DateField(required=False,label='Filed from',widget=forms.DateInput(attrs={'type':'date'}))
    to_date=forms.DateField(required=False,label='Filed through',widget=forms.DateInput(attrs={'type':'date'}))
    def clean(self):
        d=super().clean()
        if d.get('from_date') and d.get('to_date') and d['from_date']>d['to_date']:
            raise ValidationError('The start date must be on or before the end date.')
        return d

class DayForm(forms.Form):
    day=forms.DateField(label='Hearing date',widget=forms.DateInput(attrs={'type':'date'}))
