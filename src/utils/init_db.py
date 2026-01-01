import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "../../data/strategy.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS focus_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
)
""")

strategies = [
    ("Cost Leadership", "Focus on pricing efficiency, economies of scale, and supply chain optimization to achieve lowest cost position in the industry."),
    ("Differentiation", "Focus on unique product features, brand strength, innovation, and customer experience to command premium pricing."),
    ("Focus/Niche", "Focus on serving a specific market segment exceptionally well, with deep expertise and tailored solutions."),
]

for strategy_name, description in strategies:
    cursor.execute("""
    INSERT OR IGNORE INTO focus_areas (strategy_name, description)
    VALUES (?, ?)
    """, (strategy_name, description))

conn.commit()
conn.close()

print("Database initialized successfully!")
print(f"Database created at: {db_path}")