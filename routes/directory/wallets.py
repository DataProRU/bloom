import logging

from database import Wallets, WebUser, get_db
from dependencies import get_token_from_cookie, get_current_user
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
templates = Jinja2Templates(directory="templates/directory/")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.get("/wallets/")
async def get_wallets(request: Request, db: AsyncSession = Depends(get_db)):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    wallets = await db.fetch_all(Wallets.__table__.select())
    users = await db.fetch_all(WebUser.__table__.select())
    return templates.TemplateResponse("wallets.html", {"request": request, "wallets": wallets, "users": users})


@router.delete("/wallets/{id}/")
async def delete_wallet(
        id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return JSONResponse({"detail": "Access denied"}, status_code=403)

    query = Wallets.__table__.delete().where(Wallets.id == id)
    result = await db.execute(query)

    if result:
        return JSONResponse({"detail": "Wallet deleted successfully"})
    return JSONResponse({"detail": "Wallet not found"}, status_code=404)


@router.post("/wallets/{id}/edit/")
async def update_wallet(
        request: Request,
        id: int,
        name: str = Form(...),
        username: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    logger.info("checking")

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        wallet = await db.fetch_one(Wallets.__table__.select().where(Wallets.id == id))
        if not wallet:
            return templates.TemplateResponse("not_found.html", {"request": request})

        query = (
            update(Wallets.__table__)
            .where(Wallets.id == id)
            .values(name=name, username=username)
        )
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error updating wallet: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/wallets/", status_code=303)


@router.post("/wallets/add/")
async def add_wallet(
        request: Request,
        name: str = Form(...),
        username: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    if payload.get("role") != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        query = Wallets.__table__.insert().values(name=name, username=username, balance=0)
        await db.execute(query)
        logger.info(f"Wallet added successfully: {name}")
    except Exception as e:
        logger.error(f"Error adding wallet: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/wallets/", status_code=303)


@router.post("/wallets/{id}/delete/")
async def delete_wallet_post(
        id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    if payload.get("role") != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    query = Wallets.__table__.delete().where(Wallets.id == id)
    await db.execute(query)

    return RedirectResponse(url="/wallets/", status_code=303)