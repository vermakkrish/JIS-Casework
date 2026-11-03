import getpass
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import User, AuditEvent

class Command(BaseCommand):
    help='Create the first Registrar. Credentials come from a prompt or BOOTSTRAP_* environment variables.'
    def handle(self,*args,**options):
        if User.objects.filter(role='REGISTRAR').exists():
            self.stdout.write('Registrar already exists; no changes made.'); return
        email=os.getenv('BOOTSTRAP_EMAIL') or input('Registrar email: ')
        name=os.getenv('BOOTSTRAP_NAME') or input('Registrar name: ')
        password=os.getenv('BOOTSTRAP_PASSWORD') or getpass.getpass('Registrar password: ')
        user=User(username=email.strip().lower(),email=email.strip().lower(),name=name.strip(),role='REGISTRAR')
        try:
            validate_email(user.email); validate_password(password,user)
            if len(user.name)<2: raise ValidationError('Name must contain at least two characters.')
        except ValidationError as e: raise CommandError('; '.join(e.messages))
        with transaction.atomic():
            # PostgreSQL advisory transaction lock makes first-run bootstrap safe across release jobs.
            from django.db import connection
            if connection.vendor=='postgresql':
                with connection.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(74823191)')
            if User.objects.filter(role='REGISTRAR').exists(): return
            user.set_password(password); user.save()
            AuditEvent.objects.create(actor=user,action='Registrar bootstrapped',detail='Initial Registrar created by operator command.')
        self.stdout.write(self.style.SUCCESS('Registrar created. Password is not printed or stored in source.'))
