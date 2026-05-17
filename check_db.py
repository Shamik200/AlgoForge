import sqlite3
import json

def analyze_db():
    conn = sqlite3.connect('data/oms_orders.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    if ('orders',) in tables:
        cursor.execute("SELECT * FROM orders")
        orders = cursor.fetchall()
        print(f"Total orders: {len(orders)}")
        for o in orders[:5]:
            print(o)
            
    conn.close()

if __name__ == "__main__":
    analyze_db()
