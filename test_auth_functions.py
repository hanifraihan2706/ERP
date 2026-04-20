import database
import os
from dotenv import load_dotenv

load_dotenv()

print("Testing database.py functions...")
try:
    print(f"login_user exists: {'login_user' in dir(database)}")
    print(f"daftar_user exists: {'daftar_user' in dir(database)}")
    print(f"logout_user exists: {'logout_user' in dir(database)}")
except Exception as e:
    print(f"Error checking functions: {e}")
