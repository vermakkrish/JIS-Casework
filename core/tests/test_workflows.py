from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,time,timedelta
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,Client
from django.db import IntegrityError,transaction,connection,connections,close_old_connections
from django.core.exceptions import ValidationError,PermissionDenied
from django.urls import reverse
from django.utils import timezone
from core.models import User,Case,Hearing,Judgment,AuditEvent,Representation
from core import services as s

PASSWORD='Testing-only-River-93!'

def users():
    return [User.objects.create_user(username=f'{name}@example.test',email=f'{name}@example.test',name=name.title(),role=role,password=PASSWORD)
        for name,role in [('reg','REGISTRAR'),('judge','JUDGE'),('lawyer','LAWYER'),('otherjudge','JUDGE'),('otherlawyer','LAWYER')]]

def data(judge,lawyer,title='Fictional Willow dispute'):
    return dict(title=title,kind='CIVIL',claimant='Willow Studio',respondent='Cedar Works',description='Entirely fictional demonstration matter.',filed_on=timezone.localdate(),judge=judge,lawyers=[lawyer])

def future(hour=9):
    day=timezone.localdate()+timedelta(days=7)
    while day.weekday()>4: day+=timedelta(days=1)
    return datetime.combine(day,time(hour),s.IST)

class Workflows(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.r,cls.j,cls.l,cls.j2,cls.l2=users()
    def setUp(self):
        self.c=s.register_case(self.r,data(self.j,self.l))
    def refresh(self): self.c.refresh_from_db(); return self.c.version
    def test_R1_case_registration_and_unique_cin(self):
        self.assertRegex(self.c.cin,r'^JIS-\d{4}-[0-9A-F]{12}$')
        self.assertEqual(self.c.lawyers.get(),self.l)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Case.objects.create(**{k:v for k,v in self.c.__dict__.items() if k not in ['_state','id']})
        self.assertEqual(AuditEvent.objects.filter(case=self.c,action='Case registered').count(),1)
    def test_R1_validation_and_unauthorized(self):
        d=data(self.j,self.l); d['title']=' '
        with self.assertRaises(ValidationError): s.register_case(self.r,d)
        with self.assertRaises(PermissionDenied): s.register_case(self.l,data(self.j,self.l))
        self.assertEqual(Case.objects.count(),1)
    def test_R2_schedule_conflict_and_relationship(self):
        h=s.schedule(self.r,self.c.pk,self.c.version,future())
        self.assertEqual(h.case_id,self.c.pk); self.refresh(); self.assertEqual(self.c.status,'PENDING')
        c2=s.register_case(self.r,data(self.j,self.l,'Second fictional case'))
        with self.assertRaises(ValidationError): s.schedule(self.r,c2.pk,c2.version,future())
        self.assertEqual(Hearing.objects.count(),1)
    def test_R2_bad_slot_and_future_summary(self):
        with self.assertRaises(ValidationError): s.schedule(self.r,self.c.pk,self.c.version,future().replace(minute=30))
        h=s.schedule(self.r,self.c.pk,self.c.version,future())
        with self.assertRaises(ValidationError): s.record_summary(self.j,self.c.pk,h.pk,self.refresh(),'A sufficiently long fictional summary.')
    def test_R3_reschedule_adjourn_history(self):
        h=s.schedule(self.r,self.c.pk,self.c.version,future())
        with self.assertRaises(ValidationError): s.change_hearing(self.r,self.c.pk,h.pk,self.refresh(),'reschedule','',future(10))
        s.change_hearing(self.r,self.c.pk,h.pk,self.refresh(),'reschedule','Participant unavailable',future(10))
        s.change_hearing(self.r,self.c.pk,h.pk,self.refresh(),'adjourn','Additional preparation required')
        h.refresh_from_db(); self.assertIsNone(h.starts_at); self.assertEqual(h.changes.count(),3)
        self.assertEqual(h.changes.last().old_time,future(10))
        s.change_hearing(self.r,self.c.pk,h.pk,self.refresh(),'reschedule','New date agreed',future(11))
        h.refresh_from_db(); self.assertEqual(h.status,'RESCHEDULED')
    def past_hearing(self):
        return Hearing.objects.create(case=self.c,judge=self.j,starts_at=timezone.now()-timedelta(days=1))
    def test_R4_summary_attribution_and_immutable(self):
        h=self.past_hearing()
        with self.assertRaises(PermissionDenied): s.record_summary(self.j2,self.c.pk,h.pk,self.c.version,'Other Judge cannot write this.')
        s.record_summary(self.j,self.c.pk,h.pk,self.c.version,'Fictional parties presented their positions.')
        h.refresh_from_db(); self.assertEqual(h.status,'COMPLETED'); self.assertEqual(h.summary_by,self.j)
        self.refresh(); self.assertEqual(self.c.status,'IN_PROGRESS')
        with self.assertRaises(ValidationError): s.record_summary(self.j,self.c.pk,h.pk,self.c.version,'Cannot replace a completed summary.')
    def test_R4_hearing_must_belong_to_case(self):
        h=self.past_hearing(); c2=s.register_case(self.r,data(self.j,self.l,'Another fictional case'))
        with self.assertRaises(Hearing.DoesNotExist): s.record_summary(self.j,c2.pk,h.pk,c2.version,'Should not change the wrong hearing.')
        h.refresh_from_db(); self.assertEqual(h.summary,'')
    def test_R5_atomic_judgment_and_closed_guard(self):
        judgment=s.record_judgment(self.j,self.c.pk,self.c.version,'Fictional resolution','This is a fictional outcome for demonstration only.')
        self.refresh(); self.assertEqual(self.c.status,'CLOSED'); self.assertIsNotNone(self.c.closed_at)
        self.assertEqual(judgment.case_id,self.c.pk)
        with self.assertRaises(ValidationError): s.schedule(self.r,self.c.pk,self.c.version,future())
        with self.assertRaises(ValidationError): s.update_assignments(self.r,self.c.pk,self.c.version,self.j2,[self.l2],'No changes after closure')
        with self.assertRaises(ValidationError): s.record_judgment(self.j,self.c.pk,self.c.version,'Another verdict','Should not insert duplicate judgment.')
    def test_R5_rollback_if_audit_fails(self):
        with patch('core.repository.audit',side_effect=RuntimeError('simulated persistence fault')):
            with self.assertRaises(RuntimeError): s.record_judgment(self.j,self.c.pk,self.c.version,'Demo outcome','Fictional summary of the final outcome.')
        self.refresh(); self.assertEqual(self.c.status,'REGISTERED'); self.assertEqual(Judgment.objects.count(),0)
    def test_R5_requires_no_booked_hearing(self):
        s.schedule(self.r,self.c.pk,self.c.version,future())
        with self.assertRaises(ValidationError): s.record_judgment(self.j,self.c.pk,self.refresh(),'Demo verdict','Fictional judgment summary text.')
        self.assertEqual(Judgment.objects.count(),0)
    def test_R6_access_filter_search_and_idor(self):
        c2=s.register_case(self.r,data(self.j2,self.l2,'Invisible secret fictional case'))
        self.assertEqual(s.search(self.r,{}).count(),2)
        self.assertEqual(s.search(self.j,{}).count(),1); self.assertEqual(s.search(self.l,{}).count(),1)
        self.client.force_login(self.l)
        self.assertEqual(self.client.get(reverse('case_detail',args=[c2.pk])).status_code,404)
        response=self.client.get('/cases/',{'q':'Invisible'})
        self.assertContains(response,'No cases found'); self.assertNotContains(response,c2.cin)
        self.assertContains(self.client.get('/cases/',{'q':self.c.cin}),self.c.title)
    def test_R7_create_deactivate_and_session_revocation(self):
        u=s.create_account(self.r,dict(name='New Fictional Lawyer',email='new@example.test',role='LAWYER',password=PASSWORD))
        self.assertTrue(u.password.startswith('argon2$')); self.assertNotEqual(u.password,PASSWORD)
        self.client.force_login(u); self.assertEqual(self.client.get('/').status_code,200)
        s.deactivate(self.r,u.pk,'End of demonstration access')
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertFalse(self.client.login(username=u.username,password=PASSWORD))
        self.assertTrue(User.objects.filter(pk=u.pk).exists())
    def test_R7_preserve_history_and_reassign_judge(self):
        with self.assertRaises(ValidationError): s.deactivate(self.r,self.j.pk,'Deactivate assigned judge')
        s.update_assignments(self.r,self.c.pk,self.c.version,self.j2,[self.l2],'New demonstration assignment')
        s.deactivate(self.r,self.j.pk,'All open matters reassigned')
        self.assertEqual(s.search(self.l,{}).count(),0)
        self.assertEqual(s.search(self.l2,{}).count(),1)
        self.assertIn(self.j.name,self.c.events.first().detail)
    def test_R7_disallows_registrar_creation_and_deactivation(self):
        with self.assertRaises(PermissionDenied): s.create_account(self.r,dict(name='Forbidden',email='bad@example.test',role='REGISTRAR',password=PASSWORD))
        with self.assertRaises(PermissionDenied): s.deactivate(self.r,self.r.pk,'Cannot remove bootstrap account')
    def test_stale_form_rejected(self):
        v=self.c.version; s.schedule(self.r,self.c.pk,v,future())
        with self.assertRaises(ValidationError): s.update_assignments(self.r,self.c.pk,v,self.j2,[self.l],'Stale assignment form')
    def test_assignment_conflict_rolls_back_all_changes(self):
        h=s.schedule(self.r,self.c.pk,self.c.version,future())
        c2=s.register_case(self.r,data(self.j2,self.l2,'Second assigned case')); s.schedule(self.r,c2.pk,c2.version,future())
        with self.assertRaises(ValidationError): s.update_assignments(self.r,self.c.pk,self.refresh(),self.j2,[self.l2],'Conflicting assignment')
        self.refresh(); h.refresh_from_db(); self.assertEqual(self.c.judge,self.j); self.assertEqual(h.judge,self.j); self.assertEqual(self.c.lawyers.get(),self.l)
    def test_database_guards_independent_of_service(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            Case.objects.filter(pk=self.c.pk).update(status='CLOSED',closed_at=timezone.now())
        s.record_judgment(self.j,self.c.pk,self.c.version,'Resolved for demo','An entirely fictional judgment summary.')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Hearing.objects.create(case=self.c,judge=self.j,starts_at=future())
        with self.assertRaises(IntegrityError),transaction.atomic():
            Case.objects.filter(pk=self.c.pk).update(status='REGISTERED',closed_at=None)
        with self.assertRaises(IntegrityError),transaction.atomic():
            Judgment.objects.filter(case=self.c).update(verdict='Changed verdict')
    def test_foreign_keys_and_representation_uniqueness(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            Representation.objects.create(case=self.c,lawyer=self.l,assigned_by=self.r)
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError): self.j.delete()
    def test_backend_role_denials(self):
        h=self.past_hearing()
        endpoints=[reverse('case_new'),reverse('account_new'),reverse('schedule',args=[self.c.pk]),reverse('assignments',args=[self.c.pk]),reverse('summary',args=[self.c.pk,h.pk]),reverse('judgment',args=[self.c.pk])]
        self.client.force_login(self.l)
        for url in endpoints:
            with self.subTest(url=url): self.assertEqual(self.client.post(url,{}).status_code,403)
        self.client.force_login(self.r)
        self.assertEqual(self.client.post(reverse('summary',args=[self.c.pk,h.pk]),{}).status_code,403)
    def test_csrf_required_and_logout_post_only(self):
        client=Client(enforce_csrf_checks=True); client.force_login(self.r)
        self.assertEqual(client.post('/cases/new/',{}).status_code,403)
        self.assertEqual(client.get('/logout/').status_code,405)
    def test_login_rate_limit(self):
        for n in range(10): self.assertTrue(s.allow_login('target@example.test','127.0.0.2'))
        self.assertFalse(s.allow_login('target@example.test','127.0.0.2'))
        response=self.client.post('/login/',{'username':'target@example.test','password':'invalid'})
        self.assertEqual(response.status_code,429)
    def test_validation_http_and_xss_escaping(self):
        self.client.force_login(self.r)
        response=self.client.post('/cases/new/',{'title':'x'})
        self.assertEqual(response.status_code,422); self.assertEqual(Case.objects.count(),1)
        self.c.description='<script>alert(1)</script>'; self.c.save()
        response=self.client.get(reverse('case_detail',args=[self.c.pk]))
        self.assertContains(response,'&lt;script&gt;'); self.assertNotContains(response,'<script>alert')
    def test_search_invalid_dates_and_pagination(self):
        self.client.force_login(self.r)
        response=self.client.get('/cases/',{'from_date':'garbage','page':'abc'})
        self.assertEqual(response.status_code,200); self.assertContains(response,'Enter a valid date')
    def test_inactive_actor_and_target_rejected(self):
        User.objects.filter(pk=self.j.pk).update(is_active=False)
        with self.assertRaises(ValidationError): s.register_case(self.r,data(self.j,self.l))
    def test_availability_scoped_and_weekends(self):
        self.client.force_login(self.l)
        self.assertEqual(self.client.get(reverse('slots',args=[self.c.pk]),{'day':future().date()}).status_code,403)
        saturday=future().date()
        while saturday.weekday()!=5: saturday+=timedelta(days=1)
        self.assertFalse(any(x['available'] for x in s.slots_for(self.c,saturday)))

class ConcurrentWorkflows(TransactionTestCase):
    reset_sequences=True
    def setUp(self):
        if connection.vendor!='postgresql': self.skipTest('True row-lock concurrency is verified with PostgreSQL.')
        self.r,self.j,self.l,self.j2,self.l2=users()
    def test_concurrent_cins(self):
        def create(n):
            close_old_connections()
            try: return s.register_case(User.objects.get(pk=self.r.pk),data(User.objects.get(pk=self.j.pk),User.objects.get(pk=self.l.pk),f'Concurrent fictional case {n}')).cin
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=6) as pool: cins=list(pool.map(create,range(24)))
        self.assertEqual(len(set(cins)),24); self.assertEqual(Case.objects.count(),24)
    def test_concurrent_slot_has_exactly_one_winner(self):
        cases=[s.register_case(self.r,data(self.j,self.l,f'Race case {i}')) for i in range(2)]
        def book(case):
            close_old_connections()
            try:
                s.schedule(User.objects.get(pk=self.r.pk),case.pk,case.version,future()); return True
            except ValidationError: return False
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(book,cases))
        self.assertEqual(sum(result),1); self.assertEqual(Hearing.objects.count(),1)
