from datetime import datetime
from decimal import Decimal
from typing import Optional
import logging
import gspread
from sqlalchemy.orm import Session

from database import TgUser, get_db, PaymentTypes, Operations, Categories, Articles, Wallets
from databases import Database
from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pytz import timezone
from dependencies import get_token_from_cookie
from fastapi.responses import RedirectResponse

app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация gspread
try:
    gc = gspread.service_account(filename="credentials.json")
    sht2 = gc.open_by_url(
        'https://docs.google.com/spreadsheets/d/1dvW23dQyYB0D6afUYAj1L6mp-xl7DJ5W1GFLIHOxxp0/edit?gid=429053782#gid=429053782'
    )
    worksheet = sht2.get_worksheet(0)
except Exception as e:
    print(f"Ошибка при инициализации gspread: {str(e)}")

moscow_tz = timezone('Europe/Moscow')

def format_date(date):
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    return date_obj.strftime("%d.%m.%Y")

from fastapi import Query

@router.get("/tg_bot_add", response_class=HTMLResponse)
async def get_form(
    request: Request,
    username: str = Query(...),  # Обязательный параметр
    db: Database = Depends(get_db),
):
    token = get_token_from_cookie(request)
    print(token)
    if isinstance(token, RedirectResponse):
        return token

    users_data = await db.fetch_all(TgUser.__table__.select())
    payment_types = await db.fetch_all(PaymentTypes.__table__.select())
    operations = await db.fetch_all(Operations.__table__.select())
    categories = await db.fetch_all(Categories.__table__.select())
    articles = await db.fetch_all(Articles.__table__.select())
    wallets = await db.fetch_all(Wallets.__table__.select())

    # Преобразуем данные в нужный формат
    category_articles = {}
    for article in articles:
        category_name = article.category_name
        if category_name not in category_articles:
            category_articles[category_name] = []
        category_articles[category_name].append(article.title)

    operation_categories = {}
    for category in categories:
        operation_name = category.operation_name
        if operation_name not in operation_categories:
            operation_categories[operation_name] = []
        operation_categories[operation_name].append(category.name)

    return templates.TemplateResponse(
        "bot/form.html",
        {
            "request": request,
            "users": users_data,
            "username": username,
            "payment_types": payment_types,
            "operations": operations,
            "operation_categories": operation_categories,
            "category_articles": category_articles,
            "wallets": wallets,
        },
    )


@router.post("/submit", response_class=HTMLResponse)
async def submit_form(
        request: Request,
        username: str = Form(...),
        date: str = Form(...),
        operation_type: str = Form(...),
        accounting_type: Optional[str] = Form(None),
        account_type: Optional[str] = Form(None),
        date_finish: Optional[str] = Form(None),
        amount: float = Form(...),
        payment_type: Optional[str] = Form(None),
        comment: str = Form(...),
        wallet_from: Optional[str] = Form(None),
        wallet_to: Optional[str] = Form(None),
        wallet: Optional[str] = Form(None),
        db: Database = Depends(get_db),
):
    try:
        current_time = datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M:%S")
        username = username.replace("%20", " ")

        # Сначала добавляем данные, потом форматируем только добавленные строки
        formatted_operation_date = format_date(date)

        if operation_type == "Перемещение":
            formatted_finish_date = ""
        else:
            formatted_finish_date = format_date(date_finish) if date_finish else ""
            if operation_type == "Расход":
                amount = -amount

        new_row = [
            current_time,
            username,
            formatted_operation_date,
            operation_type,
            accounting_type,
            account_type,
            formatted_finish_date,
            amount,
            payment_type,
            comment,
        ]

        if operation_type == "Перемещение":
            new_row.append(wallet_from)
            new_row[7] = -new_row[7]
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
            new_row[-1] = wallet_to
            new_row[7] = -new_row[7]
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
            wallet_from_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == wallet_from))
            if wallet_from_instance:
                new_balance = wallet_from_instance.balance - Decimal(amount)
                query = Wallets.__table__.update().where(Wallets.name == wallet_from).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet not found")
            wallet_to_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == wallet_to))
            if wallet_to_instance:
                new_balance = wallet_to_instance.balance + Decimal(amount)
                query = Wallets.__table__.update().where(Wallets.name == wallet_to).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet not found")
        else:
            new_row.append(wallet)
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
            wallet_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == wallet))
            if wallet_instance:
                new_balance = wallet_instance.balance + Decimal(amount)
                query = Wallets.__table__.update().where(Wallets.name == wallet).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet not found")

        # Получаем текущий размер таблицы
        num_rows = len(worksheet.get_all_values())
        num_cols = len(worksheet.get_all_values()[0]) if num_rows > 0 else 0

        # Форматируем только если столбцы существуют
        if num_cols >= 1:  # Столбец A
            worksheet.format(f'A1:A{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy HH:mm:ss"
                }
            })

        if num_cols >= 3:  # Столбец C
            worksheet.format(f'C1:C{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        if num_cols >= 7:  # Столбец G
            worksheet.format(f'G1:G{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        # Вывод в консоль для отладки
        print(f"\nДобавлена новая запись. Текущий размер таблицы: {num_rows} строк, {num_cols} столбцов")

        return templates.TemplateResponse(
            "bot/success.html", {"request": request, "message": "Данные успешно добавлены!"}
        )
    except Exception as e:
        print(f"Ошибка при добавлении строки: {str(e)}")
        logger.error(f"Ошибка: {e}")
        return templates.TemplateResponse(
            "bot/error.html", {"request": request, "message": f"Произошла ошибка: {str(e)}"}
        )

app.include_router(router)
