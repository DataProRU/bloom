from database import Wallets


async def update_wallets_on_google_sheet(db, worksheet):
    wallets = await db.fetch_all(Wallets.__table__.select())

    wallet_names = []
    wallet_balances = []

    for wallet in wallets:
        wallet_names.append([wallet.name])
        wallet_balances.append([float(wallet.balance)])

    worksheet.batch_clear(['C7:C', 'D7:D'])

    if wallet_names:
        worksheet.update('C7', wallet_names)
        worksheet.update('D7', wallet_balances)
