import json,platform,statistics,time
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction,connection
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone
from core.models import User,Case,Representation

class Command(BaseCommand):
    help='Measure authorized HTTP-view search latency with 5000 synthetic cases; inserts are rolled back.'
    def add_arguments(self,parser): parser.add_argument('--output',default='docs/evidence/search-performance.json')
    def handle(self,*args,**options):
        roles={r:User.objects.filter(role=r,is_active=True).first() for r in ['REGISTRAR','JUDGE','LAWYER']}
        if not all(roles.values()): raise CommandError('Seed demonstration accounts first.')
        samples={}
        # Temporary fixtures and sessions are rolled back; original records are untouched.
        with transaction.atomic(),override_settings(ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False):
            r,j,l=[roles[k] for k in ['REGISTRAR','JUDGE','LAWYER']]
            rows=[Case(cin=f'BENCH-{i:08}',title=f'Benchmark fictional matter {i:05}',kind='CIVIL',claimant='Synthetic Willow',respondent='Synthetic Cedar',description='Temporary fictional benchmark record.',filed_on=timezone.localdate(),judge=j,registrar=r) for i in range(5000)]
            Case.objects.bulk_create(rows,batch_size=500)
            Representation.objects.bulk_create([Representation(case=c,lawyer=l,assigned_by=r) for c in rows],batch_size=500)
            count=Case.objects.count()
            for role,user in roles.items():
                client=Client();client.force_login(user)
                timings=[]
                for n in range(55):
                    started=time.perf_counter()
                    response=client.get('/cases/',{'q':['Benchmark','matter 000','BENCH-00000099','no-such-record'][n%4]})
                    if response.status_code!=200: raise CommandError('Search request failed during measurement.')
                    if n>=5: timings.append((time.perf_counter()-started)*1000)
                ordered=sorted(timings)
                samples[role]={'requests':len(timings),'p50_ms':round(statistics.median(timings),2),'p95_ms':round(ordered[int(len(ordered)*.95)-1],2),'max_ms':round(max(timings),2),'under_2s':all(x<2000 for x in timings)}
            transaction.set_rollback(True)
        result={'timestamp':timezone.now().isoformat(),'os':platform.platform(),'python':platform.python_version(),'database':connection.vendor,'dataset_cases':count,'synthetic_cases':5000,'conditions':'Django test HTTP client through views, auth, ORM, template rendering and pagination; local database; 5 warmups + 50 serial requests per role; four text queries; no browser/network/TLS latency; fixture transaction rolled back.','results':samples}
        path=Path(options['output']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
        self.stdout.write(json.dumps(result,indent=2))
