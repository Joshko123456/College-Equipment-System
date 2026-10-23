"""Native PostgreSQL connection and small cursor interface for existing workflows."""
import os,re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row,tuple_row
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env',override=False)
ID_TABLES={'users','student_records','categories','equipment','borrow_requests','notifications','auth_sessions','equipment_units'}
def connection_options():
    host=os.getenv('PGHOST','').strip()
    if not host:raise ValueError('Set PGHOST in .env using the Aiven PostgreSQL host.')
    mode=os.getenv('PGSSLMODE','verify-full')
    if mode not in ('verify-full','verify-ca') and host not in ('localhost','127.0.0.1','::1'):
        raise ValueError('Remote PostgreSQL requires verify-full or verify-ca TLS verification.')
    options=dict(host=host,port=int(os.getenv('PGPORT','5432')),dbname=os.getenv('PGDATABASE','defaultdb'),user=os.getenv('PGUSER','avnadmin'),password=os.getenv('PGPASSWORD',''),sslmode=mode,connect_timeout=15,options='-c timezone=Asia/Manila',application_name='bcc_equipment')
    if mode in ('verify-full','verify-ca'):
        ca=Path(os.getenv('PGSSLROOTCERT','certs/ca.pem'))
        if not ca.is_absolute():ca=ROOT/ca
        if not ca.is_file():raise ValueError('Download Aiven CA certificate to certs/ca.pem or set PGSSLROOTCERT.')
        options['sslrootcert']=str(ca)
    return options

def raw_connect():return psycopg.connect(**connection_options())
class Cursor:
    def __init__(self,conn,dictionary=False):
        self.conn=conn;self.cur=conn.cursor(row_factory=dict_row if dictionary else tuple_row);self.lastrowid=None
    def execute(self,sql,args=()):
        self.lastrowid=None
        match=re.match(r'\s*INSERT INTO\s+(\w+)\b',sql,re.I)
        returning=bool(match and match.group(1).lower() in ID_TABLES and 'RETURNING' not in sql.upper())
        if returning:sql=sql.rstrip().rstrip(';')+' RETURNING id'
        # PostgreSQL aborts transactions after errors. A savepoint lets existing
        # duplicate-serial retry and optional cleanup paths recover safely.
        if self.conn.info.transaction_status==psycopg.pq.TransactionStatus.IDLE:
            self.conn.execute('BEGIN')
        with self.conn.transaction():
            self.cur.execute(sql,tuple(int(x) if isinstance(x,bool) else x for x in args))
            if returning:
                row=self.cur.fetchone()
                if row:self.lastrowid=row['id'] if isinstance(row,dict) else row[0]
        return self
    @property
    def rowcount(self):return self.cur.rowcount
    def fetchone(self):return self.cur.fetchone()
    def fetchall(self):return self.cur.fetchall()
    def close(self):self.cur.close()
class Connection:
    def __init__(self):self.raw=raw_connect()
    def cursor(self,dictionary=False):return Cursor(self.raw,dictionary)
    def commit(self):self.raw.commit()
    def rollback(self):self.raw.rollback()
    def close(self):self.raw.close()
def connect():return Connection()
