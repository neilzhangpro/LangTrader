import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
load_dotenv()

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("dbHost"),
            port=os.getenv("dbPort"),
            database=os.getenv("dbBase"),
            user=os.getenv("dbUser"),
            password=os.getenv("dbPass")
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, query, params=None):
        self.cursor.execute(query, params)
        self.conn.commit()
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()
        self.conn.close()