"""Read-only MySQL source -> empty PostgreSQL target; all target rows in one transaction."""
import argparse,getpass
from psycopg import sql
from pg_database import raw_connect
TABLES=['users','categories','equipment','student_records','borrow_requests','auth_sessions','notifications','borrower_terms_acceptance','equipment_units','borrow_request_units','equipment_damage','transaction_view_state']
def equipment_image_filename(value):
    if value is None:return None
    filename=str(value).replace('\\','/').rsplit('/',1)[-1]
    return filename or None

def migrate(source,target):
    sc=source.cursor(dictionary=True)
    sc.execute('SHOW FULL TABLES WHERE Table_type = %s',('BASE TABLE',))
    present={next(iter(row.values())) for row in sc.fetchall()}
    extra=present-set(TABLES)
    if extra:raise ValueError('Unexpected source tables: '+', '.join(sorted(extra))+'. Review these before migration; nothing copied.')
    # Prevent target writes while empty-target validation and copy are in progress.
    target.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(sql.SQL(',').join(map(sql.Identifier,TABLES))))
    for table in TABLES:
        if target.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]:
            raise ValueError('Target is not empty: '+table+'. Use a fresh initialized PostgreSQL database.')
    counts={}
    for table in TABLES:
        if table not in present:continue
        sc.execute('SELECT * FROM `'+table+'`')
        source_columns=[x[0] for x in sc.description]
        columns=[]
        for name in source_columns:
            if table=='equipment' and name=='image_path':
                if 'image_filename' not in source_columns:
                    columns.append('image_filename')
            else:
                columns.append(name)
        target_columns={x[0] for x in target.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s',(table,))}
        if set(columns)-target_columns:raise ValueError('Unsupported source columns in '+table+': '+str(set(columns)-target_columns))
        command=sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns))
        count=0
        with target.cursor() as tc:
            while True:
                rows=sc.fetchmany(500)
                if not rows:break
                values=[]
                for row in rows:
                    values.append(tuple(
                        equipment_image_filename(row.get('image_filename') or row.get('image_path')) if table=='equipment' and target_name=='image_filename'
                        else int(row[target_name]) if isinstance(row[target_name],bool)
                        else row[target_name]
                        for target_name in columns
                    ))
                tc.executemany(command,values);count+=len(rows)
        actual=target.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
        if count!=actual:raise ValueError('Count mismatch for '+table)
        counts[table]=count
    for table in TABLES:
        seq=target.execute("SELECT pg_get_serial_sequence(%s,'id') WHERE EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s AND column_name='id')",(table,table)).fetchone()
        if seq and seq[0]:
            maximum=target.execute(sql.SQL('SELECT max(id) FROM {}').format(sql.Identifier(table))).fetchone()[0]
            target.execute('SELECT setval(%s,%s,%s)',(seq[0],max(1,maximum or 0),bool(maximum)))
    sc.close();return counts
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='Copy into an EMPTY initialized PostgreSQL database')
    args=parser.parse_args()
    if not args.execute:parser.error('Back up MySQL, stop application writes, initialize an empty PostgreSQL target, then pass --execute.')
    import mysql.connector
    host=input('Local MySQL host [127.0.0.1]: ').strip() or '127.0.0.1'
    port=int(input('Local MySQL port [3306]: ').strip() or '3306')
    database=input('Existing MySQL database [college_equipment]: ').strip() or 'college_equipment'
    user=input('Local MySQL user [root]: ').strip() or 'root'
    password=getpass.getpass('Local MySQL password (blank if none): ')
    source=mysql.connector.connect(host=host,port=port,database=database,user=user,password=password)
    try:
        # MariaDB may report a MySQL-compatible version (5.5.5) that causes
        # mysql-connector-python to reject its read-only transaction option.
        # This migration only issues SELECTs against the source.
        source.start_transaction()
        with raw_connect() as target:counts=migrate(source,target)
        print('Migration committed. Row counts:',counts)
        print('Keep your MySQL backup and copy static/uploads/equipment images separately. Run check_database.py, then start app.py.')
    except Exception as exc:
        print('Migration failed; target row changes rolled back. Error type:',type(exc).__name__)
        if isinstance(exc,ValueError):print(str(exc))
        else:print('Check source/target schema, duplicate IDs, invalid dates and connection settings. Original MySQL records were not modified.')
        raise SystemExit(1)
    finally:source.rollback();source.close()
