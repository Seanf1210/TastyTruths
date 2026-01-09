import sqlite3

conn = sqlite3.connect('instance/site.db')
cursor = conn.cursor()

# Check users table columns
print("=" * 50)
print("Users table columns:")
print("=" * 50)
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

print("\n" + "=" * 50)
print("Recipes table columns:")
print("=" * 50)
cursor.execute("PRAGMA table_info(recipes)")
columns = cursor.fetchall()
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()
