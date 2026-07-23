# Project Conversation Log

This is a privacy-safe work journal for CulturePick. It records user-visible requests, conclusions, changes, and verification results. It intentionally excludes secrets, hidden reasoning, and raw tool output.

> Backfill note: the entries before this file was created are reconstructed from the visible task context on 2026-07-23. They preserve decisions and outcomes, but are not a byte-for-byte transcript.

## Entries

### 2026-07-23 KST — Project discovery and snapshot comparison

**User request**

> Inspect the presentation-use integrated project folder, understand the project and its implemented/unimplemented features, then compare it with the adjacent backend-only folder before further work.

**Outcome**

- Identified CulturePick as a performance discovery and recommendation service built with Django REST Framework, PostgreSQL, Redis/Celery, KOPIS ingestion, community, and user activity logging.
- Compared the backend source folders: the backend-only repository and the backend within the integrated presentation snapshot were byte-identical for their shared tracked files. The backend-only repository remains the implementation target.
- Identified that the presentation materials contain unfinished or unrelated slides; no presentation files were changed.

**Work performed**

- Inspected project layout, routes, models, settings, fixtures, tests, Docker configuration, and presentation assets.

**Decisions / follow-up**

- Use `culturepick-back` as the source of truth for all backend changes.

### 2026-07-23 KST — Backend API and dependency diagnosis

**User request**

> Run Django and test implemented APIs. Check the stopped GMS integration, API keys, and database URL/credentials. Explain API improvements.

**Outcome**

- Local health, authentication, performance, community, logging, candidate recommendation, token refresh, PostgreSQL, Redis, and KOPIS smoke checks succeeded.
- The OpenAI credential was accepted, but live recommendation requests returned quota/billing exhaustion and correctly fell back to rule-based results. This is an AI-module issue and was later excluded from non-AI changes.
- The configured remote database endpoint timed out before authentication. This does not prove invalid credentials; it requires network/Security Group/VPN/route verification.
- Found a Docker/Celery configuration conflict: `.env` broker settings pointed at container-local `localhost` while Redis runs as the Compose `redis` service.
- Found six PostgreSQL test setup errors caused by a fixture performance ID longer than the model's 20-character limit.

**Work performed**

- Started the local Docker development stack, applied migrations, loaded local fixtures, ran API smoke requests, and executed the Django test suite.

**Decisions / follow-up**

- A future AI replacement should use the user's chosen fine-tuned OpenAI model; existing recommendation code was not changed in the following maintenance pass.

### 2026-07-23 KST — Non-AI reliability and security maintenance

**User request**

> Excluding AI-related items, apply all discovered errors and improvements. Do not make product or infrastructure choices without explaining them first.

**Outcome**

- Fixed local Celery broker configuration so web, worker, and beat use `redis://redis:6379/0`; made the Django database result backend explicit and made beat wait for database and Redis health.
- Added `GET /health/ready/`, which reports database and Redis readiness with `200` or `503` without leaking failure details. Existing `/health/` remains a liveness endpoint.
- Corrected the invalid performance test fixture ID and added readiness endpoint tests.
- Changed production and local Docker images to run application processes as the non-root `culturepick` user.
- Updated API and README documentation for the readiness endpoint.

**Work performed**

- Changed: `docker-compose.local.yml`, `common/views.py`, `common/tests.py`, `BE/urls.py`, `apps/performances/tests.py`, `Dockerfile`, `docker/Dockerfile`, `API.md`, and `README.md`.
- Verified: the local Docker stack starts; worker and beat connect to Redis; worker runs as non-root; the real Celery ping task returns `pong`; `/health/ready/` reports database and Redis `ok`.
- Verified: `python manage.py test --verbosity 1` passes all 107 tests in the rebuilt non-root image.

**Decisions / follow-up**

- Did not alter authentication transport, OAuth redirects, HTML sanitization policy, database deployment configuration, or KOPIS scheduling because they require product or infrastructure decisions.

### 2026-07-23 KST — Portable conversation logging setup

**User request**

> Create and apply a plugin that saves this conversation in the active folder so work can continue on another desktop environment. Also provide a more detailed explanation of pending choices.

**Outcome**

- Created and validated the personal Codex plugin `workspace-conversation-log` at `C:\Users\admin\plugins\workspace-conversation-log` and registered it in the personal marketplace.
- The plugin directs future tasks to maintain `.codex/conversation-log.md` at the active project root. It records user-visible requests, outcomes, changed files, checks, and decisions while redacting secrets.
- This file is the initial backfilled project journal.

**Work performed**

- Verified the plugin manifest with the Codex plugin validator.
- The current sandbox could not invoke the Codex CLI to install the plugin because Windows blocked the app executable. Installation must be completed from the Codex app.

**Decisions / follow-up**

- Use the plugin in a new task and explicitly ask Codex to maintain the project conversation log. Commit this log when cross-machine continuity is required.

### 2026-07-23 KST — Pending architecture and policy decision guide

**User request**

> Explain the choices that were deferred in enough detail to make an informed decision.

**Outcome**

- Prepared the following decision guide. No policy-changing code was applied without approval.

**Decisions / follow-up**

1. **Database configuration and remote access**
   - The settings use `DATABASE_URL` whenever it exists and ignore the separate `DB_*` values. Both are currently present, so a future operator can mistakenly edit the inactive values.
   - Recommended choice: make `DATABASE_URL` the single deployment source of truth, with a local Compose URL in local development and a TLS-enabled RDS URL in production. This makes the actual connection target unambiguous.
   - The remote host timed out before password authentication. To verify it, decide whether local developer machines are intentionally allowed to access RDS. If yes, add the required VPN/route/Security Group rule; if no, validate it from the production VPC instead.

2. **KOPIS automatic synchronization**
   - KOPIS tasks and a Celery beat process exist, but automatic KOPIS sync is currently not registered. Two independent scheduling mechanisms exist: code settings and database-backed `django-celery-beat` rows. Enabling both would create duplicate sync jobs.
   - Recommended choice: use database-backed schedules only, register the two existing jobs once, and run them daily at 04:10 and 04:30 KST. Confirm whether those times and the current 30-day ongoing/60-day upcoming windows are appropriate.

3. **Production HTTPS and Django security**
   - Production security flags are environment-controlled and currently default to permissive values. Enabling HTTPS redirect, secure cookies, and HSTS before confirming TLS termination can create redirect loops or make the site inaccessible.
   - Confirm the public domains and whether HTTPS terminates at an AWS load balancer, CloudFront, or the container. Then production can safely enforce HTTPS, secure cookies, explicit CORS/CSRF origins, a generated secret key, and HSTS.

4. **Authentication and social login transport**
   - Refresh tokens currently return in JSON. This is simple for the frontend but a browser script can read a token stored in local storage if an XSS issue occurs. HttpOnly secure cookies reduce that exposure but require frontend changes, credentialed CORS, and CSRF handling.
   - Confirm whether to preserve the current JSON-token contract or migrate to HttpOnly refresh cookies. Also provide the exact frontend OAuth callback URLs; the backend should allow only those URLs and enforce OAuth state/PKCE checks.
   - Login, registration, password verification, and public logging endpoints need deliberate throttling limits. Confirm the acceptable user experience and abuse tolerance before selecting Redis-backed limits.

5. **Community HTML policy**
   - Posts can store HTML and the backend currently only rejects empty text. Client-side sanitization alone does not protect another API client or future frontend from storing unsafe HTML.
   - Choose one content policy: Markdown-only (safest but changes the editor), backend HTML sanitization with an explicit Tiptap-compatible tag/attribute allowlist (recommended), or frontend-only sanitization (not recommended). Decide whether links, uploaded images, embeds, inline styles, and iframes are allowed before existing content is sanitized.

6. **Search and pagination contract**
   - My-interest and watchlist APIs return every row, while community uses offset pagination and performance searches use `icontains`. These work at current scale but become slower as users, posts, and performances grow.
   - Moving to cursor pagination or PostgreSQL trigram/full-text indexes improves scale but changes responses or requires a database migration. Confirm whether a frontend API change is acceptable and whether the RDS role can enable required PostgreSQL extensions.

7. **Logs, storage, and monitoring**
   - Public activity logs can be spammed and grow indefinitely without a rate and retention policy. Decide how long raw search/view/Q&A logs may be kept and whether to aggregate or delete old records.
   - Local S3 credential resolution failed; production appears intended to use an Elastic Beanstalk IAM role. Confirm that role, its bucket permissions, browser CORS rules, and image lifecycle/deletion policy.
   - OAuth credentials require an actual browser callback flow to validate. Error tracking and request metrics require choosing a service such as Sentry or a self-hosted monitoring stack and providing its configuration.

8. **User account recovery**
   - Password reset and verified email recovery are not currently implemented. Adding them requires a mail provider, sender identity, token-expiry policy, templates, and a frontend reset screen. Confirm whether this is a release requirement.

### 2026-07-23 KST — Automatic transcript plugin, account recovery, and HTML hardening

**User request**

> Adapt the automatic conversation logger from the copied hackathon project, preserve the full working context across desktops, clarify AWS/database/scheduling/HTTPS/search/log decisions, store community HTML through a server allowlist, and implement password reset and account recovery now.

**Outcome**

- Replaced the earlier manual-summary-only approach with a repository plugin at `plugins/workspace-conversation-log`.
- The plugin bundles a Codex `Stop` hook. It writes normalized user/assistant messages to `.codex/conversations/<session-id>.jsonl`, excludes system/tool/reasoning records, redacts common credential forms, limits transcript input to 100 MiB, and atomically replaces the session file. It fails closed and never copies an unparseable raw transcript.
- Backfilled this task's visible transcript through the same filter. The durable handoff summary remains this file.
- Registered the plugin in `.agents/plugins/marketplace.json` with repository-default installation. A new trusted task must review the hook through `/hooks`; existing tasks do not dynamically reload it.
- Added three public account-recovery APIs without changing the existing JSON access/refresh token contract:
  - password-reset email request with a generic response;
  - uid/token password confirmation with password validation and stored refresh-token revocation;
  - account provider reminder by email.
- Inactive and banned users are deliberately not reactivated because the model has no deactivation reason or reactivation policy.
- Added scoped throttling and SMTP/frontend URL settings. Recovery request views always enqueue the same-shaped Celery task; the worker performs account lookup and SMTP delivery so response timing does not reveal account existence. Production throttles use a shared Redis cache and an explicit trusted-proxy count. Production still needs a verified sender and actual email credentials. The integrated frontend currently has no `/find-account` route, so the backend is ready but the end-user flow is not complete until that small page exists.
- Added server-side Tiptap-compatible HTML sanitization through `nh3`. Create, PATCH, format conversion, and legacy API responses are sanitized. Markdown remains unchanged. Image sources are limited to `/media/` or HTTPS URLs on configured S3/CDN hosts; arbitrary external, plain-HTTP, protocol-relative, and traversal URLs are removed. Existing rows are not destructively rewritten automatically; `sanitize_community_html` is dry-run by default and requires `--apply`.
- Added a database-safe bulk cleanup command that streams rows, caps reported IDs, skips empty sanitized bodies for manual review, and avoids overwriting concurrently edited posts.

**Verification**

- Conversation logger unit tests: 8 passed. Plugin and hook JSON parsed successfully; the Windows bundled hook launcher preserved the Korean workspace path and updated the current session log successfully.
- Built all local Docker images with `nh3==0.3.6`.
- Full Django suite: 126 passed; Django system check reported no issues.
- `makemigrations --check --dry-run`: no changes detected.
- Ruff on all changed Python modules: all checks passed.
- Recreated local web, worker, and beat containers. `/health/` and `/health/ready/` returned `ok`; database and Redis readiness were `ok`; an unknown password-reset request returned the generic 200 response; the real Celery `ping_task` returned `pong`.
- Restarted the worker after adding recovery tasks and confirmed that both tasks were registered; an unknown-address reset task was received and completed successfully. Production settings loaded the Redis cache, `NUM_PROXIES=1`, and the configured S3 image host successfully.
- During testing, found and fixed a real plaintext email bug where Django escaped `&token=` as `&amp;token=`.
- During hook smoke testing, found and fixed PowerShell 5.1 native-pipe corruption of Korean `cwd` values and added a fallback to the actual hook process working directory. Also added a Windows file-lock fallback when an existing JSONL temporarily cannot be atomically replaced.

**Infrastructure conclusions that supersede the earlier preliminary guide**

1. Database variable names do not need to be unified. Use `DATABASE_URL` locally and `DB_*` in Elastic Beanstalk, but never populate both in the same environment. `DATABASE_URL` currently has precedence. `.env.example` and README now describe the two profiles. The prior recommendation to force every environment onto `DATABASE_URL` is superseded.
2. KOPIS database-backed schedules already have an idempotent registration command: `python manage.py setup_celery_beat_schedule`. The rows survive ordinary deployments in the same RDS and only need re-registration after database replacement/reset. Keep `CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=False` to avoid duplicate code schedules.
3. The current Compose topology starts beat on every EB instance. Before enabling autoscaling, move beat to one scheduler location; a single-instance environment can keep the present topology.
4. External check on 2026-07-23: `http://culturepick.ap-northeast-2.elasticbeanstalk.com/health/` returned 200, while the HTTPS endpoint timed out after 15 seconds. HTTPS is not currently terminated for this CNAME. A load-balanced EB environment needs a 443 listener, ACM certificate for a user-owned API domain, security-group access, and healthy target group. Do not enable HSTS/forced redirect until TLS and health checks are proven.
5. For current roughly ten-thousand-row service search, prefer PostgreSQL `pg_trgm`/GIN and existing response-compatible pagination before operating OpenSearch. For very large log analytics, use S3 Parquet plus Athena; for deep API traversal, use cursor pagination. OpenSearch remains appropriate later for hundreds of thousands/millions of searchable documents, typo tolerance, autocomplete, or Korean-language search requirements.

**Fine-tuning and log policy warning**

- Raw operational logs are not training-ready. Keep them access-controlled, redact personal data and credentials, deduplicate, obtain training consent/opt-out, and promote only human-reviewed examples into the existing `TrainingExampleCandidate` export flow.
- A proposed default is 60–90 days for raw search/view logs, 90–180 days for reviewable conversations, and longer retention only for de-identified aggregates or approved versioned training examples. This remains a product/privacy decision.
- Current OpenAI documentation says self-serve fine-tuning is being wound down: new/inactive organizations can no longer start training, and active existing customers lose new-job creation on 2027-01-06. Before designing around a fine-tuned OpenAI model, verify that this OpenAI organization still has eligible access and choose a fallback architecture if it does not.

**Decisions still required**

- Which owned backend domain should be used for the ACM certificate, or whether CloudFront should front EB.
- Whether EB will remain single-instance or use autoscaling, which determines the Celery beat deployment.
- Which SES-verified sender/domain and SMTP credentials to use; SES sandbox exit may also be required.
- Whether “inactive account recovery” should ever reactivate a user. Implementing it safely requires deactivation reason/date and administrator-policy fields; it is not part of the current endpoints.
- Whether password reset must invalidate already issued access tokens immediately. The current implementation revokes refresh tokens, while access tokens can remain valid for up to one hour; enabling SimpleJWT password-hash revocation forces existing users to sign in again once, while a user-level auth-version migration avoids that global logout.
- Raw-log retention periods, model-training consent/opt-out, deletion behavior, and archive destination.
- Whether to adopt PostgreSQL trigram search now or defer until measured query latency justifies a migration.

**Final plugin compatibility audit**

- Removed the redundant manifest `hooks` override so Codex uses the standard `hooks/hooks.json` discovery path. This preserves the Stop hook while remaining compatible with the bundled plugin validator schema.
- Added real Windows `py -3` launcher support before the existing `python3`, `python`, and Codex bundled-Python fallbacks. Failed launcher probes are silent and never block a task.
- Removed generated `__pycache__` artifacts from the plugin package.
- Re-ran all 8 logger tests, parsed the manifest/hook/marketplace JSON, and smoke-tested the Windows wrapper; all checks passed.

### 2026-07-23 KST — Auth-version security, trigram search, log lifecycle, and frontend handoff

**User decisions**

- Invalidate user sessions with a per-user `auth_version`.
- Add `deactivation_reason` and `deactivated_at`; do not expose a public account
  reactivation API yet.
- Defer the Elastic Beanstalk single-instance/load-balanced topology decision and
  keep it on the future infrastructure backlog.
- Keep the existing frontend JSON token contract.
- Apply PostgreSQL `pg_trgm` with GIN indexes.
- Use the recommended log policy: short-lived raw logs, de-identified daily
  aggregates, human review, and a separate curated training-data repository.
- Maintain a backend-owned Markdown checklist for frontend work, including
  password reset and account/provider recovery.

**Outcome**

- Added `auth_version` to users and JWT claims. Password changes and account-status
  transitions increment the version, clear the stored refresh token, and make old
  access/refresh tokens unusable without logging out unrelated users. Existing
  version-less tokens are accepted only while the user remains at version 1.
- Added explicit account-state reasons: `self_deactivated`, `admin_disabled`,
  `security_lock`, and `policy_banned`, plus timestamp/state consistency checks.
  Legacy inactive rows become `admin_disabled`, so they cannot accidentally enter
  a future self-service recovery path. Inactive social accounts are also blocked
  before any new JWT is issued.
- Added PostgreSQL-only migrations that install `pg_trgm` and create nine concurrent
  GIN expression indexes matching Django's `UPPER(column) ... icontains` queries for
  performances, venues, and community posts. SQLite migration runs safely skip the
  PostgreSQL operations.
- Added 90-day raw retention for search/view/Q&A logs. Expired rows are aggregated
  by day without user IDs, search keywords, questions, or answers before batch
  deletion. A shared-cache lock prevents overlapping Celery executions.
- Added the idempotent `setup_log_retention_schedule` command, which registers the
  daily job at 03:30 Asia/Seoul. The direct prune command remains dry-run unless
  `--apply` is provided.
- Updated the conversation plugin so it prunes only session JSONL files older than
  90 days on a later Stop hook; the durable handoff Markdown is never pruned.
- Training export now requires `approved_for_training`, a valid status, and both
  `reviewed_by` and `reviewed_at`. It removes sensitive fields/patterns, writes
  immutable version directories and SHA-256 manifests, and never exports raw Codex
  conversations.
- Created the independent local Git repository
  `../culturepick-training-data` on branch `main`, with a strict data policy and
  raw/staging-data ignore rules. No GitHub remote was created because the repository
  name, owner, and private-access policy have not been selected.
- Added `FRONTEND_HANDOFF.md` with exact API contracts, route/view tasks, token
  failure behavior, security constraints, completion criteria, and the explicit
  note that public inactive-account reactivation remains unavailable.

**HTTPS clarification**

- There are two practical HTTPS paths, not only one:
  1. owned API domain → ACM certificate on an EB Application Load Balancer → EB
     instances over HTTP; this is the recommended production topology and requires
     a load-balanced EB environment;
  2. default `https://d....cloudfront.net` distribution → current EB HTTP origin;
     this works without owning a domain and can front a single-instance environment.
- The `culturepick.netlify.app` hostname is owned by Netlify, so CulturePick cannot
  issue an ACM certificate for `api.culturepick.netlify.app`.
- Direct certificate termination on the EB instance is technically possible but
  remains intentionally unselected because instance replacement and certificate
  renewal become application-team responsibilities.

**Verification**

- Applied all new migrations to local PostgreSQL 16 successfully.
- Confirmed `pg_trgm` is installed and all nine expected indexes use GIN,
  `gin_trgm_ops`, and `upper(...)`.
- Full Django suite: 148 tests passed; system check reported no issues.
- Focused auth/log/export/PostgreSQL suite: 22 tests passed.
- Conversation plugin: 10 tests passed; official plugin validator passed after the
  cachebuster update.
- Ruff passed for all changed application modules; `git diff --check` passed.
- `makemigrations --check --dry-run` reported no changes; Docker Compose config
  validation passed.
- Live local `/health/` and `/health/ready/` returned 200 with database and Redis
  both `ok`. Web, worker, and beat are running, and the worker registered
  `logs.prune_expired_logs`.
- Local log-prune dry-run found no expired rows/files. Training export dry-run
  reached the mounted sibling repository and found no currently human-reviewed
  candidates, so it wrote nothing.

**Deployment / follow-up**

- Deploy the migrations before new application instances serve traffic.
- In production, run `python manage.py setup_log_retention_schedule` once against
  the production RDS and keep only one Celery Beat scheduler when autoscaling.
- Frontend work is tracked in `FRONTEND_HANDOFF.md`.
- Create a separate private GitHub repository and remote for
  `culturepick-training-data`; do not attach it to the backend remote.
- Revisit the deferred EB topology/domain decision before changing Django secure
  redirect/HSTS settings or Netlify's API base URL.
- When future work is listed, explicitly include public self-deactivated-account
  reactivation design and the deferred EB scheduler/topology decision.
