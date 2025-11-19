"""
Database Schemas for the Portfolio app

Each Pydantic model corresponds to a MongoDB collection.
The collection name is the lowercase of the class name.

Collections:
- User: authentication + identity
- Profile: public portfolio profile keyed by username
- Project: portfolio projects
- Blog: blog posts
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, description="Unique handle for public profile URL")
    email: EmailStr
    password_hash: str = Field(..., description="Hashed password")
    display_name: Optional[str] = Field(None, description="Name to show on profile")
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    verified: bool = False

class Profile(BaseModel):
    username: str = Field(..., description="Owner username (unique)")
    headline: Optional[str] = None
    about: Optional[str] = None
    socials: Optional[dict] = Field(default_factory=dict, description="Map of social links")
    theme: Optional[str] = Field(default="holo", description="Theme key for UI")

class Project(BaseModel):
    username: str = Field(..., description="Owner username")
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    image_url: Optional[str] = None
    featured: bool = False

class Blog(BaseModel):
    username: str = Field(..., description="Owner username")
    slug: str = Field(..., description="URL-friendly identifier")
    title: str
    content: str
    cover_image: Optional[str] = None
    published: bool = False
    published_at: Optional[datetime] = None
