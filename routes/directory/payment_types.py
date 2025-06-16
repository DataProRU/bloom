import logging

from database import PaymentTypes, get_db
from dependencies import get_token_from_cookie, get_current_user
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()
templates = Jinja2Templates(directory="templates/directory/")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.get("/payment_types/")
async def get_payment_types(request: Request, db: AsyncSession = Depends(get_db)):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    role = payload.get("role")
    if role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        payment_types = await db.fetch_all(PaymentTypes.__table__.select())
    except Exception as e:
        logger.error(f"Error fetching payment types: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return templates.TemplateResponse("payment_types.html", {"request": request, "payment_types": payment_types})


@router.delete("/payment_types/{id}/")
async def delete_payment_type(
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

    try:
        stmt = select(Payment_types).where(Payment_types.id == id)
        result = await db.execute(stmt)
        payment_type = result.scalar_one_or_none()

        if payment_type:
            await db.delete(payment_type)
            await db.commit()
            return JSONResponse({"detail": "Payment type deleted successfully"})
        return JSONResponse({"detail": "Payment type not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error deleting payment type: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/payment_types/{id}/edit/")
async def update_payment_type(
        request: Request,
        id: int,
        name: str = Form(...),
        db: AsyncSession = Depends(get_db),
):
    token = get_token_from_cookie(request)
    if isinstance(token, RedirectResponse):
        return token

    payload = get_current_user(token)
    if isinstance(payload, RedirectResponse):
        return payload

    user_role = payload.get("role")
    if user_role != "admin":
        return templates.TemplateResponse("not_access.html", {"request": request})

    try:
        # Проверяем, существует способ оплаты
        payment_type = await db.fetch_one(PaymentTypes.__table__.select().where(PaymentTypes.id == id))
        if not payment_type:
            return templates.TemplateResponse("not_found.html", {"request": request})

        # Обновляем способ оплаты
        query = (
            update(PaymentTypes.__table__)
            .where(PaymentTypes.id == id)
            .values(name=name)
        )
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error updating payment type: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/payment_types/", status_code=303)


@router.post("/payment_types/add/")
async def add_payment_type(
        request: Request,
        name: str = Form(...),
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
        payment_types = PaymentTypes(name=name)  # Do not set the id manually
        query = PaymentTypes.__table__.insert().values(name=name)
        await db.execute(query)
        logger.info(f"Payment type added successfully: {payment_types}")
    except Exception as e:
        logger.error(f"Error adding payment type: {e}")
        await db.rollback()  # Rollback the transaction in case of an error
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/payment_types/", status_code=303)


@router.post("/payment_types/{id}/delete/")
async def delete_payment_type_post(
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

    try:
        query = PaymentTypes.__table__.delete().where(PaymentTypes.id == id)
        await db.execute(query)
    except Exception as e:
        logger.error(f"Error deleting payment type: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return RedirectResponse(url="/payment_types/", status_code=303)
