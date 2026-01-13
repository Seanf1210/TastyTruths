import sqlite3
conn = sqlite3.connect('instance/site.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT version_num FROM alembic_version')
    versions = cursor.fetchall()
    print("Current migrations in database:")
    for row in versions:
        print(f"  {row[0]}")
except Exception as e:
    print(f"Error querying alembic_version: {e}")
conn.close()
