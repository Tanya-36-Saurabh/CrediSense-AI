
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

conn.execute("""
CREATE TABLE IF NOT EXISTS card_rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    reward_percent REAL NOT NULL
        CHECK(reward_percent >= 0 AND reward_percent <= 100),
    FOREIGN KEY (card_id) REFERENCES cards(id),
    UNIQUE(card_id, category)
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS reward_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT NOT NULL,
    card_name TEXT NOT NULL,
    category TEXT NOT NULL,
    reward_percent REAL NOT NULL
        CHECK(reward_percent >= 0 AND reward_percent <= 100),
    UNIQUE(bank_name, card_name, category)
)
""")

demo_rewards = [
    ("HDFC", "Millennia", "Shopping", 5.0),
    ("HDFC", "Millennia", "Food", 1.0),
    ("HDFC", "Millennia", "Travel", 1.0),
    ("ICICI", "Coral", "Shopping", 1.0),
    ("ICICI", "Coral", "Food", 1.0),
    ("ICICI", "Coral", "Travel", 2.0),
    ("SBI", "SimplyCLICK", "Shopping", 2.0),
    ("SBI", "SimplyCLICK", "Food", 1.0),
    ("SBI", "SimplyCLICK", "Travel", 2.0)
]

conn.executemany(
    """
    INSERT OR IGNORE INTO reward_catalog
    (bank_name, card_name, category, reward_percent)
    VALUES (?, ?, ?, ?)
    """,
    demo_rewards
)

conn.commit()

print("Demo rewards added successfully!")

columns = conn.execute(
    "PRAGMA table_info(reward_catalog)"
).fetchall()

column_names = [column[1] for column in columns]

if "max_cashback" not in column_names:
    conn.execute("""
        ALTER TABLE reward_catalog
        ADD COLUMN max_cashback REAL
    """)

conn.execute("""
    UPDATE reward_catalog
    SET max_cashback = 500
    WHERE bank_name = 'HDFC'
    AND card_name = 'Millennia'
    AND category = 'Shopping'
""")

conn.commit()

print("Reward caps updated successfully!")

conn.close()

print("Database created successfully!")
