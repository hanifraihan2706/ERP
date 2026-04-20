import database as db
import os
from dotenv import load_dotenv

load_dotenv()

try:
    # Try to select the column specifically
    res = db.get_supabase().table('tabel_transaksi_sales').select('customer_name, customer_email').limit(1).execute()
    print("Success: column 'customer_email' exists.")
except Exception as e:
    print(f"Error: {e}")
