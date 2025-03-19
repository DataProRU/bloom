from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class UserInDB(BaseModel):
    username: str
    hashed_password: str
    role: str


class User(BaseModel):
    username: str
    password: str
    role: str


class UserCreate(User):
    username: str
    password: str
    role: str


class UpdateUserRole(BaseModel):
    role: str
