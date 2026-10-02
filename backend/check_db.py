import sqlite3

con = sqlite3.connect('ai_controls.db')
cur = con.cursor()

print("Tables in ai_controls.db:")
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print(" ", row[0])

print("\nCounts:")
for table in ['source_transactions', 'archive_transactions', 'control_runs', 'control_run_records']:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]}")
    except Exception as e:
        print(f"  {table}: ERROR {e}")

print("\nControl Runs in DB:")
try:
    for row in cur.execute("SELECT id, status, total_records, eligible_records, archived_records, cleaned_records FROM control_runs"):
        print(" ", row)
except Exception as e:
    print("  ERROR:", e)

con.close()
