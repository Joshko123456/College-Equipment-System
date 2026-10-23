from pg_database import raw_connect
if __name__=='__main__':
    try:
        with raw_connect() as conn:
            print('Connected:',conn.execute('SELECT current_database(),version()').fetchone())
            print('TLS:',conn.execute('SELECT ssl,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone())
            count=conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'").fetchone()[0]
            print('Public tables:',count)
    except Exception as exc:
        print('Connection check failed:',type(exc).__name__)
        if 'certificate contains ip address with invalid length' in str(exc).lower():
            print('The TLS certificate hostname check failed. Confirm PGHOST is the Aiven service DNS hostname and PGSSLROOTCERT is its CA certificate.')
            print('PGSSLMODE=verify-ca may connect while still checking the CA, but it skips hostname verification. Do not use it unless you accept that reduced protection.')
        if isinstance(exc,ValueError):
            print(exc)
        print('Check host, port, database, password, CA certificate and Aiven network access. Read AIVEN_POSTGRESQL_SETUP.md.')
        raise SystemExit(1)
