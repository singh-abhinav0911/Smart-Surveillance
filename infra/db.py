from psycopg2.pool import ThreadedConnectionPool
import psycopg2.extras


class Database:

    def __init__(self):

        self.pool = ThreadedConnectionPool(
            minconn=5,
            maxconn=20,
            host="localhost",
            database="surveillance_db",
            user="postgres",
            password="postgres",
            port=5432
        )

    def get_conn(self):
        return self.pool.getconn()

    def release(self, conn):
        self.pool.putconn(conn)