# Aiven PostgreSQL setup — BCC Equipment Services

This package uses PostgreSQL, not MySQL. The website remains Flask/Python with your existing desktop and smartphone interfaces. Aiven hosts the database; it does not host the Flask website. No Aiven account or live database has been created for you.

## 1. Back up your existing system

Stop the old application before copying records. In XAMPP, keep MySQL running for export/migration. Open phpMyAdmin, select your existing database, and use **Export → Quick → SQL → Export**. Save that file safely. Copy your current application folder, including `static/uploads/equipment` (uploaded photos). Do not delete or overwrite the original MySQL database.

## 2. Create an Aiven PostgreSQL service

1. Sign in at https://console.aiven.io/.
2. Open/create your project, then select **Services → Create service**.
3. Select **PostgreSQL**, not MySQL.
4. Select the **Free** tier if available. Check that the service summary says Free / $0. A paid plan using temporary trial credits is different.
5. Name the service, for example `bcc-equipment-postgres`, and create it. Wait for **Running**.
6. Open the service Overview / connection information. Record the **host**, **port**, **database**, **username**, and **password**. Use the exact port shown; do not assume 5432 or your old MySQL port. The initial database is commonly `defaultdb`.
7. Download the service **CA certificate**, then save it as `certs/ca.pem` beside the application. If Aiven restricts allowed IP addresses, allow the computer/application host that will connect.

Official instructions: https://aiven.io/docs/products/postgresql/get-started
Free-tier details: https://aiven.io/docs/platform/concepts/service-pricing

## 3. Open the correct application folder

Extract the ZIP. Open the inner folder containing `app.py`, `requirements.txt`, `pg_database.py` and this guide in VS Code. Open a PowerShell terminal there. Run:

```powershell
Get-ChildItem app.py
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Using the virtual environment's Python directly avoids PowerShell activation-policy issues. Python 3.11–3.14 is suitable; if package wheels are unavailable on your installation, use Python 3.12 or 3.13.

## 4. Configure your Aiven connection

Edit `.env` in VS Code. Replace every placeholder:

```dotenv
PGHOST=your-real-postgresql-host.aivencloud.com
PGPORT=the-port-shown-in-aiven
PGDATABASE=defaultdb
PGUSER=avnadmin
PGPASSWORD='your-real-password'
PGSSLMODE=verify-full
PGSSLROOTCERT=certs/ca.pem
SECRET_KEY=your-own-long-random-value
FLASK_DEBUG=0
COOKIE_SECURE=0
```

Generate a secret with:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copy the result into SECRET_KEY. Do not post passwords, `.env`, SQL backups or screenshots of connection credentials publicly. Keep passwords quoted in `.env`; if the password contains a single quote, use double quotes and escape any embedded double quotes/backslashes according to dotenv rules. Hosting environment variables override `.env`.

The app verifies the certificate and host using `verify-full`; do not disable TLS verification to resolve certificate errors. Check that the certificate belongs to the same service and that PGHOST exactly matches Aiven's DNS host.

## 5. Check the connection and create PostgreSQL tables

```powershell
.\.venv\Scripts\python.exe check_database.py
.\.venv\Scripts\python.exe init_postgresql.py
```

The first command should show a PostgreSQL version and TLS enabled. The second creates missing tables without dropping records. It creates no default admin password or demo accounts. Do not import a MySQL `.sql` dump directly into PostgreSQL: its SQL format is different. The PostgreSQL schema is in `schema_postgresql.sql` if you prefer reviewing it in pgAdmin.

## 6. Choose ONE data path

### A. Keep your existing accounts and records (recommended)

Keep the OLD system stopped and local XAMPP MySQL running. Your new PostgreSQL tables must be empty. Do not open `/setup` or add records yet.

```powershell
.\.venv\Scripts\python.exe -m pip install mysql-connector-python
.\.venv\Scripts\python.exe migrate_mysql_to_postgresql.py --execute
```

Enter your LOCAL MySQL host, port, database name, username and password when prompted. The destination comes from `.env`. The migration reads MySQL without editing it, copies the known application tables, checks row counts, preserves IDs/password hashes, and adjusts PostgreSQL ID sequences. It maps the legacy equipment `image_path` column to PostgreSQL `image_filename`, storing only the filename used by the app. It refuses a nonempty target or unrecognized source tables/columns. If row copying fails, it rolls back the destination transaction; do not delete old records to work around an error.

Copy the old `static/uploads/equipment` directory into the new application folder. Photos are files, not stored inside the database; confirm that each filename referenced by the migrated equipment row exists in that directory. Existing account passwords remain the same. Sign in again after changing the application secret. Keep your old MySQL backup until you verify the new system.

### B. Start with an empty system

Skip migration. Start the application in Step 7, open `http://127.0.0.1:5000/setup`, and create the first administrator. Keep first-admin setup local/private until completed. Add categories using pgAdmin if needed, then equipment and people through the application. Existing MySQL records are not automatically copied with this path.

Example category initialization in pgAdmin Query Tool, connected to the SAME database:

```sql
INSERT INTO categories(name,description) VALUES
('Computers','Computer equipment'),
('Audio Visual','Classroom AV equipment'),
('Laboratory','Laboratory tools'),
('Sports','Sports equipment'),
('Electronics','Electronic accessories')
ON CONFLICT (name) DO NOTHING;
```

## 7. Start and verify locally

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000` for Student/Faculty and `http://127.0.0.1:5000/admin/login` for Admin/Staff. Internet is now required because the database is on Aiven. After migration you can stop XAMPP MySQL; the converted app no longer uses it.

Verify each role can sign in. Check equipment counts, unique serials, student/faculty activation and agreements, request → approval → release → return, Good returns without costs, Fair/Damaged cost acknowledgment, notifications (Read All / Clear All), account management, and smartphone layout. Use a test borrowing record before ordinary use.

## 8. When you host the Flask website online

Choose a host supporting Python/Flask. Upload this application without `.env` or backup files. Configure the same PG variables and SECRET_KEY in the host's environment settings. Add the CA certificate as a secret file and set PGSSLROOTCERT to its path. Use `COOKIE_SECURE=1` when the website is served over HTTPS and keep FLASK_DEBUG=0. Install with `pip install -r requirements.txt`. A Linux production command is:

```bash
gunicorn --workers 1 --threads 2 --bind 0.0.0.0:$PORT app:app
```

Use a persistent disk for uploaded equipment images AND set up backups. Aiven stores database records, not your `static/uploads/equipment` files. Local `py app.py` is for development; the website is not publicly deployed by completing database setup alone. Hosting plans, sleep behavior, and storage costs depend on your selected host.

## Troubleshooting

- **Missing app.py:** open the inner extracted directory, then run `Get-ChildItem app.py`.
- **No module named psycopg/dotenv:** install requirements using the same `.venv` Python used to start the application.
- **Set PGHOST / invalid port:** remove placeholders in `.env`; the port must contain digits only.
- **CA file missing:** save Aiven's certificate as `certs/ca.pem` or give an absolute PGSSLROOTCERT path.
- **Certificate mismatch:** use the service DNS hostname, not its raw IP address, and the correct CA certificate.
- **`certificate contains IP address with invalid length`:** first confirm PGHOST is the Aiven service DNS hostname and PGSSLROOTCERT is its CA certificate. If both are correct, the PostgreSQL driver's hostname verification is failing against the service certificate. `PGSSLMODE=verify-ca` may connect while still validating the CA, but skips hostname verification; only use it if you accept that reduced protection. Do not configure an automatic fallback from `verify-full`.
- **Connection refused / timeout:** check service Running status, host, port, internet connection and allowed source IPs.
- **Password authentication failed:** use Aiven PostgreSQL credentials, not XAMPP root credentials.
- **Relation does not exist:** run `init_postgresql.py` against the same PGDATABASE as the app.
- **Migration target not empty:** use a fresh PostgreSQL database. Never run migration over existing production records.
- **Unrecognized table/column:** your local database differs from this supplied system; review the difference before migration. The tool refuses to silently discard it.
- **Image missing after migration:** copy the old uploads directory; records alone do not include image bytes.
- **Login fails after migration:** verify the correct source database was copied and the account is active. Do not re-create accounts over migrated records.

## Technical notes

The app now uses Psycopg 3, PostgreSQL identity columns, ON CONFLICT upserts, PostgreSQL date arithmetic, and transaction savepoints for recoverable SQL errors. Existing 0/1 flags use checked SMALLINT columns to preserve the current workflow semantics. The database session timezone is Asia/Manila. Old MySQL SQL files and older instructions are retained only in `legacy_mysql_reference/`; do not use them for PostgreSQL setup.

Sources checked for this guide:
- https://aiven.io/docs/products/postgresql/get-started
- https://aiven.io/docs/products/postgresql/howto/connect-python
- https://www.postgresql.org/docs/current/libpq-ssl.html
- https://www.psycopg.org/psycopg3/docs/basic/install.html
