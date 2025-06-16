from pydantic import BaseModel
from fastapi import Form


class UserCreate(BaseModel):
    username: str
    password: str
    role: str

    @classmethod
    def as_form(
            cls,
            username: str = Form(...),
            password: str = Form(...),
            role: str = Form(...),
    ):
        return cls(username=username, password=password, role=role)


class UserLogin(BaseModel):
    username: str
    password: str
