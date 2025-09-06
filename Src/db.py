import sqlite3

conn = sqlite3.connect('deals.db', check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS deals (
    deal_id TEXT PRIMARY KEY,
    seller TEXT,
    buyer TEXT,
    amount INTEGER,
    details TEXT,
    status TEXT,
    seller_joined INTEGER DEFAULT 0,
    buyer_joined INTEGER DEFAULT 0
)
''')
conn.commit()

def add_deal(deal_id, seller, buyer, amount, details, status="pending"):
    c.execute("INSERT INTO deals VALUES (?,?,?,?,?,?,0,0)", (deal_id, seller, buyer, amount, details, status))
    conn.commit()

def update_deal(deal_id, **kwargs):
    fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values())
    values.append(deal_id)
    c.execute(f"UPDATE deals SET {fields} WHERE deal_id = ?", values)
    conn.commit()

def get_deal(deal_id):
    c.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
    return c.fetchone()

def get_pending_deals():
    c.execute("SELECT * FROM deals WHERE status='pending'")
    return c.fetchall()
