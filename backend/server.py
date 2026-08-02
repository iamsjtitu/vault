from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional

import jwt
import bcrypt
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field, ConfigDict

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
fs_bucket = AsyncIOMotorGridFSBucket(db)

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
fernet = Fernet(os.environ['ENCRYPTION_KEY'].encode())


def enc(v: str) -> str:
    return fernet.encrypt(v.encode()).decode() if v else ""


def dec(v: str) -> str:
    return fernet.decrypt(v.encode()).decode() if v else ""


app = FastAPI()
api_router = APIRouter(prefix="/api")

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))


def create_token(ver: int = 0) -> str:
    payload = {"sub": "vault_owner", "ver": ver, "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_auth(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        vault = await db.vault_config.find_one({"key": "master_pin"})
        if int(payload.get("ver", 0)) != int((vault or {}).get("token_ver", 0)):
            raise HTTPException(status_code=401, detail="Session expired, unlock again")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, unlock again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------- Models ----------

class PinInput(BaseModel):
    pin: str = Field(min_length=4, max_length=8)


class ChangePinInput(BaseModel):
    old_pin: str
    new_pin: str = Field(min_length=4, max_length=8)


class CredentialCreate(BaseModel):
    title: str
    category: str = "Other"
    member_name: str = ""
    username: str = ""
    password: str = ""
    website: str = ""
    notes: str = ""


class Credential(CredentialCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = ""
    updated_at: str = ""


class InsuranceCreate(BaseModel):
    company_name: str
    plan_name: str = ""
    policy_number: str = ""
    member_name: str = ""
    premium_amount: Optional[float] = None
    premium_frequency: str = "Yearly"
    premium_due_date: str = ""
    term_years: Optional[int] = None
    sum_assured: Optional[float] = None
    maturity_amount: Optional[float] = None
    maturity_date: str = ""
    nominee: str = ""
    notes: str = ""


class Insurance(InsuranceCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    last_paid_on: str = ""
    created_at: str = ""
    updated_at: str = ""


class CardCreate(BaseModel):
    bank_name: str
    card_name: str = ""
    card_type: str = "Debit"
    member_name: str = ""
    card_number: str = ""
    expiry: str = ""
    cvv: str = ""
    cardholder_name: str = ""
    notes: str = ""


class CardItem(CardCreate):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = ""
    updated_at: str = ""


# ---------- Auth ----------

@api_router.get("/auth/status")
async def auth_status():
    vault = await db.vault_config.find_one({"key": "master_pin"})
    return {"pin_set": vault is not None}


@api_router.post("/auth/setup")
async def setup_pin(body: PinInput):
    if not body.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must contain only digits")
    existing = await db.vault_config.find_one({"key": "master_pin"})
    if existing:
        raise HTTPException(status_code=400, detail="PIN already set")
    await db.vault_config.insert_one({"key": "master_pin", "pin_hash": hash_pin(body.pin), "token_ver": 0})
    return {"token": create_token(0)}


@api_router.post("/auth/unlock")
async def unlock(body: PinInput):
    vault = await db.vault_config.find_one({"key": "master_pin"})
    if not vault:
        raise HTTPException(status_code=400, detail="PIN not set yet")

    attempt = await db.login_attempts.find_one({"identifier": "vault"})
    now = datetime.now(timezone.utc)
    if attempt and attempt.get("count", 0) >= MAX_ATTEMPTS:
        cycles = attempt["count"] // MAX_ATTEMPTS
        lock_min = min(LOCKOUT_MINUTES * (2 ** (cycles - 1)), 1440)
        locked_until = datetime.fromisoformat(attempt["last_attempt"]) + timedelta(minutes=lock_min)
        if now < locked_until:
            remaining = int((locked_until - now).total_seconds() // 60) + 1
            raise HTTPException(status_code=429, detail=f"Too many wrong attempts. Try again in {remaining} min")

    if not verify_pin(body.pin, vault["pin_hash"]):
        await db.login_attempts.update_one(
            {"identifier": "vault"},
            {"$inc": {"count": 1}, "$set": {"last_attempt": now.isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Wrong PIN")

    await db.login_attempts.delete_one({"identifier": "vault"})
    return {"token": create_token(int(vault.get("token_ver", 0)))}


@api_router.post("/auth/change-pin")
async def change_pin(body: ChangePinInput, _: str = Depends(require_auth)):
    if not body.new_pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must contain only digits")
    vault = await db.vault_config.find_one({"key": "master_pin"})
    if not vault or not verify_pin(body.old_pin, vault["pin_hash"]):
        raise HTTPException(status_code=401, detail="Current PIN is wrong")
    await db.vault_config.update_one(
        {"key": "master_pin"},
        {"$set": {"pin_hash": hash_pin(body.new_pin)}, "$inc": {"token_ver": 1}},
    )
    return {"message": "PIN changed"}


# ---------- Credentials ----------

@api_router.get("/credentials", response_model=List[Credential])
async def list_credentials(_: str = Depends(require_auth)):
    docs = await db.credentials.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for d in docs:
        if d.get("password"):
            d["password"] = fernet.decrypt(d["password"].encode()).decode()
    return docs


@api_router.post("/credentials", response_model=Credential)
async def create_credential(body: CredentialCreate, _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc).isoformat()
    cred = Credential(**body.model_dump(), created_at=now, updated_at=now)
    doc = cred.model_dump()
    if doc["password"]:
        doc["password"] = fernet.encrypt(doc["password"].encode()).decode()
    await db.credentials.insert_one(doc)
    return cred


@api_router.put("/credentials/{cred_id}", response_model=Credential)
async def update_credential(cred_id: str, body: CredentialCreate, _: str = Depends(require_auth)):
    existing = await db.credentials.find_one({"id": cred_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Credential not found")
    update = body.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    plain_password = update["password"]
    if update["password"]:
        update["password"] = fernet.encrypt(update["password"].encode()).decode()
    await db.credentials.update_one({"id": cred_id}, {"$set": update})
    existing.update(update)
    existing["password"] = plain_password
    return existing


@api_router.delete("/credentials/{cred_id}")
async def delete_credential(cred_id: str, _: str = Depends(require_auth)):
    result = await db.credentials.delete_one({"id": cred_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Credential not found")
    await delete_parent_documents("credential", cred_id)
    return {"message": "Deleted"}


# ---------- Insurance ----------

@api_router.get("/insurance", response_model=List[Insurance])
async def list_insurance(_: str = Depends(require_auth)):
    return await db.insurance.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api_router.post("/insurance", response_model=Insurance)
async def create_insurance(body: InsuranceCreate, _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc).isoformat()
    policy = Insurance(**body.model_dump(), created_at=now, updated_at=now)
    await db.insurance.insert_one(policy.model_dump())
    return policy


@api_router.put("/insurance/{policy_id}", response_model=Insurance)
async def update_insurance(policy_id: str, body: InsuranceCreate, _: str = Depends(require_auth)):
    existing = await db.insurance.find_one({"id": policy_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
    update = body.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.insurance.update_one({"id": policy_id}, {"$set": update})
    existing.update(update)
    return existing


FREQ_MONTHS = {"Yearly": 12, "Half-Yearly": 6, "Quarterly": 3, "Monthly": 1}

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    max_day = 29 if m == 2 and (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else MONTH_DAYS[m - 1]
    return date(y, m, min(d.day, max_day))


@api_router.post("/insurance/{policy_id}/mark-paid")
async def mark_premium_paid(policy_id: str, _: str = Depends(require_auth)):
    policy = await db.insurance.find_one({"id": policy_id}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if not policy.get("premium_due_date"):
        raise HTTPException(status_code=400, detail="No premium due date set")
    months = FREQ_MONTHS.get(policy.get("premium_frequency", "Yearly"))
    current = date.fromisoformat(policy["premium_due_date"])
    new_due = add_months(current, months).isoformat() if months else ""
    today = date.today().isoformat()
    update = {
        "premium_due_date": new_due,
        "last_paid_on": today,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.insurance.update_one({"id": policy_id}, {"$set": update})
    await db.premium_payments.insert_one({
        "id": str(uuid.uuid4()),
        "policy_id": policy_id,
        "paid_on": today,
        "due_date": policy["premium_due_date"],
        "amount": policy.get("premium_amount"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    policy.update(update)
    return policy


@api_router.get("/insurance/{policy_id}/payments")
async def list_payments(policy_id: str, _: str = Depends(require_auth)):
    return await db.premium_payments.find({"policy_id": policy_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.post("/insurance/{policy_id}/undo-paid")
async def undo_premium_paid(policy_id: str, _: str = Depends(require_auth)):
    policy = await db.insurance.find_one({"id": policy_id}, {"_id": 0})
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    payment = await db.premium_payments.find_one({"policy_id": policy_id}, sort=[("created_at", -1)])
    if not payment:
        raise HTTPException(status_code=400, detail="No payment to undo")
    await db.premium_payments.delete_one({"id": payment["id"]})
    prev = await db.premium_payments.find_one({"policy_id": policy_id}, sort=[("created_at", -1)])
    update = {
        "premium_due_date": payment["due_date"],
        "last_paid_on": prev["paid_on"] if prev else "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.insurance.update_one({"id": policy_id}, {"$set": update})
    policy.update(update)
    return policy


@api_router.delete("/insurance/{policy_id}")
async def delete_insurance(policy_id: str, _: str = Depends(require_auth)):
    result = await db.insurance.delete_one({"id": policy_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Policy not found")
    await delete_parent_documents("insurance", policy_id)
    await db.premium_payments.delete_many({"policy_id": policy_id})
    return {"message": "Deleted"}


# ---------- Cards ----------

@api_router.get("/cards", response_model=List[CardItem])
async def list_cards(_: str = Depends(require_auth)):
    docs = await db.cards.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for d in docs:
        d["card_number"] = dec(d.get("card_number", ""))
        d["cvv"] = dec(d.get("cvv", ""))
    return docs


@api_router.post("/cards", response_model=CardItem)
async def create_card(body: CardCreate, _: str = Depends(require_auth)):
    now = datetime.now(timezone.utc).isoformat()
    card = CardItem(**body.model_dump(), created_at=now, updated_at=now)
    doc = card.model_dump()
    doc["card_number"] = enc(doc["card_number"])
    doc["cvv"] = enc(doc["cvv"])
    await db.cards.insert_one(doc)
    return card


@api_router.put("/cards/{card_id}", response_model=CardItem)
async def update_card(card_id: str, body: CardCreate, _: str = Depends(require_auth)):
    existing = await db.cards.find_one({"id": card_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Card not found")
    update = body.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    plain_number, plain_cvv = update["card_number"], update["cvv"]
    update["card_number"] = enc(update["card_number"])
    update["cvv"] = enc(update["cvv"])
    await db.cards.update_one({"id": card_id}, {"$set": update})
    existing.update(update)
    existing["card_number"], existing["cvv"] = plain_number, plain_cvv
    return existing


@api_router.delete("/cards/{card_id}")
async def delete_card(card_id: str, _: str = Depends(require_auth)):
    result = await db.cards.delete_one({"id": card_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Card not found")
    await delete_parent_documents("card", card_id)
    return {"message": "Deleted"}


@api_router.get("/members")
async def list_members(_: str = Depends(require_auth)):
    names = set()
    for coll in (db.credentials, db.cards, db.insurance):
        names.update(await coll.distinct("member_name"))
    return sorted(n for n in names if n)


# ---------- Documents ----------

EXT_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}
INLINE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_DOC_EXT = set(EXT_CONTENT_TYPES)
MAX_DOC_SIZE = 10 * 1024 * 1024


def safe_filename(name: str) -> str:
    name = Path(name or "file").name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:100] or "file"


async def delete_parent_documents(parent_type: str, parent_id: str):
    async for d in db.documents.find({"parent_type": parent_type, "parent_id": parent_id}):
        try:
            await fs_bucket.delete(ObjectId(d["gridfs_id"]))
        except Exception:
            pass
    await db.documents.delete_many({"parent_type": parent_type, "parent_id": parent_id})


@api_router.post("/documents/upload")
async def upload_document(parent_type: str, parent_id: str, file: UploadFile = File(...), _: str = Depends(require_auth)):
    if parent_type not in ("credential", "card", "insurance"):
        raise HTTPException(status_code=400, detail="Invalid parent type")
    fname = safe_filename(file.filename)
    ext = Path(fname).suffix.lower()
    if ext not in ALLOWED_DOC_EXT:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")
    data = await file.read()
    if len(data) > MAX_DOC_SIZE:
        raise HTTPException(status_code=400, detail="Max file size is 10 MB")
    gridfs_id = await fs_bucket.upload_from_stream(fname, fernet.encrypt(data))
    doc = {
        "id": str(uuid.uuid4()),
        "parent_type": parent_type,
        "parent_id": parent_id,
        "filename": fname,
        "content_type": EXT_CONTENT_TYPES[ext],
        "size": len(data),
        "gridfs_id": str(gridfs_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(dict(doc))
    doc.pop("gridfs_id")
    doc.pop("_id", None)
    return doc


@api_router.get("/documents")
async def list_documents(parent_type: str, parent_id: str, _: str = Depends(require_auth)):
    return await db.documents.find(
        {"parent_type": parent_type, "parent_id": parent_id}, {"_id": 0, "gridfs_id": 0}
    ).sort("created_at", -1).to_list(200)


@api_router.get("/documents/counts")
async def document_counts(parent_type: str, _: str = Depends(require_auth)):
    rows = await db.documents.aggregate([
        {"$match": {"parent_type": parent_type}},
        {"$group": {"_id": "$parent_id", "count": {"$sum": 1}}},
    ]).to_list(1000)
    return {r["_id"]: r["count"] for r in rows}


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, _: str = Depends(require_auth)):
    doc = await db.documents.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    fname = safe_filename(doc["filename"])
    ext = Path(fname).suffix.lower()
    media = EXT_CONTENT_TYPES.get(ext, "application/octet-stream")
    disposition = "inline" if ext in INLINE_EXTS else "attachment"
    stream = await fs_bucket.open_download_stream(ObjectId(doc["gridfs_id"]))
    data = fernet.decrypt(await stream.read())
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, _: str = Depends(require_auth)):
    doc = await db.documents.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        await fs_bucket.delete(ObjectId(doc["gridfs_id"]))
    except Exception:
        pass
    await db.documents.delete_one({"id": doc_id})
    return {"message": "Deleted"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def create_indexes():
    await db.credentials.create_index("id")
    await db.insurance.create_index("id")
    await db.cards.create_index("id")
    await db.documents.create_index([("parent_type", 1), ("parent_id", 1)])
    await db.premium_payments.create_index("policy_id")
    await db.login_attempts.create_index("identifier")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
