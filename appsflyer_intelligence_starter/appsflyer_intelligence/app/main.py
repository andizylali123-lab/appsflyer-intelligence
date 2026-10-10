from datetime import datetime, timedelta, date
from pathlib import Path
import os, io, json, uuid

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'appsflyer.db'}")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_LONG_RANDOM_SECRET")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 12
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

engine_args = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(1000), nullable=False)
    row_count = Column(Integer, default=0)
    columns_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
app = FastAPI(title="AppsFlyer Intelligence API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AuthPayload(BaseModel):
    email: EmailStr
    password: str

def create_token(user_id: int):
    return jwt.encode({"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)

def get_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    error = HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise error
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise error
    return user

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AppsFlyer Intelligence API"}

@app.post("/api/register")
def register(payload: AuthPayload, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must contain at least 8 characters.")
    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, password_hash=pwd_context.hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer", "email": user.email}

@app.post("/api/login")
def login(payload: AuthPayload, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return {"access_token": create_token(user.id), "token_type": "bearer", "email": user.email}

def load_dataset(dataset: Dataset) -> pd.DataFrame:
    path = Path(dataset.stored_path)
    if not path.exists():
        raise HTTPException(404, "Stored dataset file was not found.")
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        return pd.read_excel(path, sheet_name=0)
    except Exception as exc:
        raise HTTPException(422, f"Could not read this dataset: {exc}")

# Normalize common column variants into consistent internal names.
ALIASES = {
    "date": ["date", "install date", "event date", "day", "install_date", "event_time"],
    "media_source": ["media source", "media_source", "mediasource", "source", "partner"],
    "channel": ["channel", "media channel", "marketing channel"],
    "campaign": ["campaign", "campaign name", "campaign_name", "campaign id", "campaign_id"],
    "country": ["country", "geo", "country code", "country_code", "region"],
    "platform": ["platform", "os", "operating system", "operating_system"],
    "installs": ["installs", "install", "total installs"],
    "clicks": ["clicks", "click"],
    "impressions": ["impressions", "impression"],
    "spend": ["spend", "cost", "total cost", "ad spend", "af_cost"],
    "conversions": ["conversions", "conversion", "purchases", "purchase count"],
    "revenue": ["revenue", "total revenue", "af_revenue", "sales"],
    "event_name": ["event name", "event_name", "event", "af event", "af_event"],
    "event_count": ["event count", "event_count", "events", "count"],
}
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    lookup = {str(c).strip().lower().replace("-", " ").replace("_", " "): c for c in out.columns}
    rename = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            key = alias.lower().replace("_", " ")
            if key in lookup:
                rename[lookup[key]] = canonical
                break
    out = out.rename(columns=rename)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["installs", "clicks", "impressions", "spend", "conversions", "revenue", "event_count"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
    for col in ["media_source", "channel", "campaign", "country", "platform", "event_name"]:
        if col in out.columns:
            out[col] = out[col].fillna("Unknown").astype(str)
    return out

def safe_sum(df, col):
    if col not in df.columns:
        return None
    return float(df[col].fillna(0).sum())

def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b

@app.get("/api/me")
def me(user: User = Depends(get_user)):
    return {"id": user.id, "email": user.email}

@app.post("/api/upload")
async def upload_report(file: UploadFile = File(...), user: User = Depends(get_user), db: Session = Depends(get_db)):
    filename = Path(file.filename or "report").name
    suffix = Path(filename).suffix.lower()
    if suffix not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(415, "Upload a CSV, XLSX, or XLS file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than the {MAX_UPLOAD_MB} MB limit.")
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    dataset_id = str(uuid.uuid4())
    path = UPLOAD_DIR / f"{user.id}_{dataset_id}{suffix}"
    path.write_bytes(content)
    try:
        df = pd.read_csv(io.BytesIO(content)) if suffix == ".csv" else pd.read_excel(io.BytesIO(content), sheet_name=0)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not read file. Check the file format. Details: {exc}")
    if df.empty:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "The report has no data rows.")
    normalized = normalize_columns(df)
    record = Dataset(id=dataset_id, user_id=user.id, filename=filename, stored_path=str(path),
                     row_count=len(df), columns_json=json.dumps(list(normalized.columns)))
    db.add(record); db.commit()
    return {"id": dataset_id, "filename": filename, "rows": len(df), "columns": list(normalized.columns),
            "normalized_columns": list(normalized.columns), "message": "Upload processed successfully."}

@app.get("/api/datasets")
def datasets(user: User = Depends(get_user), db: Session = Depends(get_db)):
    rows = db.query(Dataset).filter(Dataset.user_id == user.id).order_by(Dataset.created_at.desc()).all()
    return [{"id": d.id, "filename": d.filename, "rows": d.row_count, "created_at": d.created_at.isoformat()} for d in rows]

def select_df(dataset_id, user, db):
    if dataset_id:
        ds = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == user.id).first()
        if not ds: raise HTTPException(404, "Dataset not found.")
        return normalize_columns(load_dataset(ds)), [ds]
    dslist = db.query(Dataset).filter(Dataset.user_id == user.id).order_by(Dataset.created_at.desc()).all()
    if not dslist: return pd.DataFrame(), []
    frames = [normalize_columns(load_dataset(ds)) for ds in dslist]
    return pd.concat(frames, ignore_index=True, sort=False), dslist

@app.get("/api/analysis")
def analysis(dataset_id: str | None = None, user: User = Depends(get_user), db: Session = Depends(get_db)):
    df, dslist = select_df(dataset_id, user, db)
    if df.empty:
        return {"empty": True, "message": "Upload a report to start analyzing your marketing data.", "datasets": []}
    spend, installs, clicks, impressions = (safe_sum(df, c) for c in ["spend","installs","clicks","impressions"])
    conversions, revenue = safe_sum(df, "conversions"), safe_sum(df, "revenue")
    kpis = {
        "spend": spend, "installs": installs, "clicks": clicks, "impressions": impressions,
        "conversions": conversions, "revenue": revenue,
        "cpi": ratio(spend, installs), "cpc": ratio(spend, clicks), "cpa": ratio(spend, conversions),
        "ctr": ratio(clicks, impressions), "install_rate": ratio(installs, clicks),
        "roas": ratio(revenue, spend)
    }
    def group_metrics(col):
        if col not in df.columns: return []
        grouped = df.groupby(col, dropna=False).agg(
            spend=("spend","sum") if "spend" in df else ("_dummy","size")
        ) if "spend" in df else df.groupby(col, dropna=False).size().to_frame("rows")
        result = []
        for key, part in df.groupby(col, dropna=False):
            result.append({"name": str(key), "spend": safe_sum(part,"spend"), "installs": safe_sum(part,"installs"),
                           "clicks": safe_sum(part,"clicks"), "conversions": safe_sum(part,"conversions"),
                           "revenue": safe_sum(part,"revenue"), "cpi": ratio(safe_sum(part,"spend"),safe_sum(part,"installs")),
                           "roas": ratio(safe_sum(part,"revenue"),safe_sum(part,"spend")), "rows": int(len(part))})
        return sorted(result, key=lambda x: (x["spend"] or 0), reverse=True)[:50]
    daily = []
    if "date" in df.columns:
        valid = df.dropna(subset=["date"]).groupby("date", dropna=True)
        for day, part in valid:
            daily.append({"date": str(day), "spend": safe_sum(part,"spend"), "installs": safe_sum(part,"installs"),
                          "clicks": safe_sum(part,"clicks"), "conversions": safe_sum(part,"conversions"),
                          "revenue": safe_sum(part,"revenue")})
        daily.sort(key=lambda x: x["date"])
    events = group_metrics("event_name")
    return {"empty": False, "kpis": kpis, "media_sources": group_metrics("media_source"),
            "channels": group_metrics("channel"), "campaigns": group_metrics("campaign"),
            "countries": group_metrics("country"), "events": events, "daily": daily,
            "columns": list(df.columns), "rows": int(len(df)),
            "datasets": [{"id": d.id, "filename": d.filename, "rows": d.row_count} for d in dslist],
            "data_quality": {"rows": int(len(df)), "duplicate_rows_exact": int(df.duplicated().sum()),
                             "missing_cells": int(df.isna().sum().sum())},
            "notes": ["Metrics requiring absent columns are shown as unavailable.", "ROAS requires revenue and spend."]}
@app.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, user: User = Depends(get_user), db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == user.id).first()
    if not ds: raise HTTPException(404, "Dataset not found.")
    Path(ds.stored_path).unlink(missing_ok=True)
    db.delete(ds); db.commit()
    return {"message": "Dataset deleted."}

@app.get("/api/demo.csv")
def demo_csv():
    return FileResponse(ROOT / "sample_data" / "demo_appsflyer.csv", filename="demo_appsflyer.csv", media_type="text/csv")

app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
