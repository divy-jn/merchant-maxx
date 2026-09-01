import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT tgname FROM pg_trigger WHERE tgname = 'enforce_intent_finality';")
res = cur.fetchall()
print("Triggers found:", res)
conn.close()
