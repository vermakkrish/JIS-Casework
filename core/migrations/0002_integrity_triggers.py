from django.db import migrations

SQLITE = [
"""CREATE TRIGGER jis_case_guard BEFORE UPDATE ON core_case BEGIN
 SELECT CASE WHEN OLD.status='CLOSED' THEN RAISE(ABORT,'Closed cases are immutable') END;
 SELECT CASE WHEN NEW.status='CLOSED' AND NOT EXISTS(SELECT 1 FROM core_judgment WHERE case_id=NEW.id) THEN RAISE(ABORT,'Closure requires judgment') END;
 END""",
"""CREATE TRIGGER jis_judgment_guard BEFORE INSERT ON core_judgment BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND status!='CLOSED' AND judge_id=NEW.judge_id) THEN RAISE(ABORT,'Invalid judgment case or Judge') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM core_hearing WHERE case_id=NEW.case_id AND status IN ('SCHEDULED','RESCHEDULED')) THEN RAISE(ABORT,'Outstanding hearing') END;
 END""",
"""CREATE TRIGGER jis_judgment_close AFTER INSERT ON core_judgment BEGIN
 UPDATE core_case SET status='CLOSED', closed_at=NEW.created_at, version=version+1 WHERE id=NEW.case_id;
 END""",
"""CREATE TRIGGER jis_judgment_immutable BEFORE UPDATE ON core_judgment BEGIN SELECT RAISE(ABORT,'Judgments are immutable'); END""",
"""CREATE TRIGGER jis_hearing_insert BEFORE INSERT ON core_hearing BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND status='CLOSED') THEN RAISE(ABORT,'Closed case') END;
 END""",
"""CREATE TRIGGER jis_hearing_update BEFORE UPDATE ON core_hearing BEGIN
 SELECT CASE WHEN OLD.status='COMPLETED' THEN RAISE(ABORT,'Completed hearing is immutable') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND status='CLOSED') THEN RAISE(ABORT,'Closed case') END;
 END""",
]
POSTGRES = """
CREATE FUNCTION jis_case_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF OLD.status='CLOSED' THEN RAISE EXCEPTION 'Closed cases are immutable' USING ERRCODE='23514'; END IF;
 IF NEW.status='CLOSED' AND NOT EXISTS(SELECT 1 FROM core_judgment WHERE case_id=NEW.id) THEN RAISE EXCEPTION 'Closure requires judgment' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER jis_case_guard BEFORE UPDATE ON core_case FOR EACH ROW EXECUTE FUNCTION jis_case_guard_fn();
CREATE FUNCTION jis_judgment_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 PERFORM id FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND status!='CLOSED' AND judge_id=NEW.judge_id) THEN RAISE EXCEPTION 'Invalid judgment case or Judge' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM core_hearing WHERE case_id=NEW.case_id AND status IN ('SCHEDULED','RESCHEDULED')) THEN RAISE EXCEPTION 'Outstanding hearing' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER jis_judgment_guard BEFORE INSERT ON core_judgment FOR EACH ROW EXECUTE FUNCTION jis_judgment_guard_fn();
CREATE FUNCTION jis_judgment_close_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 UPDATE core_case SET status='CLOSED',closed_at=NEW.created_at,version=version+1 WHERE id=NEW.case_id;
 RETURN NEW; END $$;
CREATE TRIGGER jis_judgment_close AFTER INSERT ON core_judgment FOR EACH ROW EXECUTE FUNCTION jis_judgment_close_fn();
CREATE FUNCTION jis_judgment_immutable_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 RAISE EXCEPTION 'Judgments are immutable' USING ERRCODE='23514'; END $$;
CREATE TRIGGER jis_judgment_immutable BEFORE UPDATE ON core_judgment FOR EACH ROW EXECUTE FUNCTION jis_judgment_immutable_fn();
CREATE FUNCTION jis_hearing_guard_fn() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 PERFORM id FROM core_case WHERE id=NEW.case_id FOR UPDATE;
 IF TG_OP='UPDATE' AND OLD.status='COMPLETED' THEN RAISE EXCEPTION 'Completed hearing is immutable' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM core_case WHERE id=NEW.case_id AND status='CLOSED') THEN RAISE EXCEPTION 'Closed case' USING ERRCODE='23514'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER jis_hearing_insert BEFORE INSERT ON core_hearing FOR EACH ROW EXECUTE FUNCTION jis_hearing_guard_fn();
CREATE TRIGGER jis_hearing_update BEFORE UPDATE ON core_hearing FOR EACH ROW EXECUTE FUNCTION jis_hearing_guard_fn();
"""

def forward(apps, schema_editor):
    if schema_editor.connection.vendor=='sqlite':
        for statement in SQLITE: schema_editor.execute(statement)
    elif schema_editor.connection.vendor=='postgresql': schema_editor.execute(POSTGRES)
    else: raise RuntimeError('JIS supports SQLite development and PostgreSQL production only.')

def backward(apps, schema_editor):
    names={'jis_case_guard':'core_case','jis_judgment_guard':'core_judgment','jis_judgment_close':'core_judgment',
           'jis_judgment_immutable':'core_judgment','jis_hearing_insert':'core_hearing','jis_hearing_update':'core_hearing'}
    for name,table in names.items():
        suffix=f' ON {table}' if schema_editor.connection.vendor=='postgresql' else ''
        schema_editor.execute(f'DROP TRIGGER IF EXISTS {name}{suffix}')
    if schema_editor.connection.vendor=='postgresql':
        for name in ['case_guard','judgment_guard','judgment_close','judgment_immutable','hearing_guard']:
            schema_editor.execute(f'DROP FUNCTION IF EXISTS jis_{name}_fn()')

class Migration(migrations.Migration):
    dependencies=[('core','0001_initial')]
    operations=[migrations.RunPython(forward,backward)]
