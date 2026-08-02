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

## Implemented
### June 2026 — MVP
- PIN setup (first run) + unlock keypad with dots/shake animation
- Logins vault: CRUD, categories (Bank/Email/Social/Card/Other), search, show/hide password, copy username/password with toast, strong password generator (16 chars)
- Insurance vault: CRUD with company, plan, policy number, premium (+frequency), term years, sum assured, maturity amount/date, nominee, notes; ₹ en-IN formatting
- Lock button, session expiry auto-lock, change-pin API endpoint (backend only)

### June 2026 — Iteration 2
- Change PIN dialog via settings gear (old/new/confirm, digits only)
- Cards section: debit/credit cards rendered as dark payment-card tiles; card_number + CVV Fernet-encrypted at rest; show/hide, copy number, edit/delete
- Insurance: member_name (Father/Mother/Self) with badge + search by member/company/plan/policy/nominee; premium_due_date field
- Premium Reminders banner: policies due within 30 days (or overdue) with ₹ amount and due text
- PWA installable (manifest.json, sw.js, 192/512 icons): install on Windows (Chrome/Edge "Install app") and mobile ("Add to Home Screen"); data syncs across devices via cloud backend
- Desktop layout: 2-column grid on md+ screens
- Fixed: axios 401 interceptor no longer auto-locks on change-pin failure

### June 2026 — Iteration 3
- Family Grouping: member_name on Logins & Cards (like Insurance) — "Member / For Whom" field in forms, emerald member badges, member filter pills (dynamic, hidden when unused), member included in logins search
- Fixed: FAB was mis-anchored (fadeUp transform created containing block); animation now opacity-only, FAB truly bottom-right

### June 2026 — Iteration 4
- Mobile fixes: datalist → tappable suggestion chips (title + member, all 3 forms); refresh no longer re-asks PIN (localStorage token check on mount)
- Auto Lock Timer: vault locks after 5 min inactivity (mousedown/keydown/touchstart/scroll reset timer), toast on auto-lock
- Keyboard PIN entry (0-9 + Backspace) on lock screen
- GET /api/members endpoint (distinct members across all collections) powers suggestions
- New PWA icon (blue gradient padlock)
- Deployed to user's VPS (v.9x.design) with GitHub Actions auto-deploy (password auth)

### June 2026 — Iteration 5
- Document Storage: attach PDFs/photos/docs to any entry (logins, cards, insurance) via paperclip button → Documents dialog (upload/view/delete)
- Files stored in MongoDB GridFS, Fernet-encrypted at rest; 10MB cap; extension whitelist; cascade delete with parent entry
- Settings: auto-lock time selector (2/5/10 min, localStorage)
- VPS nginx client_max_body_size 15M (live + setup script)

### June 2026 — Iteration 6
- Attachment count badge on paperclip (all tabs, GET /api/documents/counts, refreshes on dialog close)
- Mark Premium Paid: green Paid button in reminder rows → POST /api/insurance/{id}/mark-paid advances due date by frequency (month-end safe), sets last_paid_on shown on card

### June 2026 — Iteration 7
- Payment History: mark-paid records in premium_payments (amount, paid_on, due date paid); GET /api/insurance/{id}/payments; History button + dialog on insurance cards; cascade delete with policy
- Maturity Alerts: indigo banner for policies maturing within 60 days (or matured — rose "claim now")

### June 2026 — Iteration 8
- Undo Paid: toast Undo action + Undo button on newest history row; POST /api/insurance/{id}/undo-paid restores due date & last_paid_on, deletes payment record
- Yearly Premium Total: annualized summary card on Insurance tab (Yearly ×1, Half-Yearly ×2, Quarterly ×4, Monthly ×12) with member-wise breakdown

## Testing
- Iteration 1: 100% pass backend (8/8 pytest) + all frontend flows (see /app/test_reports/iteration_1.json)
- Master PIN for testing: 1234 (see /app/memory/test_credentials.md)

## Backlog
- P1: Change PIN UI (backend endpoint `/api/auth/change-pin` already exists)
- P1: Auto-lock after inactivity timeout
- P2: Export/backup vault (encrypted file)
- P2: Premium due-date reminders for insurance
- P2: Card details section (card number, expiry, CVV)
