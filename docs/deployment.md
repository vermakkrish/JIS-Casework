# Deployment and recovery runbook

## Current status

**Deployment is paused at the project owner's request. No public URL has been verified.** The source repository is [vermakkrish/JIS-Casework](https://github.com/vermakkrish/JIS-Casework).

Render and Docker configuration are prepared for the Django/PostgreSQL stack. Vercel has been discussed as a preferred host, but a Vercel-specific deployment has not been implemented or tested. Choosing a host, provisioning a persistent database, configuring secrets and completing live smoke tests are still required. The original build session had no enabled hosting connection; that historical limitation is not a statement about current platform availability.

When deployment resumes, use a host's secure connection flow or secret manager; do not paste credentials into chat or commit them. Review current resource pricing before provisioning paid services.

## Prepared Render path

The checked-in `render.yaml` defines one Python web service and one persistent PostgreSQL 18 database, using plan IDs selected during preparation, `0.5c-512mb` and `0.1c-256mb`. These are paid resources; verify the actual current price and approve the cost before applying. Database public IP access is disabled. The web service exposes only its sign-in page until authenticated. No free expiring database or ephemeral filesystem storage is used.

1. Push this repository to a team-owned Git remote. Exclude `private/`, SQLite files, `.env`, dumps, and local runtime folders; `.gitignore` already does so.
2. In the Render account, connect the repository and create a Blueprint from `render.yaml`. Review the concrete web/database resource plan and billing before applying.
3. Supply `SECRET_KEY` through Render’s secret prompt using at least 50 random characters, for example the output of `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Do not store that output in source control. The Blueprint deliberately does not use Render’s shorter default generated-secret format.
4. Render supplies `DATABASE_URL`, Python version, and `JIS_ENV=production`; the app also accepts `RENDER_EXTERNAL_HOSTNAME` as an allowed host. For a custom domain add that exact hostname to `ALLOWED_HOSTS` and its HTTPS origin to `CSRF_TRUSTED_ORIGINS`. Do not use wildcard hosts. Ensure the ingress strips user-supplied forwarded scheme headers.
5. Build installs the pinned dependencies and collects static files. The pre-deployment job runs versioned migrations once before the new service starts. Gunicorn serves the application; WhiteNoise serves fingerprinted static assets. Do not use Django runserver publicly.
6. For a blank real installation, run `python manage.py bootstrap_registrar` in the host shell. Supply `BOOTSTRAP_EMAIL`, `BOOTSTRAP_NAME`, and `BOOTSTRAP_PASSWORD` as temporary secrets if interactive input is unavailable. Remove the password variable after successful bootstrap. The command is idempotent and never prints the password.
7. For a dedicated fictional evaluation environment, use `ALLOW_DEMO_SEED=1` and a strong temporary `DEMO_PASSWORD`, then run `python manage.py seed_demo` instead of bootstrap. It requires an empty database. Remove both environment values after seeding; change each account to a separate password if others will use the demo.
8. Run `python manage.py check --deploy --fail-level WARNING`, verify `/health/`, and run the HTTPS smoke command below with private role credentials. Run the browser acceptance suite against a fresh dedicated demo to verify R1–R7 on the actual host. It intentionally writes fictional records; do not run against non-demo data.
9. Restart/redeploy the web service and verify the same CINs, hearing history and judgment remain. Record the returned live URL, commit SHA, deployed version, database identifier (not password), test timestamp and smoke outcomes in the README. Only then call the live deployment verified.

```bash
# Export these privately: BASE_URL=https://actual-host, REGISTRAR_EMAIL,
# REGISTRAR_PASSWORD, JUDGE_EMAIL, JUDGE_PASSWORD, LAWYER_EMAIL, LAWYER_PASSWORD
BROWSER_CHANNEL=chromium node scripts/smoke.mjs
# Dedicated fresh seed only; uses DEMO_PASSWORD and documented seed emails:
BASE_URL=https://actual-host BROWSER_CHANNEL=chromium npm run test:e2e
```

## Container alternative

`Dockerfile` builds a non-root Gunicorn image. `compose.yaml` provides PostgreSQL 18 with a named persistent volume and no public database port. Set `POSTGRES_PASSWORD` to a URL-safe random value and `SECRET_KEY` privately, then:

```bash
docker compose up -d db
docker compose build web
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py bootstrap_registrar
docker compose up -d web
```

The default Compose setup binds the application to loopback for local review. For public hosting, place it behind a trusted HTTPS proxy, set `JIS_ENV=production`, exact host/origin values, and forward the trusted scheme. Keep the PostgreSQL volume across restarts. Never use `docker compose down -v` on a database you intend to keep. A Docker daemon was unavailable on the build machine, so the container image has not been executed here; Django production checks and PostgreSQL tests are the verified evidence.

## Backup and restore

Choose a backup retention policy appropriate to the project (for the fictional evaluation, daily backups and seven-day retention is a reasonable starting point). Use the provider’s managed snapshots/PITR if available, and export a logical backup before migrations. Store backup files encrypted outside the application container, with restricted access; they include password hashes and session records.

```bash
# DATABASE_URL is supplied in the operator environment, never copied into documentation.
pg_dump --format=custom --file=jis-backup.dump "$DATABASE_URL"
# Restore into a NEW empty database, never into the running production DB.
pg_restore --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL" jis-backup.dump
```

A full custom-format restore creates tables/data before restoring triggers, avoiding the closed-case insertion guard during bulk restoration. After restore, run migrations/checks, compare Case/Hearing/Judgment counts and CINs, validate Closed ↔ judgment consistency, and smoke-test each role before switching the app to the restored database. Delete sessions with `python manage.py clearsessions`; to revoke all existing sessions after recovery, delete session rows through a trusted operator command. Perform a restore rehearsal periodically; a backup that has never been restored is insufficient evidence.

For a failed application release, roll back the app to a compatible commit. Do not blindly reverse migrations that contain user data. Restore a backup into a new database and switch only after validation if schema/data recovery is required.

## References checked during preparation

- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Django password hashing](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/)
- [Render Django deployment](https://render.com/docs/deploy-django)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Render compute plan IDs](https://render.com/docs/compute-plans)

The runbook is an implementation plan with local validation, not evidence of an external deployment. Host validation, billing, secret provisioning and live smoke tests remain pending until access is available.
