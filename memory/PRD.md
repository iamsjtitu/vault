# PRD — MyVault (Personal Password & Insurance Vault)

## Original Problem Statement
"remember bank login id and passwords along with other logins. Also Insurance Details bhi store karne hai jaise Insurance company name, plan name, Premium Amount, Kitne years ka hai, Benefit, Maturity Amount etc."

## User Choices
- Single 4-digit Master PIN auth (no email/social login)
- Categories + password generator + copy-to-clipboard
- Passwords encrypted at rest
- Light, clean design

## Architecture
- FastAPI + MongoDB backend (`/app/backend/server.py`), all routes prefixed `/api`
- Master PIN: bcrypt-hashed in `vault_config`; JWT (HS256, 12h) Bearer tokens; brute-force lockout (5 tries → 15 min) via `login_attempts`
- Credential passwords Fernet-encrypted at rest (`ENCRYPTION_KEY` in backend/.env)
- React frontend: PinScreen, CredentialsTab, InsuranceTab; axios instance in `src/lib/api.js` (token in localStorage `vault_token`, 401 → auto-lock)
- Design: light "Soft Utility" theme, Work Sans + IBM Plex Sans, max-w-md mobile-first layout

## Implemented (June 2026 — MVP)
- PIN setup (first run) + unlock keypad with dots/shake animation
- Logins vault: CRUD, categories (Bank/Email/Social/Card/Other), search, show/hide password, copy username/password with toast, strong password generator (16 chars)
- Insurance vault: CRUD with company, plan, policy number, premium (+frequency), term years, sum assured, maturity amount/date, nominee, notes; ₹ en-IN formatting
- Lock button, session expiry auto-lock, change-pin API endpoint (backend only)

## Testing
- Iteration 1: 100% pass backend (8/8 pytest) + all frontend flows (see /app/test_reports/iteration_1.json)
- Master PIN for testing: 1234 (see /app/memory/test_credentials.md)

## Backlog
- P1: Change PIN UI (backend endpoint `/api/auth/change-pin` already exists)
- P1: Auto-lock after inactivity timeout
- P2: Export/backup vault (encrypted file)
- P2: Premium due-date reminders for insurance
- P2: Card details section (card number, expiry, CVV)
