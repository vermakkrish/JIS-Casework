import os
from datetime import datetime,time,timedelta
from django.core.management.base import BaseCommand,CommandError
from django.core import management
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from core.models import User,Case,Hearing
from core import services as s

class Command(BaseCommand):
    help='Seed fictional data into an empty demo database. Never runs automatically in production.'
    def add_arguments(self,parser):
        parser.add_argument('--reset',action='store_true')
        parser.add_argument('--confirm-fictional-reset',action='store_true')
    def handle(self,*args,**opts):
        if not settings.DEBUG and os.getenv('ALLOW_DEMO_SEED')!='1':
            raise CommandError('Set ALLOW_DEMO_SEED=1 only for a dedicated fictional demonstration database.')
        password=os.getenv('DEMO_PASSWORD')
        if not password: raise CommandError('Set DEMO_PASSWORD to a strong private password. It is never printed.')
        from django.contrib.auth.password_validation import validate_password
        validate_password(password)
        if opts['reset']:
            if not opts['confirm_fictional_reset']: raise CommandError('Reset requires --confirm-fictional-reset. This deletes all database records.')
            management.call_command('flush',interactive=False,verbosity=0)
        if User.objects.exists() or Case.objects.exists(): raise CommandError('Database is not empty. Refusing to overwrite records; use a separate demo database.')
        with transaction.atomic():
            users={}
            for role,name,prefix in [('REGISTRAR','Avery Sen','registrar'),('JUDGE','Mira Dev','judge'),('LAWYER','Rohan Vale','lawyer'),('JUDGE','Ishan Reed','judge.two'),('LAWYER','Leela Moss','lawyer.two')]:
                users[prefix]=User.objects.create_user(username=f'{prefix}@jis.example.test',email=f'{prefix}@jis.example.test',name=name,role=role,password=password)
            r,j,l=users['registrar'],users['judge'],users['lawyer']
            titles=[('Willow Studio v. Cedar Works','CIVIL','Willow Studio','Cedar Works'),('Maple Collective v. Northlight Co.','CIVIL','Maple Collective','Northlight Co.'),('Riverbend Workshop matter','CRIMINAL','Riverbend Workshop','Fictional Participant A'),('Orchid House v. Elm Atelier','CIVIL','Orchid House','Elm Atelier'),('Harbor Lane demonstration matter','CRIMINAL','Harbor Lane Association','Fictional Participant B'),('Juniper Press v. Acorn Design','CIVIL','Juniper Press','Acorn Design')]
            cases=[]
            for n,(title,kind,claimant,respondent) in enumerate(titles):
                cases.append(s.register_case(r,{'title':title,'kind':kind,'claimant':claimant,'respondent':respondent,'description':'Fictional academic case concerning a disagreement between invented parties. The record demonstrates scheduling and record management only; no legal conclusion is implied.','filed_on':timezone.localdate()-timedelta(days=15-n),'judge':j if n<5 else users['judge.two'],'lawyers':[l] if n<5 else [users['lawyer.two']]}))
            tomorrow=timezone.localdate()+timedelta(days=1)
            while tomorrow.weekday()>4: tomorrow+=timedelta(days=1)
            for n in [0,1,2]:
                c=cases[n]; s.schedule(r,c.pk,c.version,datetime.combine(tomorrow,time(9+n),s.IST))
            # An explicitly historical seed fixture permits an immediate Judge demonstration.
            c=cases[3]
            past=timezone.localdate()-timedelta(days=1)
            while past.weekday()>4: past-=timedelta(days=1)
            h=Hearing.objects.create(case=c,judge=j,starts_at=datetime.combine(past,time(10),s.IST))
            s.repo.history(h,r,'',None,'Historical fictional hearing fixture for evaluation')
            c.status='PENDING'; c.save()
            s.repo.audit(r,'Hearing scheduled','Historical demonstration slot; ready for a Judge summary.',c)
            c=cases[4]; s.record_judgment(j,c.pk,c.version,'Demonstration matter resolved','The fictional parties reached the recorded demonstration outcome. This text illustrates a final record only, without legal authority.')
        self.stdout.write(self.style.SUCCESS('Seeded 5 fictional accounts and 6 cases. Account emails are documented in the user guide. Password was supplied privately.'))
