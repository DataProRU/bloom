import os
from datetime import datetime
from decimal import Decimal
from typing import Optional
import logging
import gspread
from sqlalchemy import desc
from starlette.responses import JSONResponse
from fastapi import status

from database import TgUser, get_db, PaymentTypes, Operations, Categories, Articles, Wallets, FinancialOperations
from databases import Database
from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pytz import timezone
from dependencies import get_token_from_cookie
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from utils.wallets import update_wallets_on_google_sheet

load_dotenv()

app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация gspread
try:
    gc = gspread.service_account(filename=os.getenv('GOOGLE_TABLES_CREDENTIALS_FILE'))
    sht2 = gc.open_by_url(
        os.getenv("GOOGLE_TABLES_URL")
    )
    worksheet = sht2.get_worksheet(0)
    balances_worksheet = sht2.get_worksheet(1)
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
    operations_list = await db.fetch_all(
        FinancialOperations.__table__
        .select()
        .where(FinancialOperations.username == username)
    )

    operations_list.sort(
        key=lambda x: datetime.strptime(x["timestamp"], "%d.%m.%Y %H:%M:%S"),
        reverse=True
    )

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

    financial_operations = [
        {
            'id': row.id,
            'timestamp': row.timestamp,
            'username': row.username,
            'operation_date': row.operation_date,
            'operation_type': row.operation_type,
            'accounting_type': row.accounting_type,
            'account_type': row.account_type,
            'finish_date': row.finish_date,
            'amount': row.amount,
            'payment_type': row.payment_type,
            'comment': row.comment,
            'wallet': row.wallet,
            'wallet_from': row.wallet_from,
            'wallet_to': row.wallet_to
        }
        for row in operations_list
    ]
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
            "financial_operations": financial_operations,
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

        amount_for_db = abs(int(amount))

        query = FinancialOperations.__table__.insert().values(
            timestamp=current_time,
            username=username,
            operation_date=formatted_operation_date,
            operation_type=operation_type,
            accounting_type=accounting_type,
            account_type=account_type,
            finish_date=formatted_finish_date,
            amount=amount_for_db,
            payment_type=payment_type,
            comment=comment,
            wallet=wallet,
            wallet_from=wallet_from,
            wallet_to=wallet_to
        )
        operation_id = await db.execute(query)

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
            row_from = new_row.copy()
            row_from[7] = -abs(row_from[7])
            row_from.append(wallet_from)
            row_from.append(operation_id)
            worksheet.append_row(row_from, value_input_option="USER_ENTERED")

            row_to = new_row.copy()
            row_to[7] = abs(row_to[7])
            row_to.append(wallet_to)
            row_to.append(operation_id)
            worksheet.append_row(row_to, value_input_option="USER_ENTERED")
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
            new_row.append(operation_id)
            worksheet.append_row(new_row, value_input_option="USER_ENTERED")
            wallet_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == wallet))
            if wallet_instance:
                new_balance = wallet_instance.balance + Decimal(amount)
                query = Wallets.__table__.update().where(Wallets.name == wallet).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet not found")

        await update_wallets_on_google_sheet(db, balances_worksheet)

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

@router.patch("/edit/{operation_id}", response_class=JSONResponse)
async def edit_operation(
    request: Request,
    operation_id: int,
    username: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    operation_type: Optional[str] = Form(None),
    accounting_type: Optional[str] = Form(None),
    account_type: Optional[str] = Form(None),
    date_finish: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    payment_type: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    wallet_from: Optional[str] = Form(None),
    wallet_to: Optional[str] = Form(None),
    wallet: Optional[str] = Form(None),
    db: Database = Depends(get_db),
):
    try:
        form_data = {
            "username": username,
            "operation_date": format_date(date) if date else None,
            "operation_type": operation_type,
            "accounting_type": accounting_type,
            "account_type": account_type,
            "finish_date": format_date(date_finish) if date_finish else None,
            "amount": abs(int(Decimal(amount))) if amount else None,
            "payment_type": payment_type,
            "comment": comment,
            "wallet_from": wallet_from,
            "wallet_to": wallet_to,
            "wallet": wallet,
        }

        update_data = {k: v for k, v in form_data.items() if v is not None}

        if not update_data:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": "error", "message": "Нет данных для обновления"}
            )

        fin_operation = await db.fetch_one(FinancialOperations.__table__.select().where(FinancialOperations.id == operation_id))

        old_amount = Decimal(fin_operation.amount) if fin_operation.amount else Decimal(0)

        query = (
            FinancialOperations.__table__
            .update()
            .where(FinancialOperations.id == operation_id)
            .values(**update_data)
        )
        await db.execute(query)

        select_query = FinancialOperations.__table__.select().where(FinancialOperations.id == operation_id)
        row = await db.fetch_one(select_query)

        if not row:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Операция с id={operation_id} не найдена"}
            )

        now_str = datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M:%S")
        amount_decimal = Decimal(row.amount) if row.amount else Decimal(0)
        operation_type = row.operation_type.lower() if row.operation_type else ""

        formatted_operation_date = row.operation_date
        formatted_finish_date = row.finish_date if row.finish_date and operation_type != "перемещение" else ""

        if operation_type == "расход":
            amount_for_sheet = -abs(int(amount_decimal))
        elif operation_type == "приход":
            amount_for_sheet = abs(int(amount_decimal))
        else:
            amount_for_sheet = int(amount_decimal)

        row_data = [
            now_str,
            row.username,
            formatted_operation_date,
            row.operation_type,
            row.accounting_type,
            row.account_type,
            formatted_finish_date,
            amount_for_sheet,
            row.payment_type,
            row.comment,
        ]

        if operation_type == "перемещение":
            row_data.append(row.wallet_from)
            row_data[7] = -abs(int(amount_decimal))
            row_data.append(operation_id)
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

            row_data[-2] = row.wallet_to
            row_data[7] = abs(int(amount_decimal))
            row_data[-1] = operation_id
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

            wallet_from_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet_from))
            if wallet_from_instance:
                new_balance = wallet_from_instance.balance + old_amount - amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet_from).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail=f"Wallet from {row.wallet_from} not found")

            wallet_to_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet_to))
            if wallet_to_instance:
                new_balance = wallet_to_instance.balance - old_amount + amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet_to).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet to not found")
        else:
            row_data.append(row.wallet)
            row_data.append(operation_id)
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

            wallet_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet))
            if wallet_instance:
                if operation_type == "приход":
                    new_balance_amount = amount_for_sheet - old_amount
                else:
                    new_balance_amount = old_amount - abs(amount_for_sheet)
                new_balance = wallet_instance.balance + new_balance_amount
                query = Wallets.__table__.update().where(Wallets.name == row.wallet).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail="Wallet not found")

        await update_wallets_on_google_sheet(db, balances_worksheet)

        num_rows = len(worksheet.get_all_values())
        num_cols = len(worksheet.get_all_values()[0]) if num_rows > 0 else 0

        if num_cols >= 1:
            worksheet.format(f'A1:A{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy HH:mm:ss"
                }
            })

        if num_cols >= 3:
            worksheet.format(f'C1:C{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        if num_cols >= 7:
            worksheet.format(f'G1:G{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        print(f"\nОбновлена запись с id={operation_id}. Текущий размер таблицы: {num_rows} строк, {num_cols} столбцов")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Запись обновлена и добавлена в Google Таблицу",
                "updated_fields": list(update_data.keys())
            }
        )

    except Exception as e:
        logger.error(f"Ошибка при обновлении operation_id {operation_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )

@router.delete("/delete/{operation_id}", response_class=JSONResponse)
async def delete_operation(
    operation_id: int,
    db: Database = Depends(get_db),
):
    try:
        select_query = FinancialOperations.__table__.select().where(FinancialOperations.id == operation_id)
        row = await db.fetch_one(select_query)

        if not row:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "error", "message": f"Операция с id={operation_id} не найдена"}
            )

        now_str = datetime.now(moscow_tz).strftime("%d.%m.%Y %H:%M:%S")
        amount_decimal = Decimal(row.amount) if row.amount else Decimal(0)
        original_operation_type = row.operation_type.lower() if row.operation_type else ""

        formatted_operation_date = row.operation_date
        formatted_finish_date = row.finish_date if row.finish_date and original_operation_type != "перемещение" else ""

        if original_operation_type == "расход":
            amount_for_sheet = -abs(int(amount_decimal))
        elif original_operation_type == "приход":
            amount_for_sheet = abs(int(amount_decimal))
        else:
            amount_for_sheet = int(amount_decimal)

        row_data = [
            now_str,
            row.username,
            formatted_operation_date,
            "УДАЛЕНО",
            row.accounting_type,
            row.account_type,
            formatted_finish_date,
            amount_for_sheet,
            row.payment_type,
            row.comment,
        ]

        if original_operation_type == "перемещение":
            row_data.append(row.wallet_from)
            row_data[7] = -abs(int(amount_decimal))
            row_data.append(operation_id)
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

            row_data[-2] = row.wallet_to
            row_data[7] = abs(int(amount_decimal))
            row_data[-1] = operation_id
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")
        else:
            row_data.append(row.wallet)
            row_data.append(operation_id)
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")

        if original_operation_type == "расход":
            wallet_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet))
            if wallet_instance:
                new_balance = wallet_instance.balance + amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail=f"Wallet {row.wallet} not found")
        elif original_operation_type == "приход":
            wallet_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet))
            if wallet_instance:
                new_balance = wallet_instance.balance - amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail=f"Wallet {row.wallet} not found")
        elif original_operation_type == "перемещение":
            wallet_from_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet_from))
            if wallet_from_instance:
                new_balance = wallet_from_instance.balance + amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet_from).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail=f"Wallet from {row.wallet_from} not found")

            wallet_to_instance = await db.fetch_one(Wallets.__table__.select().where(Wallets.name == row.wallet_to))
            if wallet_to_instance:
                new_balance = wallet_to_instance.balance - amount_decimal
                query = Wallets.__table__.update().where(Wallets.name == row.wallet_to).values(balance=new_balance)
                await db.execute(query)
            else:
                raise HTTPException(status_code=404, detail=f"Wallet to {row.wallet_to} not found")

        num_rows = len(worksheet.get_all_values())
        num_cols = len(worksheet.get_all_values()[0]) if num_rows > 0 else 0

        await update_wallets_on_google_sheet(db, balances_worksheet)

        if num_cols >= 1:
            worksheet.format(f'A1:A{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy HH:mm:ss"
                }
            })

        if num_cols >= 3:
            worksheet.format(f'C1:C{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        if num_cols >= 7:
            worksheet.format(f'G1:G{num_rows}', {
                "numberFormat": {
                    "type": "DATE",
                    "pattern": "dd.mm.yyyy"
                }
            })

        delete_query = FinancialOperations.__table__.delete().where(FinancialOperations.id == operation_id)
        await db.execute(delete_query)

        print(f"\nУдалена запись с id={operation_id}. Текущий размер таблицы: {num_rows} строк, {num_cols} столбцов")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "success",
                "message": "Операция удалена из базы данных и добавлена в Google Таблицу с типом 'УДАЛЕНО'"
            }
        )

    except Exception as e:
        logger.error(f"Ошибка при удалении operation_id {operation_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )

app.include_router(router)
