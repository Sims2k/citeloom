"""Quick script to check Zotero database schema."""
import sqlite3
import sys
from pathlib import Path

db_path = Path("C:/Users/Simon/Zotero/zotero.sqlite")
if not db_path.exists():
    print(f"Database not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check items table structure
print("=== items table structure ===")
cursor.execute("PRAGMA table_info(items)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Check if itemData table exists
print("\n=== Checking for itemData table ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='itemData'")
if cursor.fetchone():
    print("  itemData table exists")
    cursor.execute("PRAGMA table_info(itemData)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
else:
    print("  itemData table does not exist")

# Check itemAttachments table
print("\n=== itemAttachments table structure ===")
cursor.execute("PRAGMA table_info(itemAttachments)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()


