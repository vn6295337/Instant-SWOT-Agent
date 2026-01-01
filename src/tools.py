import sqlite3

def get_strategy_context(strategy_name: str) -> str:
    """MCP Tool Function - Query strategy database"""
    db_path = 'data/strategy.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT description FROM focus_areas WHERE strategy_name = ?',
        (strategy_name,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "No such strategy found."