
import sqlite3

conn = sqlite3.connect("credisense.db")

conn.execute("""
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    card_name TEXT NOT NULL,
    credit_limit REAL NOT NULL,
    outstanding REAL DEFAULT 0
)
""")


conn.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    merchant TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    transaction_date TEXT NOT NULL,
    FOREIGN KEY (card_id) REFERENCES cards(id)
)
""")

conn.commit()
conn.close()

print("Database created successfully!")
