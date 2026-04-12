# 🏦 FraudDetection — Real-Time Banking Fraud Detection with Machine Learning

A fully functional digital banking backend where fraud detection is integrated directly into every transaction — not as a separate module. Every transfer and withdrawal is scored in real time by a trained Gradient Boosting model running locally via Docker. Flagged transactions are held 
for human review, and those decisions automatically feed back into future model training datasets.

---

## What's Inside

This is a complete banking system. It includes:

- Full user authentication (register → email activation → two-phase OTP login → JWT cookies)
- Bank account management with KYC verification workflow
- Fund deposits, withdrawals, and two-phase OTP transfers with live currency conversion
- Virtual card creation, activation, blocking, top-up, and deletion
- Real-time fraud scoring on every transaction using Gradient Boosting
- Human-in-the-loop fraud review with feedback loop into model retraining
- Automated ML retraining pipeline via Celery Beat + MLflow
- Async email notifications for all banking events (28 templates)
- PDF statement generation via ReportLab + Redis
- Cloudinary image uploads for profile/ID/signature photos
- Redis-backed rate limiting with per-endpoint config and violation logging
- Idempotency keys on all financial operations
- Role-based access control across 6 user roles

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Database | PostgreSQL 16, SQLModel, SQLAlchemy (async), Alembic |
| ML | scikit-learn (GradientBoostingClassifier), MLflow, pandas, numpy |
| Task Queue | Celery 5.3, RabbitMQ (broker), Redis (result backend) |
| Cache | Redis |
| Email | FastMail, Mailpit (dev), Jinja2 templates |
| Storage | Cloudinary (images), ReportLab (PDF statements) |
| Auth | PyJWT, Argon2, OTP |
| Infrastructure | Docker, Docker Compose, Traefik |
| Monitoring | Flower (Celery), MLflow UI |
| Logging | Loguru (debug.log + error.log) |

---

## Project Structure

```
src/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI app, lifespan, health checks, middleware
│   │   ├── auth/                          # User model, schemas, JWT + Argon2 utils
│   │   ├── bank_account/                  # Account model, schemas, Luhn account number generation, currency conversion
│   │   ├── transaction/                   # Transaction model, schemas, failure tracking utils
│   │   ├── virtual_card/                  # Card model, schemas, Visa number + CVV generation
│   │   ├── user_profile/                  # Profile model, KYC schemas, image type enums
│   │   ├── next_of_kin/                   # Next of kin model and schemas
│   │   └── core/
│   │       ├── ai/                        # TransactionAIService, risk scoring, AIReviewStatusEnum
│   │       ├── ml/
│   │       │   ├── feature_engineering.py # 30+ features: time, account, history, velocity, metadata
│   │       │   ├── training.py            # ModelTrainer — dataset prep, GB training, MLflow logging
│   │       │   ├── deployment.py          # ModelDeployer, ModelInference, fallback heuristic
│   │       │   ├── evaluation.py          # AUC, precision, recall, F1, confusion matrix, false positives
│   │       │   ├── config.py              # ML settings (threshold, hyperparams, paths)
│   │       │   ├── models.py              # MLModel, ModelPrediction, TrainingDataset DB tables
│   │       │   ├── schema.py              # ModelStatusEnum, ModelTypeEnum
│   │       │   └── cleanup.py             # Cleans stale MLflow runs on startup
│   │       ├── tasks/                     # Celery tasks: email, image_upload, statement PDF, ML training
│   │       ├── emails/                    # EmailTemplate base class + 28 Jinja2 HTML/text templates
│   │       ├── services/                  # One service file per email event type
│   │       ├── rate_limit/                # Redis middleware, per-endpoint limits, RateLimitLog model
│   │       ├── management/commands/       # seed_db.py — users, accounts, transactions, fraud labels
│   │       ├── config.py                  # Pydantic settings from .env
│   │       ├── db.py                      # Async engine, session factory, init_db
│   │       ├── celery_app.py              # Celery app, two queues, Beat schedule
│   │       ├── health.py                  # HealthCheck with retry, dependency ordering, 25s cache
│   │       ├── logging.py                 # Loguru — debug + error log files with rotation
│   │       └── model_registry.py          # Auto-discovers all models.py for Alembic metadata
│   └── api/
│       ├── main.py                        # Aggregates all 30+ routers
│       ├── routes/
│       │   ├── auth/                      # register, activate, login, logout, refresh, password_reset
│       │   ├── bank_account/              # create, activate, deposit, withdraw, transfer, statement, history
│       │   ├── card/                      # create, activate, block, topup, delete
│       │   ├── next_of_kin/               # create, all, update, delete
│       │   ├── profile/                   # create, update, me, all_profiles, upload + status
│       │   ├── transaction/               # fraud_review, risk_history
│       │   └── ml/                        # train, models list, status, evaluate, deploy, auto-deploy
│       └── services/                      # Business logic: user_auth, bank_account, card, transaction, profile, next_of_kin
├── migrations/                            # 12 Alembic migration files (one per table)
├── local.yml                              # Docker Compose — 10 services
├── Makefile                               # Developer shortcuts
├── postman-prescript.js                   # Auto-generates Idempotency-Key UUID for Postman
└── alembic.ini
```

---

## Database — 13 Tables

| Table | What it stores |
|---|---|
| `user` | Credentials (Argon2 hash), OTP + expiry, lockout state, role, security question |
| `profile` | KYC data — personal info, employment, ID documents, photo URLs (Cloudinary) |
| `nextofkin` | Emergency contacts per user (max 3, one primary required) |
| `bankaccount` | 16-digit Luhn account number, balance, currency, KYC verified status |
| `transaction` | Amount, reference, type, status, AI review status, JSONB metadata, failure reason |
| `virtualcard` | Visa card number (Luhn), CVV hash (Argon2), daily/monthly limits, block reason |
| `idempotencykey` | UUID v4 key + cached response body per financial operation (24hr expiry) |
| `transactionriskscore` | ML fraud probability, JSONB risk factors, reviewer ID, confirmed fraud flag |
| `mlmodel` | AUC, precision, recall, F1, feature list, hyperparams, MLflow run ID + model URI |
| `modelprediction` | Per-transaction prediction score, input features (JSONB), true label |
| `trainingdataset` | Dataset metadata — size, fraud/legit count, feature info, MLflow artifact URI |
| `ratelimitlog` | Violation records — IP, user, endpoint, count, window start/end, blocked_until |
| `alembic_version` | Current migration version |

---

## How Fraud Detection Works

```
User initiates transfer or withdrawal
              ↓
Feature extraction — FeatureExtractor (feature_engineering.py)
  Time:     hour_of_day, day_of_week, is_weekend, is_banking_hours,
            is_late_night, month, is_month_end, is_month_start
  Amount:   raw amount, is_currency_conversion, conversion_ratio
  Account:  sender/receiver balance, age_days, tx_count,
            avg/std/max/min amount (separate for sender + receiver)
  History:  user_transaction_count_90d, user_avg_amount_90d,
            user_max_amount_90d, user_std_amount_90d,
            user_transaction_frequency_daily, tx_type ratios
  Velocity: tx_count + tx_total_amount over 1h / 1d / 7d / 30d
              ↓
GradientBoostingClassifier.predict_proba()
  → fraud probability score: 0.0 – 1.0
              ↓
        Score < 0.7?
       ↙            ↘
    YES               NO
 CLEARED           FLAGGED
 ai_review_status  Temporarily blocked
 = CLEARED         ai_review_status = FLAGGED
 Transaction       Stored in TransactionRiskScore
 proceeds          Account executive notified
                        ↓
             POST /transaction/{id}/review
              ↙                    ↘
     is_fraud=true           is_fraud=false
     CONFIRMED_FRAUD         CLEARED
     Transaction FAILED      Transaction COMPLETED
          ↓                  automatically
  Stored as labeled
  training data →
  feeds next training run
```

**Fallback heuristic** (when no model is deployed — `_fallback_prediction()` in `deployment.py`):
- Amount > 10,000 → score 0.7 · Amount > 5,000 → 0.5 · Amount > 1,000 → 0.3 · else 0.1
- Late night (before 6AM or after 10PM) → +0.1

---

## ML Pipeline

### Training flow (`training.py`)

```python
ModelTrainer.train_model(start_date, end_date, hyperparams)
  → prepare_training_dataset()        # async DB queries via FeatureExtractor
  → pd.get_dummies() + fillna(0)      # encode categoricals, fill nulls
  → train_test_split(stratify=y)      # 80/20 stratified split
  → GradientBoostingClassifier.fit()  # train on 80%
  → roc_auc_score, precision_score,   # evaluate on 20%
     recall_score, f1_score,
     confusion_matrix
  → mlflow.sklearn.log_model()        # log to MLflow registry
  → MLModel saved to DB               # status = READY
```

Default hyperparameters (configurable via API):
```python
n_estimators=100, learning_rate=0.1, max_depth=3,
min_samples_split=2, min_samples_leaf=1, subsample=0.8, random_state=42
```

### Deployment (`deployment.py`)

`ModelDeployer.deploy_model()` — promotes a `READY` model to `DEPLOYED`, archives the current deployed model, and transitions the MLflow registry stage to Production.

`ModelInference.predict_fraud()` — loads model by `mlflow_model_uri`, caches it in memory, aligns features to `model.feature_names_in_`, calls `predict_proba()`.

### Celery Beat schedule (`celery_app.py`)

| Task | Schedule | Purpose |
|---|---|---|
| `train_fraud_detection_model` | Daily at night | Incremental retraining on recent data |
| `train_fraud_detection_model` | Weekly (Sunday) | Deep retraining with extended history + stronger hyperparams |
| `evaluate_fraud_model_performance` | Daily morning | Track model drift |
| `auto_deploy_best_model` | Weekly Monday | Promote better model if AUC improved |

Two Celery queues: `nextgen_tasks` (email, PDF, image) and `ml_tasks` (training, deployment) — kept separate so ML jobs never block emails.

---

## Authentication

**Login — two phases:**
```
POST /api/v1/auth/login/request-otp   # email + password → OTP sent to email
POST /api/v1/auth/login/verify-otp    # email + OTP → sets HttpOnly JWT cookies
```

**Fund transfer — two verifications:**
```
POST /api/v1/bank-account/transfer/initiate   # security_answer verified → OTP sent → Transaction = Pending
POST /api/v1/bank-account/transfer/complete   # OTP verified → balances updated → Transaction = Completed
```

**Tokens:**
- Access token: 30 min, signed with `SIGNING_KEY`
- Refresh token: 1 day, same key
- Activation + password reset tokens: signed with `JWT_SECRET_KEY` (separate key), short expiry
- All cookies: `HttpOnly=True`, `SameSite=lax`, `Secure` in production

---

## User Roles

| Role | Permissions |
|---|---|
| `customer` | Own profile, bank accounts, transactions, virtual cards |
| `teller` | Process deposits, process withdrawals |
| `account_executive` | Activate bank accounts after KYC, activate virtual cards, review flagged fraud, view risk history |
| `branch_manager` | View all user profiles |
| `admin` | General administration |
| `super_admin` | Full ML pipeline access — train, evaluate, deploy, auto-deploy |

---

## Rate Limiting

Middleware in `core/rate_limit/middleware.py` — runs on every request before routing.
Redis key format: `ratelimit:{endpoint}:{ip}:{user_id}`

| Endpoint | Limit | Window |
|---|---|---|
| `/auth/login/request-otp` | 10 | 5 min |
| `/auth/register` | 3 | 1 hour |
| `/auth/reset-password` | 3 | 1 hour |
| `/bank-account/transfer/initiate` | 10 | 1 hour |
| `/bank-account/withdraw` | 10 | 1 hour |
| `/bank-account/deposit` | 20 | 1 hour |
| `/virtual-card/top-up` | 20 | 1 hour |
| `/profile/upload` | 10 | 1 hour |
| `/health` | 500 | 1 min (not blocked) |
| Default | 100 | 1 min (not blocked) |

Violations → HTTP 429, `Retry-After` header, logged to `ratelimitlog` table.
Response headers on every request: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

---

## Idempotency

Transfers, withdrawals, and card top-ups require an `Idempotency-Key: <uuid-v4>` header.
The server stores `key + endpoint + response_body` in the `idempotencykey` table with 24-hour expiry.
Duplicate requests return the cached response — no double processing.

`postman-prescript.js` auto-generates this header in Postman for every request.

---

## Email Notifications

28 HTML + plain text Jinja2 templates, all sent asynchronously via `send_email_task` (Celery):

| Event | Template |
|---|---|
| Account registration | `activation.html` |
| Account activated | `account_activated.html` |
| Bank account created | `account_created.html` |
| Bank account activated | `account_activated.html` |
| Login OTP | `login_otp.html` |
| Transfer OTP | `transfer_otp.html` |
| Transfer alert (sender + receiver) | `transfer_alert.html` |
| Deposit alert | `deposit_alert.html` |
| Withdrawal alert | `withdrawal_alert.html` |
| Password reset | `password_reset.html` |
| Account lockout | `account_lockout.html` |
| Card created | `card_created.html` |
| Card activated | `card_activated.html` |
| Card blocked | `card_blocked.html` |

Email task has 3 retries with exponential backoff. Dev emails captured by Mailpit at `localhost:8025`.

---


## Seed Data

`seed_db.py` generates realistic training data from your actual DB schema:

| What | Count |
|---|---|
| Users | 20 (1 super admin, 1 account executive, 1 teller, 17 customers) |
| Bank accounts | 25–40 (1–2 per user, random currency) |
| Transactions | ~1000 (50 per user, spread over 90 days) |
| Fraud labels | 10 (FLAGGED or CONFIRMED_FRAUD with risk scores 0.75–0.99) |

All seeded users have password: `password123`
Seed user emails follow the pattern: `user1@example.com`, `user2@example.com`, etc.

---

## Security Summary

| Feature | Implementation |
|---|---|
| Password hashing | Argon2 (`argon2-cffi`) |
| OTP | 6-digit random, 5-min expiry, cleared after use |
| Account lockout | After 3 failed attempts, auto-unlock after cooldown |
| Account number | 16-digit with Luhn checksum validation |
| Card number | 16-digit Luhn-validated Visa number (`generate_visa_card_number()`) |
| CVV | Argon2 hashed — never stored plain, sent once in activation email |
| JWT | Two separate signing keys for auth tokens vs activation/reset tokens |
| Cookies | HttpOnly, SameSite=lax, Secure in production |
| Rate limiting | Redis per endpoint+IP+user, violations logged to DB |
| Idempotency | UUID v4 keys, 24hr expiry, cached response body |
| Role enforcement | Checked at route level AND inside service functions |
| Input validation | Pydantic v2 on all request schemas |

---

