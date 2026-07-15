import os
from app import app, db

# 1. Define the path to the database
db_path = os.path.join('database', 'wellbeing.db')

# 2. Delete the old file if it exists
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f"✅ Old database '{db_path}' deleted successfully.")
    except PermissionError:
        print("❌ Error: The database is currently open. STOP 'python app.py' first!")
        exit()
else:
    print(f"ℹ️ No existing database found at '{db_path}'.")

# 3. Create the new database with the updated columns
with app.app_context():
    db.create_all()
    print("✅ New database created with 'Consent' columns!")
    print("🚀 You can now run 'python app.py' and Register.")