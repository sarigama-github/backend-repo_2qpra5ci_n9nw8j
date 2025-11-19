import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId

from database import db, create_document, get_documents
from schemas import User as UserSchema, Profile as ProfileSchema, Project as ProjectSchema, Blog as BlogSchema

app = FastAPI(title="Multi-User Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def collection(name: str):
    return db[name]


def to_public(doc: dict):
    if not doc:
        return doc
    doc = {**doc}
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


# Health
@app.get("/")
def read_root():
    return {"message": "Portfolio API running"}

@app.get("/test")
def test_database():
    status = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set" if not os.getenv("DATABASE_URL") else "✅ Set",
        "database_name": "❌ Not Set" if not os.getenv("DATABASE_NAME") else "✅ Set",
        "collections": []
    }
    try:
        cols = db.list_collection_names()
        status["database"] = "✅ Connected"
        status["collections"] = cols
    except Exception as e:
        status["database"] = f"❌ Error: {str(e)[:80]}"
    return status

# Auth (simple username+password-hash signup/login)
class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/signup")
def signup(payload: SignupRequest):
    # very basic: store hash as plain placeholder for now (client should hash)
    users = collection("user")
    if users.find_one({"username": payload.username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    if users.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = UserSchema(
        username=payload.username,
        email=payload.email,
        password_hash=payload.password,  # In production: hash properly
        display_name=payload.display_name or payload.username,
        verified=False,
    )
    user_id = create_document("user", user)

    # create empty profile
    profile = ProfileSchema(username=payload.username, headline="", about="", socials={}, theme="holo")
    create_document("profile", profile)

    return {"id": user_id, "username": payload.username}

@app.post("/auth/login")
def login(payload: LoginRequest):
    users = collection("user")
    user = users.find_one({"username": payload.username, "password_hash": payload.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"ok": True, "username": payload.username}

# Public fetch for a username
@app.get("/profiles/{username}")
def get_profile(username: str):
    prof = collection("profile").find_one({"username": username})
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    projects = list(collection("project").find({"username": username}).sort("featured", -1))
    blogs = list(collection("blog").find({"username": username, "published": True}).sort("published_at", -1))
    return {
        "profile": to_public(prof),
        "projects": [to_public(p) for p in projects],
        "blogs": [to_public(b) for b in blogs],
    }

# Manage profile content (simple, keyed by username)
class ProfileUpdate(BaseModel):
    headline: Optional[str] = None
    about: Optional[str] = None
    socials: Optional[dict] = None
    theme: Optional[str] = None

@app.put("/profiles/{username}")
def update_profile(username: str, payload: ProfileUpdate):
    profs = collection("profile")
    prof = profs.find_one({"username": username})
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        update["updated_at"] = datetime.utcnow()
        profs.update_one({"username": username}, {"$set": update})
    prof = profs.find_one({"username": username})
    return to_public(prof)

# Projects
class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    url: Optional[str] = None
    image_url: Optional[str] = None
    featured: bool = False

@app.post("/profiles/{username}/projects")
def create_project(username: str, payload: ProjectCreate):
    proj = ProjectSchema(username=username, **payload.model_dump())
    pid = create_document("project", proj)
    return {"id": pid}

@app.get("/profiles/{username}/projects")
def list_projects(username: str):
    items = list(collection("project").find({"username": username}).sort("featured", -1))
    return [to_public(i) for i in items]

@app.delete("/profiles/{username}/projects/{project_id}")
def delete_project(username: str, project_id: str):
    try:
        oid = ObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    res = collection("project").delete_one({"_id": oid, "username": username})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}

# Blogs
class BlogCreate(BaseModel):
    slug: str
    title: str
    content: str
    cover_image: Optional[str] = None
    published: bool = False

@app.post("/profiles/{username}/blogs")
def create_blog(username: str, payload: BlogCreate):
    data = payload.model_dump()
    if data.get("published"):
        data["published_at"] = datetime.utcnow()
    blog = BlogSchema(username=username, **data)
    bid = create_document("blog", blog)
    return {"id": bid}

@app.get("/profiles/{username}/blogs")
def list_blogs(username: str, published_only: bool = True):
    filt = {"username": username}
    if published_only:
        filt["published"] = True
    items = list(collection("blog").find(filt).sort("published_at", -1))
    return [to_public(i) for i in items]

@app.get("/profiles/{username}/blogs/{slug}")
def get_blog(username: str, slug: str):
    blog = collection("blog").find_one({"username": username, "slug": slug})
    if not blog:
        raise HTTPException(status_code=404, detail="Not found")
    return to_public(blog)

