from flask import Flask, render_template, request, redirect, url_for, session, flash, g, make_response, jsonify, abort
import psycopg, os, secrets, hashlib, hmac, re
from pg_database import connect as pg_connect
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).with_name('.env'), override=False)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import timedelta

app = Flask(__name__)
BORROWER_TERMS_VERSION = '2026-10-04-v1'
STUDENT_COURSE_OPTIONS = ('CCJS','CITE','COTE','COHM','COTM')
FACULTY_DEPARTMENT_OPTIONS = ('CCJS','CITE','COHM','COTM')

EQUIPMENT_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'equipment')
os.makedirs(EQUIPMENT_UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def load_secret_key():
    env_key = os.getenv('SECRET_KEY')
    if env_key:
        return env_key
    key_file = os.path.join(os.path.dirname(__file__), '.secret_key')
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    return key
        key = secrets.token_hex(32)
        with open(key_file, 'w', encoding='utf-8') as f:
            f.write(key)
        return key
    except OSError:
        return secrets.token_hex(32)

app.secret_key = load_secret_key()
app.config.update(
    SESSION_COOKIE_NAME='college_equipment_admin_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

STUDENT_SESSION_SECONDS = int(os.getenv('STUDENT_SESSION_SECONDS', '28800'))  # 8 hours


def equipment_image_url(item):
    """Return a local image for every equipment record.

    Uploaded photos take priority. Existing seeded equipment uses bundled
    illustrations, while newly added items fall back to a category image.
    """
    filename = (item.get('image_filename') if hasattr(item, 'get') else None) or ''
    if filename:
        full = os.path.join(EQUIPMENT_UPLOAD_DIR, os.path.basename(filename))
        if os.path.isfile(full):
            return url_for('static', filename='uploads/equipment/' + os.path.basename(filename))

    asset = str((item.get('asset_code') if hasattr(item, 'get') else '') or '').upper()
    name = str((item.get('name') if hasattr(item, 'get') else '') or '').lower()
    category = str((item.get('category') if hasattr(item, 'get') else '') or '').lower()

    by_asset = {
        'CE-001': 'laptop-real.png',
        'CE-002': 'lcd-projector-real.png',
        'CE-003': 'portable-speaker-real.png',
        'CE-004': 'digital-multimeter-real.png',
        'CE-005': 'extension-cord-real.png',
    }
    if asset in by_asset:
        return url_for('static', filename='images/equipment/' + by_asset[asset])

    by_name = [
        ('laptop', 'laptop-real.png'),
        ('projector', 'lcd-projector-real.png'),
        ('speaker', 'portable-speaker-real.png'),
        ('multimeter', 'digital-multimeter-real.png'),
        ('extension', 'extension-cord-real.png'),
    ]
    for key, img in by_name:
        if key in name:
            return url_for('static', filename='images/equipment/' + img)

    category_files = {
        'computers': 'category-computers-real.png',
        'audio visual': 'category-av-real.png',
        'laboratory': 'category-laboratory-real.png',
        'sports': 'category-sports-real.png',
        'electronics': 'category-electronics-real.png',
    }
    return url_for('static', filename='images/equipment/' + category_files.get(category, 'category-electronics-real.png'))


def save_equipment_image(upload, asset_code):
    if not upload or not upload.filename:
        return None
    original = secure_filename(upload.filename)
    if '.' not in original:
        raise ValueError('Image must be PNG, JPG, JPEG, or WEBP.')
    ext = original.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Image must be PNG, JPG, JPEG, or WEBP.')
    safe_code = secure_filename(asset_code).lower() or 'equipment'
    filename = f"{safe_code}-{secrets.token_hex(5)}.{ext}"
    upload.save(os.path.join(EQUIPMENT_UPLOAD_DIR, filename))
    return filename



def db():
    return pg_connect()


def query(sql, args=(), one=False, commit=False):
    c = db()
    cur = c.cursor(dictionary=True)
    try:
        cur.execute(sql, args)
        if commit:
            c.commit()
            return cur.lastrowid
        return cur.fetchone() if one else cur.fetchall()
    except Exception:
        if commit:
            c.rollback()
        raise
    finally:
        cur.close()
        c.close()


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _admin_identity():
    uid = session.get('admin_uid')
    if not uid:
        return None
    u = query("SELECT id,school_id,full_name,role FROM users WHERE id=%s AND active=1 AND role IN ('admin','staff')", (uid,), one=True)
    if not u:
        session.clear()
        return None
    return {'id': u['id'], 'school_id': u['school_id'], 'name': u['full_name'], 'role': u['role']}


def _student_identity(scope):
    raw_token = request.cookies.get('student_session')
    if not raw_token:
        return None
    row = query(
        """
        SELECT a.id auth_session_id,a.user_id,u.school_id,u.full_name,u.role
        FROM auth_sessions a
        JOIN users u ON u.id=a.user_id
        WHERE a.session_scope=%s AND a.token_hash=%s AND a.revoked=0
          AND a.expires_at>NOW() AND u.active=1 AND u.role IN ('student','faculty')
        """,
        (scope, token_hash(raw_token)), one=True
    )
    if not row:
        return None
    query("UPDATE auth_sessions SET last_seen=NOW() WHERE id=%s", (row['auth_session_id'],), commit=True)
    return {
        'id': row['user_id'], 'school_id': row['school_id'], 'name': row['full_name'],
        'role': row['role'], 'auth_session_id': row['auth_session_id'], 'raw_token': raw_token
    }


def admin_required(*allowed):
    def deco(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            u = _admin_identity()
            if not u:
                return redirect(url_for('admin_login'))
            if allowed and u['role'] not in allowed:
                flash('Access denied.', 'danger')
                return redirect(url_for('admin_dashboard'))
            g.current_user = u
            return f(*args, **kwargs)
        return wrapped
    return deco


def student_required(f):
    @wraps(f)
    def wrapped(scope, *args, **kwargs):
        u = _student_identity(scope)
        if not u:
            return redirect(url_for('student_login', expired='1'))
        g.current_user = u
        g.student_scope = scope
        if request.endpoint not in ('borrower_terms','student_logout'):
            accepted=query('SELECT user_id FROM borrower_terms_acceptance WHERE user_id=%s AND terms_version=%s',(u['id'],BORROWER_TERMS_VERSION),one=True)
            if not accepted:return redirect(url_for('borrower_terms',scope=scope))
        return f(scope, *args, **kwargs)
    return wrapped


def csrf_for_current_user():
    u = getattr(g, 'current_user', None)
    if not u:
        return ''
    if u['role'] in ('student', 'faculty'):
        raw = u.get('raw_token', '')
        return hmac.new(app.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not session.get('_csrf'):
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def verify_csrf():
    expected = csrf_for_current_user()
    supplied = request.form.get('_csrf', '')
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def notify_user(user_id, message, dedupe=False):
    """Create an in-app notification for one user.

    dedupe=True prevents housekeeping reminders from being inserted repeatedly.
    """
    if not user_id or not message:
        return None
    if dedupe:
        existing = query(
            'SELECT id FROM notifications WHERE user_id=%s AND message=%s LIMIT 1',
            (user_id, message), one=True
        )
        if existing:
            return existing['id']
    return query(
        'INSERT INTO notifications(user_id,message) VALUES(%s,%s)',
        (user_id, message), commit=True
    )


def notify_personnel(message, dedupe=False, exclude_user_id=None):
    """Notify every active Administrator and Staff account."""
    people = query(
        "SELECT id FROM users WHERE active=1 AND role IN ('admin','staff') ORDER BY id"
    )
    for person in people:
        if exclude_user_id and person['id'] == exclude_user_id:
            continue
        notify_user(person['id'], message, dedupe=dedupe)


def process_due_notifications():
    """Update overdue loans and create one-time due-date reminders.

    This runs during normal application traffic and is also triggered by the
    live notification polling endpoints while users have the system open.
    """
    query(
        "UPDATE borrow_requests SET status='Overdue' "
        "WHERE status='Released' AND due_date<CURRENT_DATE",
        commit=True
    )
    due_rows = query(
        """
        SELECT b.id,b.borrower_id,b.due_date,b.status,b.quantity,
               (b.due_date - CURRENT_DATE) days_until_due,
               e.name equipment_name,u.full_name borrower_name
        FROM borrow_requests b
        JOIN equipment e ON e.id=b.equipment_id
        JOIN users u ON u.id=b.borrower_id
        WHERE b.status IN ('Released','Overdue')
          AND b.return_requested_at IS NULL
          AND b.due_date<=(CURRENT_DATE + 1)
        ORDER BY b.due_date,b.id
        """
    )
    for row in due_rows:
        due = row['due_date'].strftime('%b %d, %Y') if hasattr(row['due_date'], 'strftime') else str(row['due_date'])
        days = int(row.get('days_until_due') or 0)
        if row['status'] == 'Released' and days == 1:
            message = (
                f"Due tomorrow: {row['equipment_name']} for request #{row['id']} "
                f"must be returned by {due}."
            )
            notify_user(row['borrower_id'], message, dedupe=True)
        elif row['status'] == 'Released' and days == 0:
            message = (
                f"Due today: {row['equipment_name']} for request #{row['id']} "
                f"must be returned today ({due}). Please use the Return Equipment button in My Borrowing."
            )
            notify_user(row['borrower_id'], message, dedupe=True)
        elif row['status'] == 'Overdue':
            student_message = (
                f"Overdue: {row['equipment_name']} for request #{row['id']} "
                f"was due on {due}. Please use the Return Equipment button in My Borrowing and return it as soon as possible."
            )
            personnel_message = (
                f"Overdue equipment: {row['borrower_name']} has {row['equipment_name']} "
                f"(request #{row['id']}) that was due on {due}."
            )
            notify_user(row['borrower_id'], student_message, dedupe=True)
            notify_personnel(personnel_message, dedupe=True)


def notification_detail_url(notification_id):
    if g.current_user['role'] in ('student', 'faculty'):
        return url_for('student_notification_detail', scope=g.student_scope, id=notification_id)
    return url_for('notification_detail', id=notification_id)


def render_notification_detail(notification_id):
    notification = query(
        'SELECT * FROM notifications WHERE id=%s AND user_id=%s',
        (notification_id, g.current_user['id']), one=True
    )
    if not notification:
        abort(404)
    transaction = None
    # Existing notification messages include the borrowing request number.
    match = re.search(r'\brequest\s+#(\d+)\b', notification['message'], re.IGNORECASE)
    if match:
        sql = '''SELECT b.*,e.name equipment_name,e.model equipment_model,e.serial_number,e.asset_code,e.location,
                        u.full_name borrower_name,u.school_id,
                        reviewer.full_name reviewer_name
                 FROM borrow_requests b
                 JOIN equipment e ON e.id=b.equipment_id
                 JOIN users u ON u.id=b.borrower_id
                 LEFT JOIN users reviewer ON reviewer.id=b.reviewed_by
                 WHERE b.id=%s'''
        params = (int(match.group(1)),)
        if g.current_user['role'] in ('student', 'faculty'):
            sql += ' AND b.borrower_id=%s'
            params += (g.current_user['id'],)
        transaction = query(sql, params, one=True)
    query('UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s',
          (notification_id, g.current_user['id']), commit=True)
    return render_template('notification_detail.html', notification=notification, transaction=attach_unit_serials([transaction])[0] if transaction else None)


def notification_payload(user_id):
    count = query(
        'SELECT COUNT(*) n FROM notifications WHERE user_id=%s AND is_read=0',
        (user_id,), one=True
    )['n']
    latest = query(
        'SELECT id,message,created_at FROM notifications WHERE user_id=%s AND is_read=0 ORDER BY id DESC LIMIT 5',
        (user_id,)
    )
    max_row = query(
        'SELECT COALESCE(MAX(id),0) max_id FROM notifications WHERE user_id=%s',
        (user_id,), one=True
    )
    return {
        'unread_count': int(count or 0),
        'max_id': int(max_row['max_id'] or 0),
        'latest': [
            {
                'id': int(row['id']),
                'message': row['message'],
                'url': notification_detail_url(row['id']),
                'created_at': row['created_at'].isoformat(sep=' ', timespec='minutes')
                    if hasattr(row['created_at'], 'isoformat') else str(row['created_at'])
            } for row in latest
        ]
    }


@app.context_processor
def inject_auth_context():
    # Identity is set only by the appropriate protected route.
    # This prevents an Admin session from taking over Student login pages.
    u = getattr(g, 'current_user', None)
    unread = 0
    if u:
        try:
            unread = query(
                'SELECT COUNT(*) n FROM notifications WHERE user_id=%s AND is_read=0',
                (u['id'],), one=True
            )['n']
        except Exception:
            unread = 0
    return {
        'current_user': u,
        'student_scope': getattr(g, 'student_scope', None),
        'csrf_token': csrf_for_current_user() if u else '',
        'equipment_image': equipment_image_url,
        'notification_unread_count': int(unread or 0),
    }


_schema_ready = False

def ensure_supporting_tables():
    global _schema_ready
    if _schema_ready:return
    # Schema is initialized explicitly, never by destructive reset during traffic.
    query('SELECT user_id FROM borrower_terms_acceptance LIMIT 1')
    query('SELECT archived FROM equipment LIMIT 1')
    ensure_equipment_units()
    _schema_ready=True


@app.before_request
def housekeeping():
    if request.endpoint and request.endpoint != 'static':
        try:
            ensure_supporting_tables()
            process_due_notifications()
        except Exception:
            # Login pages can still display a clear DB error from their own handlers.
            pass


@app.after_request
def secure_response(response):
    # Authenticated/private screens should never be reused from browser/proxy cache.
    if getattr(g, 'current_user', None):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@app.route('/')
def home():
    if _admin_identity():
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('student_login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    try:
        ensure_supporting_tables()
        all_admins = query("SELECT id,school_id,full_name,email,active FROM users WHERE role='admin' ORDER BY id")
    except Exception:
        return 'Database connection failed. Check your Aiven PostgreSQL settings in .env and follow AIVEN_POSTGRESQL_SETUP.md.', 500

    # Never overwrite an existing administrator record.
    if any(bool(a['active']) for a in all_admins):
        return redirect(url_for('admin_login'))
    if all_admins:
        return redirect(url_for('admin_recover'))

    error = None
    if request.method == 'POST':
        school_id = request.form.get('school_id', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '')
        if len(password) < 6:
            error = 'Password must contain at least 6 characters.'
        else:
            try:
                query(
                    "INSERT INTO users(school_id,full_name,email,password_hash,role,department,active) VALUES(%s,%s,%s,%s,'admin',%s,1)",
                    (school_id, full_name, email, generate_password_hash(password), request.form.get('department')),
                    commit=True,
                )
                return redirect(url_for('admin_login', kind='success', notice='Administrator account created. Please sign in.'))
            except Exception:
                error = 'That School/Employee ID or email already exists. No existing record was changed.'
    return render_template('setup.html', setup_error=error)


@app.route('/admin/recover', methods=['GET', 'POST'])
def admin_recover():
    """Recover an existing inactive admin only when there is no active admin."""
    try:
        ensure_supporting_tables()
        active_count = query("SELECT COUNT(*) n FROM users WHERE role='admin' AND active=1", one=True)['n']
        admins = query("SELECT id,school_id,full_name,email,active FROM users WHERE role='admin' ORDER BY id")
    except Exception:
        return 'PostgreSQL connection failed. Check your Aiven service and .env settings; run check_database.py.', 500
    if active_count:
        return redirect(url_for('admin_login'))
    if not admins:
        return redirect(url_for('setup'))

    error = None
    if request.method == 'POST':
        sid = request.form.get('school_id', '').strip()
        name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        row = query("SELECT * FROM users WHERE role='admin' AND TRIM(school_id)=%s LIMIT 1", (sid,), one=True)
        matches = bool(row and row['full_name'].strip().lower() == name.lower())
        if matches and row.get('email'):
            matches = row['email'].strip().lower() == email.lower()
        if not matches:
            error = 'The information does not match the existing administrator record.'
        elif len(password) < 6:
            error = 'New password must contain at least 6 characters.'
        else:
            query("UPDATE users SET password_hash=%s,active=1 WHERE id=%s", (generate_password_hash(password), row['id']), commit=True)
            return redirect(url_for('admin_login', kind='success', notice='Existing administrator record recovered. Sign in with the new password.'))
    return render_template('admin_recover.html', admins=admins, recover_error=error)


@app.route('/login')
def login():
    return redirect(url_for('student_login'))


@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'GET' and not any(request.args.get(key) for key in ('continue', 'notice', 'expired')):
        return render_template('student_welcome.html')
    error = None
    if request.method == 'POST':
        sid = request.form.get('school_id', '').strip()
        password = request.form.get('password', '')
        try:
            ensure_supporting_tables()
            u = query("SELECT * FROM users WHERE TRIM(school_id)=%s AND active=1 AND role IN ('student','faculty') LIMIT 1", (sid,), one=True)
        except Exception:
            return 'PostgreSQL connection failed. Check your Aiven service and .env settings; run check_database.py.', 500
        if u and u.get('password_hash') and check_password_hash(u['password_hash'], password):
            scope = secrets.token_urlsafe(10).replace('-', '').replace('_', '')
            raw_token = secrets.token_urlsafe(32)
            query(
                "INSERT INTO auth_sessions(session_scope,token_hash,user_id,role,expires_at) VALUES(%s,%s,%s,%s,(NOW() + %s * INTERVAL '1 second'))",
                (scope, token_hash(raw_token), u['id'], u['role'], STUDENT_SESSION_SECONDS), commit=True
            )
            response = make_response(redirect(url_for('student_dashboard', scope=scope)))
            response.set_cookie(
                'student_session', raw_token, max_age=STUDENT_SESSION_SECONDS, httponly=True,
                secure=app.config['SESSION_COOKIE_SECURE'], samesite='Lax', path=f'/student/s/{scope}'
            )
            return response
        error = 'Invalid Student / Faculty ID or password.'
    return render_template('student_login.html', student_error=error)


@app.route('/student/s/<scope>/terms', methods=['GET','POST'])
@student_required
def borrower_terms(scope):
    error=None
    if request.method=='POST':
        if not verify_csrf():abort(400)
        if request.form.get('accept_terms')!='yes':
            error='Please read and accept the terms before continuing.'
        else:
            query('INSERT INTO borrower_terms_acceptance(user_id,terms_version) VALUES(%s,%s) ON CONFLICT DO NOTHING',
                  (g.current_user['id'],BORROWER_TERMS_VERSION),commit=True)
            return redirect(url_for('student_dashboard',scope=scope))
    return render_template('borrower_terms.html',terms_error=error)


@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    """Self-activation for both students and faculty borrowers.

    Students are pre-registered in student_records. Faculty are pre-created in
    users with activation_required=1, active=0 and no password hash. In both
    cases the borrower personally sets the password and accepts the agreement.
    """
    error = None
    if not session.get('activation_csrf'):
        session['activation_csrf'] = secrets.token_urlsafe(32)
    if request.method == 'POST':
        sid = request.form.get('school_id', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        record = query("SELECT * FROM student_records WHERE TRIM(student_id)=%s AND active=1", (sid,), one=True)
        faculty = query(
            "SELECT * FROM users WHERE TRIM(school_id)=%s AND role='faculty' LIMIT 1",
            (sid,), one=True
        )
        if not hmac.compare_digest(request.form.get('_activation_csrf',''), session['activation_csrf']):
            abort(400)
        if request.form.get('accept_terms') != 'yes':
            error = 'You must read and agree to the borrowing, damage responsibility and cost terms before activating your account.'
        elif record and faculty:
            error = 'This ID appears in more than one borrower record. Please contact the administrator.'
        elif not record and not faculty:
            error = 'Student / Faculty ID was not found in the official records. Please contact the administrator.'
        elif record and record['user_id']:
            error = 'This Student ID already has an activated account. Please sign in.'
        elif faculty and faculty.get('active'):
            error = 'This Faculty ID already has an activated account. Please sign in.'
        elif faculty and not faculty.get('activation_required'):
            error = 'This Faculty account is not available for activation. Please contact the administrator.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif len(password) < 6:
            error = 'Password must contain at least 6 characters.'
        else:
            c = db()
            cur = c.cursor(dictionary=True)
            try:
                if record:
                    cur.execute(
                        "INSERT INTO users(school_id,full_name,email,password_hash,role,department,active,activation_required) VALUES(%s,%s,%s,%s,'student',%s,1,0)",
                        (record['student_id'], record['full_name'], record['email'], generate_password_hash(password), record['program'])
                    )
                    uid = cur.lastrowid
                    cur.execute('INSERT INTO borrower_terms_acceptance(user_id,terms_version) VALUES(%s,%s)', (uid, BORROWER_TERMS_VERSION))
                    cur.execute("UPDATE student_records SET user_id=%s,registered_at=NOW() WHERE id=%s AND user_id IS NULL", (uid, record['id']))
                    if cur.rowcount != 1:
                        raise RuntimeError('Student record was already activated.')
                    account_label = 'Student'
                else:
                    uid = faculty['id']
                    cur.execute(
                        "UPDATE users SET password_hash=%s,active=1,activation_required=0 WHERE id=%s AND role='faculty' AND active=0 AND activation_required=1",
                        (generate_password_hash(password), uid)
                    )
                    if cur.rowcount != 1:
                        raise RuntimeError('Faculty record was already activated or is unavailable.')
                    cur.execute(
                        'INSERT INTO borrower_terms_acceptance(user_id,terms_version) VALUES(%s,%s) ON CONFLICT (user_id,terms_version) DO UPDATE SET accepted_at=EXCLUDED.accepted_at',
                        (uid, BORROWER_TERMS_VERSION)
                    )
                    account_label = 'Faculty'
                c.commit()
                return redirect(url_for(
                    'student_login', kind='success',
                    notice=f'{account_label} account activated successfully. Sign in using your ID and personal password.'
                ))
            except Exception:
                c.rollback()
                error = 'Unable to activate this account. The ID or email may already be used, or the record may no longer be available.'
            finally:
                cur.close(); c.close()
    return render_template('student_register.html', student_error=error)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if _admin_identity():
        return redirect(url_for('admin_dashboard'))

    try:
        ensure_supporting_tables()
        active_admin_count = query("SELECT COUNT(*) n FROM users WHERE active=1 AND role='admin'", one=True)['n']
        personnel_count = query("SELECT COUNT(*) n FROM users WHERE active=1 AND role IN ('admin','staff')", one=True)['n']
        any_admin_count = query("SELECT COUNT(*) n FROM users WHERE role='admin'", one=True)['n']
    except Exception:
        return 'Database connection failed. Check Aiven PostgreSQL connectivity with check_database.py.', 500

    error = None
    if request.method == 'POST':
        school_id = request.form.get('school_id', '').strip()
        password = request.form.get('password', '')
        u = query(
            "SELECT * FROM users WHERE TRIM(school_id)=%s AND active=1 AND role IN ('admin','staff') LIMIT 1",
            (school_id,), one=True
        )
        if u and u.get('password_hash') and check_password_hash(u['password_hash'], password):
            session.clear()
            session.permanent = True
            session['admin_uid'] = u['id']
            session['_csrf'] = secrets.token_urlsafe(32)
            return redirect(url_for('admin_dashboard'))
        error = 'Invalid Administrator/Staff ID or password.'

    return render_template('admin_login.html', admin_count=personnel_count, active_admin_count=active_admin_count, any_admin_count=any_admin_count, admin_error=error)


# ---------- STUDENT: path-scoped sessions (supports multiple students in one browser) ----------
@app.route('/student/s/<scope>/dashboard')
@student_required
def student_dashboard(scope):
    uid = g.current_user['id']
    stats = {
        'equipment': query('SELECT COUNT(*) n FROM equipment WHERE archived=0', one=True)['n'],
        'available': query('SELECT COALESCE(SUM(available_qty),0) n FROM equipment WHERE archived=0', one=True)['n'],
        'pending': query("SELECT COUNT(*) n FROM borrow_requests WHERE borrower_id=%s AND status='Pending'", (uid,), one=True)['n'],
        'overdue': query("SELECT COUNT(*) n FROM borrow_requests WHERE borrower_id=%s AND status='Overdue'", (uid,), one=True)['n'],
    }
    rows = query("SELECT b.*,e.name,e.model,e.serial_number,e.asset_code,e.image_filename FROM borrow_requests b JOIN equipment e ON e.id=b.equipment_id WHERE borrower_id=%s ORDER BY b.id DESC LIMIT 8", (uid,))
    recent_notifications=query('SELECT id,message,created_at,is_read FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 3',(g.current_user['id'],))
    return render_template('dashboard.html', stats=stats, rows=rows, recent_notifications=recent_notifications)


@app.route('/student/s/<scope>/equipment')
@student_required
def student_equipment(scope):
    return render_template(
        'equipment.html',
        items=equipment_with_units(),
        cats=[]
    )


@app.route('/student/s/<scope>/borrow/<int:id>', methods=['POST'])
@student_required
def student_borrow(scope, id):
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400
    f = request.form
    item = query('SELECT * FROM equipment WHERE id=%s AND archived=0', (id,), one=True)
    qty = int(f['quantity'])
    if not item or qty < 1 or qty > item['available_qty']:
        return redirect(url_for('student_equipment', scope=scope, kind='danger', notice='Requested quantity is not available.'))
    elif f['due_date'] < f['borrow_date']:
        return redirect(url_for('student_equipment', scope=scope, kind='danger', notice='Due date must be on or after borrow date.'))
    else:
        c=db();cur=c.cursor(dictionary=True)
        try:
            cur.execute('SELECT archived FROM equipment WHERE id=%s FOR UPDATE',(id,))
            current=cur.fetchone()
            if not current or current['archived']:
                c.rollback()
                return redirect(url_for('student_equipment',scope=scope,kind='danger',notice='Equipment is no longer available.'))
            cur.execute('INSERT INTO borrow_requests(borrower_id,equipment_id,quantity,purpose,borrow_date,due_date) VALUES(%s,%s,%s,%s,%s,%s)',
                (g.current_user['id'],id,qty,f['purpose'],f['borrow_date'],f['due_date']))
            request_id=cur.lastrowid;c.commit()
        except Exception:c.rollback();raise
        finally:cur.close();c.close()
        personnel_message = (
            f"New borrowing request #{request_id}: {g.current_user['name']} ({g.current_user['role']}) requested "
            f"{qty} × {item['name']} from {f['borrow_date']} to {f['due_date']}."
        )
        notify_personnel(personnel_message)
        notify_user(
            g.current_user['id'],
            f"Request #{request_id} for {item['name']} was submitted and is awaiting Admin/Staff review."
        )
        return redirect(url_for('student_equipment', scope=scope, kind='success', notice='Borrowing request submitted. Admin and Staff have been notified.'))


def transaction_clear_cutoff(user_id):
    row = query(
        'SELECT cleared_through_request_id FROM transaction_view_state WHERE user_id=%s',
        (user_id,), one=True
    )
    return int((row or {}).get('cleared_through_request_id') or 0)


def save_transaction_clear_cutoff(user_id):
    row = query('SELECT COALESCE(MAX(id),0) max_id FROM borrow_requests', one=True)
    cutoff = int((row or {}).get('max_id') or 0)
    query(
        """INSERT INTO transaction_view_state(user_id,cleared_through_request_id,cleared_at)
           VALUES(%s,%s,NOW())
           ON CONFLICT (user_id) DO UPDATE SET cleared_through_request_id=EXCLUDED.cleared_through_request_id,
                                   cleared_at=NOW()""",
        (user_id, cutoff), commit=True
    )
    return cutoff


@app.route('/student/s/<scope>/requests')
@student_required
def student_requests(scope):
    cutoff = transaction_clear_cutoff(g.current_user['id'])
    rows = query(
        """
        SELECT b.*,e.name,e.model,e.serial_number,e.asset_code,e.fair_cost,e.damage_cost,
               CASE WHEN b.status IN ('Released','Overdue')
                         AND b.return_requested_at IS NULL
                    THEN 1 ELSE 0 END can_request_return
        FROM borrow_requests b
        JOIN equipment e ON e.id=b.equipment_id
        WHERE borrower_id=%s
          AND (b.status IN ('Pending','Approved','Released','Overdue') OR b.id>%s)
        ORDER BY b.id DESC
        """,
        (g.current_user['id'], cutoff)
    )
    return render_template('requests.html', rows=attach_unit_serials(rows))


@app.route('/student/s/<scope>/requests/clear-all', methods=['POST'])
@student_required
def student_requests_clear_all(scope):
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400
    save_transaction_clear_cutoff(g.current_user['id'])
    return redirect(url_for(
        'student_requests', scope=scope, kind='success',
        notice='Transaction history cleared from this view. Active borrowing requests remain visible and all official records are preserved.'
    ))


@app.route('/student/s/<scope>/request/<int:id>/return', methods=['POST'])
@student_required
def student_request_return(scope, id):
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400
    row = query(
        """
        SELECT b.*,e.name equipment_name,e.model equipment_model,e.serial_number,e.asset_code,u.full_name borrower_name
        FROM borrow_requests b
        JOIN equipment e ON e.id=b.equipment_id
        JOIN users u ON u.id=b.borrower_id
        WHERE b.id=%s AND b.borrower_id=%s
        """,
        (id, g.current_user['id']), one=True
    )
    if not row:
        return redirect(url_for('student_requests', scope=scope, kind='danger', notice='Borrowing transaction was not found.'))
    if row['status'] not in ('Released', 'Overdue'):
        return redirect(url_for('student_requests', scope=scope, kind='danger', notice='This equipment is not currently eligible for return.'))
    if row.get('return_requested_at'):
        return redirect(url_for('student_requests', scope=scope, kind='success', notice='Your return has already been submitted and is waiting for Admin/Staff inspection.'))

    query('UPDATE borrow_requests SET return_requested_at=NOW() WHERE id=%s', (id,), commit=True)
    notify_personnel(
        f"Return submitted: {row['borrower_name']} is returning {row['equipment_name']} "
        f"(request #{id}). Open Borrowing & Return to inspect the equipment and approve the return."
    )
    notify_user(
        g.current_user['id'],
        f"Return submitted: {row['equipment_name']} for request #{id} is awaiting Admin/Staff approval and inspection. "
        f"You will be notified after its condition is recorded."
    )
    return redirect(url_for('student_requests', scope=scope, kind='success', notice='Return submitted. Please bring the equipment to Admin/Staff for condition inspection.'))


@app.route('/student/s/<scope>/notifications')
@student_required
def student_notifications(scope):
    uid = g.current_user['id']
    rows = query('SELECT * FROM notifications WHERE user_id=%s ORDER BY id DESC', (uid,))
    return render_template('notifications.html', rows=rows)


def mark_all_notifications_read():
    if not verify_csrf():
        abort(400)
    query('UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0',
          (g.current_user['id'],), commit=True)


@app.route('/student/s/<scope>/notifications/read-all', methods=['POST'])
@student_required
def student_notifications_read_all(scope):
    mark_all_notifications_read()
    return redirect(url_for('student_notifications', scope=scope,
                            kind='success', notice='All notifications marked as read.'))


@app.route('/student/s/<scope>/api/notifications')
@student_required
def student_notifications_api(scope):
    return jsonify(notification_payload(g.current_user['id']))


@app.route('/student/s/<scope>/notifications/<int:id>')
@student_required
def student_notification_detail(scope, id):
    return render_notification_detail(id)


@app.route('/student/s/<scope>/logout')
@student_required
def student_logout(scope):
    query('UPDATE auth_sessions SET revoked=1 WHERE id=%s', (g.current_user['auth_session_id'],), commit=True)
    response = make_response(redirect(url_for('student_login')))
    response.delete_cookie('student_session', path=f'/student/s/{scope}')
    return response


# ---------- ADMIN / STAFF ----------
@app.route('/admin/dashboard')
@admin_required('admin', 'staff')
def admin_dashboard():
    stats = {
        'equipment': query('SELECT COUNT(*) n FROM equipment WHERE archived=0', one=True)['n'],
        'available': query('SELECT COALESCE(SUM(available_qty),0) n FROM equipment WHERE archived=0', one=True)['n'],
        'pending': query("SELECT COUNT(*) n FROM borrow_requests WHERE status='Pending'", one=True)['n'],
        'overdue': query("SELECT COUNT(*) n FROM borrow_requests WHERE status='Overdue'", one=True)['n'],
    }
    rows = query("SELECT b.*,e.name,e.model,e.asset_code,e.image_filename,u.full_name FROM borrow_requests b JOIN equipment e ON e.id=b.equipment_id JOIN users u ON u.id=b.borrower_id ORDER BY b.id DESC LIMIT 8")
    recent_notifications=query('SELECT id,message,created_at,is_read FROM notifications WHERE user_id=%s ORDER BY id DESC LIMIT 3',(g.current_user['id'],))
    return render_template('dashboard.html', stats=stats, rows=rows, recent_notifications=recent_notifications)


@app.route('/dashboard')
def dashboard_legacy():
    return redirect(url_for('admin_dashboard' if _admin_identity() else 'student_login'))


@app.route('/equipment')
@admin_required('admin', 'staff')
def equipment():
    return render_template(
        'equipment.html',
        items=equipment_with_units(),
        cats=query('SELECT * FROM categories ORDER BY name')
    )


def assign_automatic_serial(cur, equipment_id, unit_id):
    # Stable identifiers use durable database IDs, never the current stock count.
    base = f"EQ{equipment_id:04d}-U{unit_id:06d}"
    for attempt in range(10):
        serial = base if attempt == 0 else base + '-' + secrets.token_hex(4).upper()
        try:
            cur.execute('UPDATE equipment_units SET serial_number=%s,needs_serial=0 WHERE id=%s', (serial,unit_id))
            return serial
        except psycopg.IntegrityError as exc:
            if exc.sqlstate != '23505': raise
    raise ValueError('Could not allocate a unique serial number. Please try again.')


def ensure_equipment_units():
    """One durable row per physical unit; never infer historical manufacturer serials."""
    c = db(); cur = c.cursor(dictionary=True)
    try:
        cur.execute('SELECT * FROM equipment ORDER BY id FOR UPDATE')
        for e in cur.fetchall():
            cur.execute('SELECT COUNT(*) n FROM equipment_units WHERE equipment_id=%s', (e['id'],))
            if cur.fetchone()['n']: continue
            cur.execute("SELECT id,quantity FROM borrow_requests WHERE equipment_id=%s AND status IN ('Released','Overdue') ORDER BY id", (e['id'],))
            loans = cur.fetchall()
            assignments = [loan['id'] for loan in loans for _ in range(loan['quantity'])]
            count = max(e['total_qty'],len(assignments))
            unavailable = max(0, e['total_qty']-e['available_qty']-len(assignments))
            for index in range(count):
                # Generated placeholders are explicitly flagged; personnel must enter real serials.
                serial = 'UNVERIFIED-' + secrets.token_hex(12).upper()
                needs_serial = True
                if count == 1 and e.get('serial_number') and not e['serial_number'].startswith(('LEGACY-', 'GROUP-', 'UNVERIFIED-')):
                    serial = e['serial_number']
                    needs_serial = False
                loan = assignments[index] if index < len(assignments) else None
                condition = e['condition_status'] if e['condition_status'] in ('Good','Fair','Damaged','For Repair') else 'Good'
                if not loan and index < len(assignments)+unavailable: condition = 'For Repair'
                cur.execute('INSERT INTO equipment_units(equipment_id,serial_number,condition_status,current_request_id,needs_serial) VALUES(%s,%s,%s,%s,%s)',(e['id'],serial,condition,loan,needs_serial))
                if loan:
                    cur.execute('INSERT INTO borrow_request_units(request_id,unit_id,serial_at_release) VALUES(%s,%s,%s)',(loan,cur.lastrowid,'Legacy loan — serial not recorded'))
            refresh_unit_totals(cur,e['id'])
        cur.execute('SELECT id,equipment_id FROM equipment_units WHERE needs_serial=1 ORDER BY id FOR UPDATE')
        for unit in cur.fetchall():
            assign_automatic_serial(cur,unit['equipment_id'],unit['id'])
        c.commit()
    except Exception:
        c.rollback(); raise
    finally:
        cur.close(); c.close()


def refresh_unit_totals(cur, equipment_id):
    cur.execute("""SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN current_request_id IS NULL AND condition_status IN ('Good','Fair') THEN 1 ELSE 0 END),0) available
        FROM equipment_units WHERE equipment_id=%s AND active=1""",(equipment_id,))
    totals=cur.fetchone()
    cur.execute('UPDATE equipment SET total_qty=%s,available_qty=%s WHERE id=%s',(totals['total'],totals['available'],equipment_id))


def equipment_with_units():
    items=query('SELECT e.*,c.name category FROM equipment e LEFT JOIN categories c ON c.id=e.category_id WHERE e.archived=0 ORDER BY e.name')
    units=query('SELECT * FROM equipment_units WHERE active=1 ORDER BY id')
    grouped={}
    for u in units: grouped.setdefault(u['equipment_id'],[]).append(u)
    for e in items: e['units']=grouped.get(e['id'],[])
    return items


def attach_unit_serials(rows):
    if not rows: return rows
    ids=[r['id'] for r in rows]
    links=query('SELECT request_id,serial_at_release FROM borrow_request_units WHERE request_id IN ('+','.join(['%s']*len(ids))+') ORDER BY unit_id',tuple(ids))
    grouped={}
    for link in links: grouped.setdefault(link['request_id'],[]).append(link['serial_at_release'])
    for row in rows: row['unit_serials']=grouped.get(row['id'],[])
    return rows


def save_inventory(equipment_id=None):
    f=request.form
    c=None; cur=None
    try:
        name=f.get('name','').strip(); code=f.get('asset_code','').strip(); model=f.get('model','').strip()
        if not name or len(name)>120 or not code or len(code)>40:
            raise ValueError('Enter a valid equipment name and asset code.')
        if not model or len(model)>120 or model.lower() in ('update required','model not yet set','n/a','na'):
            raise ValueError('Equipment model is required. Enter the actual brand/model or manufacturer model number.')
        condition=f.get('condition_status','Good')
        if condition not in ('Good','Fair','Damaged','For Repair'): raise ValueError('Invalid condition.')
        from decimal import Decimal, InvalidOperation
        def money_field(name, default):
            raw=(f.get(name) or str(default)).strip()
            try:
                value=Decimal(raw)
                if not value.is_finite() or value<0 or value>Decimal('99999999.99') or value!=value.quantize(Decimal('0.01')):
                    raise ValueError()
                return value
            except (InvalidOperation, ValueError):
                raise ValueError('Fair and damaged return costs must be valid non-negative PHP amounts with at most two decimal places.')
        fair_cost=money_field('fair_cost','250.00')
        damage_cost=money_field('damage_cost','1000.00')
        try:
            quantity = int(f.get('add_quantity' if equipment_id else 'total_qty', '0' if equipment_id else '1'))
        except (TypeError, ValueError):
            raise ValueError('Quantity must be a whole number.')
        if quantity < (0 if equipment_id else 1) or quantity > 10000:
            raise ValueError('Enter a quantity from 1 to 10,000 (or 0 when keeping existing units).')
        c=db(); cur=c.cursor(dictionary=True)
        if equipment_id:
            cur.execute('SELECT * FROM equipment WHERE id=%s FOR UPDATE',(equipment_id,)); old=cur.fetchone()
            if not old or old.get('archived'): raise ValueError('Equipment not found or deleted.')
        else: old={}
        photo=save_equipment_image(request.files.get('equipment_image'),code) or old.get('image_filename')
        if equipment_id:
            cur.execute('UPDATE equipment SET asset_code=%s,name=%s,model=%s,category_id=%s,description=%s,condition_status=%s,location=%s,image_filename=%s,fair_cost=%s,damage_cost=%s WHERE id=%s',
                (code,name,model,f.get('category_id') or None,f.get('description'),condition,f.get('location'),photo,fair_cost,damage_cost,equipment_id))
        else:
            # Retained for compatibility only; physical serials live in equipment_units.
            cur.execute('INSERT INTO equipment(asset_code,serial_number,name,model,category_id,description,total_qty,available_qty,condition_status,location,image_filename,fair_cost,damage_cost) VALUES(%s,%s,%s,%s,%s,%s,0,0,%s,%s,%s,%s,%s)',
                (code,'GROUP-'+secrets.token_hex(12),name,model,f.get('category_id') or None,f.get('description'),condition,f.get('location'),photo,fair_cost,damage_cost))
            equipment_id=cur.lastrowid
        for _ in range(quantity):
            temporary = 'AUTO-PENDING-' + secrets.token_hex(16)
            cur.execute('INSERT INTO equipment_units(equipment_id,serial_number,condition_status,needs_serial) VALUES(%s,%s,%s,1)',(equipment_id,temporary,condition))
            assign_automatic_serial(cur,equipment_id,cur.lastrowid)
        refresh_unit_totals(cur,equipment_id); c.commit()
        flash('Equipment saved. A unique serial number was automatically generated for each new unit.','success')
    except ValueError as exc:
        if c: c.rollback()
        flash(str(exc),'danger')
    except psycopg.Error as exc:
        if c: c.rollback()
        flash('An asset code or serial number already exists. Every unit needs a unique serial number.' if exc.sqlstate=='23505' else 'Unable to save equipment. Check the database and try again.','danger')
    finally:
        if cur: cur.close()
        if c: c.close()
    return redirect(url_for('equipment'))


@app.route('/equipment/unit/<int:unit_id>/edit',methods=['POST'])
@admin_required('admin','staff')
def edit_unit(unit_id):
    if not verify_csrf(): abort(400)
    c=db(); cur=c.cursor(dictionary=True)
    try:
        cur.execute('SELECT equipment_id FROM equipment_units WHERE id=%s',(unit_id,)); ref=cur.fetchone()
        if not ref: abort(404)
        cur.execute('SELECT id,archived FROM equipment WHERE id=%s FOR UPDATE',(ref['equipment_id'],));equipment=cur.fetchone()
        if not equipment or equipment['archived']:raise ValueError('Equipment not found or deleted.')
        cur.execute('SELECT * FROM equipment_units WHERE id=%s FOR UPDATE',(unit_id,));u=cur.fetchone()
        condition=request.form.get('condition_status','Good')
        if condition not in ('Good','Fair','Damaged','For Repair'):raise ValueError('Invalid condition.')
        if u['current_request_id']:raise ValueError('Return this unit before changing its condition.')
        cur.execute('UPDATE equipment_units SET condition_status=%s WHERE id=%s',(condition,unit_id))
        refresh_unit_totals(cur,u['equipment_id']);c.commit();flash('Unit condition updated.','success')
    except ValueError as exc:c.rollback();flash(str(exc),'danger')
    except psycopg.Error:c.rollback();flash('Unable to save the unit condition. Please try again.','danger')
    finally:cur.close();c.close()
    return redirect(url_for('equipment'))


@app.route('/student/s/<scope>/request/<int:id>/damage',methods=['GET','POST'])
@student_required
def borrower_damage(scope,id):
    return damage_page(id,scope)


@app.route('/request/<int:id>/damage',methods=['GET','POST'])
@admin_required('admin','staff')
def personnel_damage(id):
    return damage_page(id)


def damage_page(id,scope=None):
    borrower=g.current_user['role'] in ('student','faculty')
    b=query('SELECT b.*,e.name,e.model,e.asset_code,e.image_filename,u.full_name FROM borrow_requests b JOIN equipment e ON e.id=b.equipment_id JOIN users u ON u.id=b.borrower_id WHERE b.id=%s',(id,),one=True)
    if not b or (borrower and b['borrower_id']!=g.current_user['id']):abort(404)
    if b['status'] not in ('Released','Overdue','Returned'):abort(400)
    if b['status']=='Returned' and b.get('return_condition')=='Good':
        if request.method=='POST':abort(403)
        return redirect(url_for('student_requests',scope=scope) if borrower else url_for('requests_page'))
    if request.method=='POST':
        if not verify_csrf():abort(400)
        action=request.form.get('action');c=db();cur=c.cursor(dictionary=True)
        message=None
        try:
            cur.execute('SELECT id FROM borrow_requests WHERE id=%s FOR UPDATE',(id,));cur.fetchone()
            cur.execute('SELECT * FROM equipment_damage WHERE request_id=%s FOR UPDATE',(id,));d=cur.fetchone()
            if action=='report':
                if d:raise ValueError('A condition report already exists for this transaction.')
                description=request.form.get('description','').strip()
                if len(description)<20 or len(description)>4000:raise ValueError('Describe the Fair/Damaged condition using 20–4,000 characters, including the affected serial number(s).')
                if borrower and request.form.get('responsibility')!='yes':raise ValueError('Please acknowledge responsibility before submitting the report.')
                cur.execute('INSERT INTO equipment_damage(request_id,description,reported_by,responsibility_ack_at) VALUES(%s,%s,%s,CASE WHEN %s=1 THEN NOW() ELSE NULL END)',(id,description,g.current_user['id'],borrower))
                if borrower:
                    cur.execute('UPDATE equipment_damage SET borrower_explanation=%s,explanation_at=NOW() WHERE request_id=%s',(description,id))
                message=f'Condition report for request #{id} was submitted. Review the Fair/Damaged condition and the applicable cost.'
            elif action in ('responsibility','explain') and borrower and d:
                if request.form.get('responsibility')!='yes':raise ValueError('Please check the responsibility acknowledgment.')
                explanation=request.form.get('borrower_explanation','').strip()
                if len(explanation)<20 or len(explanation)>4000:raise ValueError('Explain what happened, your actions, and the affected item using 20–4,000 characters.')
                if d.get('borrower_explanation'):raise ValueError('Your explanation is already recorded. Contact staff if a correction is needed.')
                cur.execute('UPDATE equipment_damage SET borrower_explanation=%s,explanation_at=NOW(),responsibility_ack_at=COALESCE(responsibility_ack_at,NOW()) WHERE request_id=%s',(explanation,id))
                message=f'The borrower acknowledged responsibility for the Fair/Damaged condition on request #{id}.'
            elif action=='assess' and not borrower and d:
                if d['paid_at']:raise ValueError('This assessment is settled and cannot be changed.')
                from decimal import Decimal, InvalidOperation
                try:
                    amount=Decimal(request.form.get('amount',''))
                    if not amount.is_finite() or amount<0 or amount>Decimal('99999999.99') or amount!=amount.quantize(Decimal('0.01')):raise ValueError()
                except (InvalidOperation,ValueError):raise ValueError('Enter a valid non-negative amount in PHP with at most two decimal places.')
                notes=request.form.get('assessment_notes','').strip()
                if not notes or len(notes)>4000:raise ValueError('Explain the repair/replacement cost or why no charge applies (up to 4,000 characters).')
                cur.execute('UPDATE equipment_damage SET amount=%s,assessment_notes=%s,assessed_by=%s,assessed_at=NOW(),assessment_version=assessment_version+1,cost_ack_at=NULL WHERE request_id=%s',(amount,notes,g.current_user['id'],id))
                message=f'Condition cost for request #{id}: PHP {amount:,.2f}. Open the condition report to review the cost and acknowledgment.'
            elif action=='ack_cost' and borrower and d:
                if not d.get('borrower_explanation') or not d['responsibility_ack_at']:raise ValueError('Submit your explanation and responsibility acknowledgment before accepting the cost.')
                if d['amount'] is None:raise ValueError('The cost has not been assessed yet.')
                if str(d['assessment_version'])!=request.form.get('version'):raise ValueError('The assessment changed. Refresh and review the latest amount.')
                if request.form.get('accept_cost')!='yes':raise ValueError('Please confirm that you accept the displayed cost.')
                cur.execute('UPDATE equipment_damage SET cost_ack_at=COALESCE(cost_ack_at,NOW()),responsibility_ack_at=COALESCE(responsibility_ack_at,NOW()) WHERE request_id=%s',(id,))
                message=f'The borrower accepted the assessed condition cost for request #{id}.'
            elif action=='paid' and not borrower and d:
                if d['amount'] is None or d['amount']<=0:raise ValueError('A positive assessed cost is required before recording payment.')
                if str(d['assessment_version'])!=request.form.get('version'):raise ValueError('The assessment changed. Refresh before recording payment.')
                if d['paid_at']:raise ValueError('Payment has already been recorded.')
                reference=request.form.get('payment_reference','').strip()
                if not reference or len(reference)>120:raise ValueError('Enter a receipt or payment reference (up to 120 characters).')
                cur.execute('UPDATE equipment_damage SET paid_at=NOW(),paid_by=%s,payment_reference=%s WHERE request_id=%s',(g.current_user['id'],reference,id))
                message=f'Payment recorded for request #{id}: PHP {d["amount"]:,.2f}. The condition charge is settled.'
            else:abort(403)
            c.commit()
        except ValueError as exc:
            c.rollback();message=None;error=str(exc)
        except Exception:c.rollback();raise
        finally:cur.close();c.close()
        if message:
            notify_user(b['borrower_id'],message)
            notify_personnel(message)
        return redirect(url_for('borrower_damage',scope=scope,id=id,notice=message or error) if borrower else url_for('personnel_damage',id=id,notice=message or error))
    d=query('SELECT * FROM equipment_damage WHERE request_id=%s',(id,),one=True)
    return render_template('damage.html',loan=attach_unit_serials([b])[0],damage=d,is_borrower=borrower)


def move_request_units(request_id, action, condition='Good', remarks=None, total_cost=None):
    """Lock inventory before the loan so a unit cannot be issued twice."""
    c=db();cur=c.cursor(dictionary=True)
    try:
        cur.execute('SELECT equipment_id FROM borrow_requests WHERE id=%s',(request_id,));ref=cur.fetchone()
        if not ref:raise ValueError('Request not found.')
        cur.execute('SELECT id,name,fair_cost,damage_cost,archived FROM equipment WHERE id=%s FOR UPDATE',(ref['equipment_id'],));equipment=cur.fetchone()
        cur.execute('SELECT * FROM borrow_requests WHERE id=%s FOR UPDATE',(request_id,));b=cur.fetchone()
        if action=='release':
            if equipment['archived']:raise ValueError('This equipment was deleted and cannot be released.')
            if b['status']!='Approved':raise ValueError('This request is no longer awaiting release.')
            cur.execute("""SELECT * FROM equipment_units
                WHERE equipment_id=%s AND active=1 AND current_request_id IS NULL
                  AND needs_serial=0 AND condition_status IN ('Good','Fair')
                ORDER BY id LIMIT %s FOR UPDATE""", (b['equipment_id'],b['quantity']))
            units=cur.fetchall()
            if len(units)!=b['quantity']:
                raise ValueError('Not enough available units to release this request. No units were issued.')
            for u in units:
                cur.execute('UPDATE equipment_units SET current_request_id=%s WHERE id=%s',(request_id,u['id']))
                cur.execute('INSERT INTO borrow_request_units(request_id,unit_id,serial_at_release) VALUES(%s,%s,%s)',(request_id,u['id'],u['serial_number']))
            cur.execute("UPDATE borrow_requests SET status='Released',released_at=NOW() WHERE id=%s",(request_id,))
        else:
            if b['status'] not in ('Released','Overdue'):raise ValueError('This request is no longer awaiting return.')
            cur.execute('SELECT id FROM equipment_units WHERE current_request_id=%s FOR UPDATE',(request_id,));units=cur.fetchall()
            if len(units)!=b['quantity']:raise ValueError('Unit assignments do not match this loan. Contact the administrator before returning it.')
            cur.execute('UPDATE equipment_units SET current_request_id=NULL,condition_status=%s WHERE current_request_id=%s',(condition,request_id))
            if condition=='Good' and not remarks:remarks='Equipment returned in good condition. No damage reported during inspection. Cost: PHP 0.00.'
            cur.execute("UPDATE borrow_requests SET status='Returned',returned_at=NOW(),return_condition=%s,remarks=%s WHERE id=%s",(condition,remarks,request_id))
        if action=='return' and condition in ('Fair','Damaged'):
            # Automatic charge applies ONLY to Fair and Damaged returns.
            per_unit = equipment['fair_cost'] if condition=='Fair' else equipment['damage_cost']
            amount = parse_condition_cost(total_cost) if total_cost is not None else per_unit * b['quantity']
            if amount>99999999.99:raise ValueError('Total condition cost exceeds the supported amount. Review the equipment rates.')
            condition_word = 'fair condition' if condition=='Fair' else 'damaged condition'
            default_detail = (
                f"Return inspection recorded {equipment['name']} in {condition_word}. "
                f"Automatic responsibility charge: PHP {per_unit:,.2f} per unit × {b['quantity']} unit(s)."
            )
            description = remarks or default_detail
            assessment_note = (
                f"Automatic {condition} return charge. PHP {per_unit:,.2f} per unit × "
                f"{b['quantity']} unit(s) = PHP {amount:,.2f}. "
                + (f"Inspection note: {remarks}" if remarks else 'No additional inspection note was entered.')
            )
            if total_cost is not None:
                default_detail=f"Return inspection recorded {equipment['name']} in {condition_word}. Total assessed cost: PHP {amount:,.2f}."
                description=remarks or default_detail
                assessment_note=f'Manually assessed total {condition} cost for this borrowing: PHP {amount:,.2f}. '+(remarks or 'Condition recorded during return inspection.')
            cur.execute('SELECT request_id,paid_at FROM equipment_damage WHERE request_id=%s FOR UPDATE',(request_id,))
            existing=cur.fetchone()
            if existing and existing['paid_at']:
                raise ValueError('This condition charge was already settled and cannot be replaced.')
            if existing:
                cur.execute('''UPDATE equipment_damage
                    SET description=COALESCE(NULLIF(description,''),%s), amount=%s, assessment_notes=%s,
                        assessed_by=%s, assessed_at=NOW(), assessment_version=assessment_version+1, cost_ack_at=NULL
                    WHERE request_id=%s''',
                    (description,amount,assessment_note,g.current_user['id'],request_id))
            else:
                cur.execute('''INSERT INTO equipment_damage
                    (request_id,description,reported_by,amount,assessment_notes,assessed_by,assessed_at,assessment_version)
                    VALUES(%s,%s,%s,%s,%s,%s,NOW(),1)''',
                    (request_id,description,g.current_user['id'],amount,assessment_note,g.current_user['id']))
        refresh_unit_totals(cur,b['equipment_id']);c.commit()
    except Exception:c.rollback();raise
    finally:cur.close();c.close()


@app.route('/equipment/<int:id>/delete', methods=['POST'])
@admin_required('admin','staff')
def delete_equipment(id):
    if not verify_csrf():abort(400)
    c=db();cur=c.cursor(dictionary=True)
    try:
        cur.execute('SELECT id,archived FROM equipment WHERE id=%s FOR UPDATE',(id,))
        item=cur.fetchone()
        if not item or item['archived']:raise ValueError('Equipment not found or already deleted.')
        cur.execute("SELECT id FROM borrow_requests WHERE equipment_id=%s AND status IN ('Pending','Approved','Released','Overdue') FOR UPDATE",(id,))
        if cur.fetchall():raise ValueError('Complete or reject unfinished borrowing requests before deleting this equipment.')
        cur.execute('SELECT id FROM equipment_units WHERE equipment_id=%s AND current_request_id IS NOT NULL FOR UPDATE',(id,))
        if cur.fetchall():raise ValueError('Return all issued units before deleting this equipment.')
        cur.execute('UPDATE equipment SET archived=1 WHERE id=%s',(id,))
        c.commit()
        flash('Equipment deleted from the catalog. Serial numbers, borrowing history and cost records are preserved.','success')
    except ValueError as exc:c.rollback();flash(str(exc),'danger')
    except psycopg.Error:c.rollback();flash('Unable to delete equipment. Please try again.','danger')
    finally:cur.close();c.close()
    return redirect(url_for('equipment'))


def parse_condition_cost(raw):
    from decimal import Decimal, InvalidOperation
    try:
        value=Decimal(raw)
        if not value.is_finite() or value<0 or value>Decimal('99999999.99') or value!=value.quantize(Decimal('0.01')):raise ValueError()
        return value
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError('Enter a total condition cost in PHP, from 0 to 99,999,999.99, with at most two decimal places.')


@app.route('/equipment/add', methods=['POST'])
@admin_required('admin', 'staff')
def add_equipment():
    if not verify_csrf(): abort(400)
    return save_inventory()


@app.route('/equipment/<int:id>/edit', methods=['POST'])
@admin_required('admin', 'staff')
def edit_equipment(id):
    if not verify_csrf(): abort(400)
    return save_inventory(id)


@app.route('/requests')
@admin_required('admin', 'staff')
def requests_page():
    cutoff = transaction_clear_cutoff(g.current_user['id'])
    rows = query(
        """
        SELECT b.*,e.name,e.model,e.serial_number,e.asset_code,e.fair_cost,e.damage_cost,
               u.full_name,u.school_id,u.role borrower_role,
               COALESCE(NULLIF(TRIM(u.department),''), NULLIF(TRIM(sr.program),''), 'UNASSIGNED') borrower_group,
               CASE WHEN b.status IN ('Released','Overdue') AND b.due_date<=CURRENT_DATE THEN 1 ELSE 0 END return_due
        FROM borrow_requests b
        JOIN equipment e ON e.id=b.equipment_id
        JOIN users u ON u.id=b.borrower_id
        LEFT JOIN student_records sr ON sr.user_id=u.id
        WHERE b.status IN ('Pending','Approved','Released','Overdue') OR b.id>%s
        ORDER BY b.id DESC
        """,
        (cutoff,)
    )
    rows = attach_unit_serials(rows)

    student_rows = []
    faculty_rows = []
    for row in rows:
        role = (row.get('borrower_role') or '').lower()
        group = (row.get('borrower_group') or 'UNASSIGNED').strip().upper()
        if role == 'student':
            row['borrower_group'] = group if group in STUDENT_COURSE_OPTIONS else 'UNASSIGNED'
            student_rows.append(row)
        elif role == 'faculty':
            row['borrower_group'] = group if group and group != 'UNASSIGNED' else 'Not specified'
            faculty_rows.append(row)

    course_options = list(STUDENT_COURSE_OPTIONS)
    if any(r.get('borrower_group') == 'UNASSIGNED' for r in student_rows):
        course_options.append('UNASSIGNED')
    student_course_counts = {
        course: sum(1 for r in student_rows if r.get('borrower_group') == course)
        for course in course_options
    }
    active_student_course = next(
        (course for course in course_options if student_course_counts.get(course, 0) > 0),
        course_options[0] if course_options else 'CCJS'
    )

    return render_template(
        'requests.html',
        rows=rows,
        student_rows=student_rows,
        faculty_rows=faculty_rows,
        transaction_course_options=course_options,
        student_course_counts=student_course_counts,
        active_student_course=active_student_course
    )


@app.route('/requests/clear-all', methods=['POST'])
@admin_required('admin', 'staff')
def requests_clear_all():
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400
    save_transaction_clear_cutoff(g.current_user['id'])
    flash('Transaction history cleared from this view. Active borrowing requests remain visible and all official records are preserved.', 'success')
    return redirect(url_for('requests_page'))


@app.route('/request/<int:id>/<action>', methods=['POST'])
@admin_required('admin', 'staff')
def request_action(id, action):
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400
    b = query('SELECT * FROM borrow_requests WHERE id=%s', (id,), one=True)
    if not b:
        return redirect(url_for('requests_page'))
    details = query(
        'SELECT b.*,e.name equipment_name,e.model equipment_model,u.full_name borrower_name FROM borrow_requests b JOIN equipment e ON e.id=b.equipment_id JOIN users u ON u.id=b.borrower_id WHERE b.id=%s',
        (id,), one=True
    ) or b
    if action in ('approve', 'reject') and b['status'] == 'Pending':
        status = 'Approved' if action == 'approve' else 'Rejected'
        remarks = (request.form.get('remarks') or '').strip()
        query('UPDATE borrow_requests SET status=%s,reviewed_by=%s,reviewed_at=NOW(),remarks=%s WHERE id=%s', (status, g.current_user['id'], remarks or None, id), commit=True)
        if status == 'Approved':
            notify_user(
                b['borrower_id'],
                f"Approved: request #{id} for {details['equipment_name']} was approved. Borrow date: {b['borrow_date']}; due date: {b['due_date']}."
            )
        else:
            suffix = f" Reason: {remarks}" if remarks else ''
            notify_user(
                b['borrower_id'],
                f"Rejected: request #{id} for {details['equipment_name']} was not approved.{suffix}"
            )
    elif action == 'release' and b['status'] == 'Approved':
        try:
            move_request_units(id,'release')
        except ValueError as exc:
            flash(str(exc),'danger')
            return redirect(url_for('requests_page'))
        notify_user(b['borrower_id'], f"Released: {details['equipment_name']} for request #{id}. View your transaction for the issued serial numbers. Due: {b['due_date']}.")
    elif action == 'return' and b['status'] in ('Released', 'Overdue'):
        return_condition = request.form.get('return_condition', 'Good')
        if return_condition not in ('Good', 'Fair', 'Damaged'):
            flash('Select a valid return condition.', 'danger')
            return redirect(url_for('requests_page'))
        remarks = (request.form.get('remarks') or '').strip()
        try:
            cost=parse_condition_cost(request.form.get('condition_cost','')) if return_condition in ('Fair','Damaged') else None
            move_request_units(id,'return',return_condition,remarks or None,total_cost=cost)
        except ValueError as exc:
            flash(str(exc),'danger')
            return redirect(url_for('requests_page'))
        if return_condition in ('Fair','Damaged'):
            assessed=query('SELECT amount FROM equipment_damage WHERE request_id=%s',(id,),one=True)
            charge=assessed['amount']
            condition_note=f'{return_condition} condition requires a responsibility note. A total cost of PHP {charge:,.2f} was recorded. Open Condition Report / Cost to review and acknowledge it.'
        else:
            condition_note='The equipment was received in good condition. Condition note recorded. Cost: PHP 0.00. No damage responsibility is required.'
        notify_user(
            b['borrower_id'],
            f"Return approved: {details['equipment_name']} for request #{id} was received and inspected. Condition: {return_condition}. {condition_note}"
        )
        notify_personnel(
            f"Equipment returned: {details['borrower_name']} returned {details['equipment_name']} for request #{id}. Condition: {return_condition}.",
            exclude_user_id=None
        )
    flash('Transaction updated.', 'success')
    return redirect(url_for('requests_page'))


@app.route('/users', methods=['GET', 'POST'])
@admin_required('admin')
def users():
    if request.method == 'POST':
        if not verify_csrf():
            return 'Invalid security token. Refresh the page and try again.', 400
        f = request.form
        try:
            if f['record_type'] == 'student':
                course = (f.get('department') or '').strip().upper()
                if course not in STUDENT_COURSE_OPTIONS:
                    flash('Select a valid student course: CCJS, CITE, COTE, COHM, or COTM.', 'danger')
                    return redirect(url_for('users'))
                query(
                    'INSERT INTO student_records(student_id,full_name,email,program,year_level,section) VALUES(%s,%s,%s,%s,%s,%s)',
                    (f['school_id'], f['full_name'], f.get('email') or None, course, f.get('year_level'), f.get('section')), commit=True
                )
                flash('Student record created. The student can now activate an account and create a private password.', 'success')
            else:
                role = f.get('role')
                if role == 'faculty':
                    department = (f.get('department') or '').strip().upper()
                    if department not in FACULTY_DEPARTMENT_OPTIONS:
                        flash('Select a valid Faculty Department / Office: CCJS, CITE, COHM, or COTM.', 'danger')
                        return redirect(url_for('users'))
                    query(
                        "INSERT INTO users(school_id,full_name,email,password_hash,role,department,active,activation_required) VALUES(%s,%s,%s,NULL,'faculty',%s,0,1)",
                        (f['school_id'], f['full_name'], f.get('email') or None, department), commit=True
                    )
                    flash('Faculty record created. The faculty member must use Activate Account to create a private password and accept the borrower agreement.', 'success')
                else:
                    if role not in ('admin', 'staff') or len(f.get('password', '')) < 6:
                        flash('Select a valid personnel role and a password with at least 6 characters.', 'danger')
                        return redirect(url_for('users'))
                    query(
                        'INSERT INTO users(school_id,full_name,email,password_hash,role,department,active,activation_required) VALUES(%s,%s,%s,%s,%s,%s,1,0)',
                        (f['school_id'], f['full_name'], f.get('email') or None, generate_password_hash(f['password']), role, f.get('department')), commit=True
                    )
                    flash('Personnel account created.', 'success')
        except Exception:
            flash('School/Student ID or email already exists.', 'danger')
    records = query("SELECT sr.*, u.id account_id, u.active account_active FROM student_records sr LEFT JOIN users u ON u.id=sr.user_id WHERE sr.active=1 ORDER BY sr.id DESC")
    student_course_groups = []
    for course in STUDENT_COURSE_OPTIONS:
        grouped_records = [row for row in records if (row.get('program') or '').strip().upper() == course]
        student_course_groups.append({'key': course, 'label': course, 'records': grouped_records})
    legacy_student_records = [row for row in records if (row.get('program') or '').strip().upper() not in STUDENT_COURSE_OPTIONS]
    if legacy_student_records:
        student_course_groups.append({'key': 'UNASSIGNED', 'label': 'Legacy / Unassigned', 'records': legacy_student_records})
    personnel = query("SELECT id,school_id,full_name,email,role,department,active,created_at FROM users WHERE role IN ('admin','staff') AND active=1 ORDER BY id DESC")
    faculty = query("SELECT id,school_id,full_name,email,role,department,active,activation_required,created_at FROM users WHERE role='faculty' AND (active=1 OR activation_required=1) ORDER BY id DESC")
    return render_template('users.html', records=records, student_course_groups=student_course_groups, personnel=personnel, faculty=faculty)


@app.route('/users/student/<int:record_id>/delete', methods=['POST'])
@admin_required('admin')
def delete_student_record(record_id):
    """Remove a student from active administration records without breaking history.

    Students with no borrowing history are deleted completely. If transaction
    history exists, the account and registry record are deactivated instead so
    reports and old borrowing/return records remain valid.
    """
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400

    record = query('SELECT * FROM student_records WHERE id=%s', (record_id,), one=True)
    if not record:
        flash('Student record was not found.', 'danger')
        return redirect(url_for('users'))

    c = db()
    cur = c.cursor(dictionary=True)
    try:
        uid = record.get('user_id')
        if uid:
            cur.execute('SELECT COUNT(*) n FROM borrow_requests WHERE borrower_id=%s', (uid,))
            history_count = cur.fetchone()['n']
            if history_count:
                cur.execute('UPDATE users SET active=0 WHERE id=%s AND role=\'student\'', (uid,))
                cur.execute('UPDATE student_records SET active=0 WHERE id=%s', (record_id,))
                try:
                    cur.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=%s', (uid,))
                except Exception:
                    # Older databases may not yet have the support table.
                    pass
                c.commit()
                flash('Student removed from active records. Existing borrowing history was preserved.', 'success')
            else:
                # Deleting the user also clears auth sessions/notifications through
                # foreign-key cascades; student_records is removed afterward.
                cur.execute('DELETE FROM users WHERE id=%s AND role=\'student\'', (uid,))
                cur.execute('DELETE FROM student_records WHERE id=%s', (record_id,))
                c.commit()
                flash('Student account and record deleted successfully.', 'success')
        else:
            cur.execute('DELETE FROM student_records WHERE id=%s', (record_id,))
            c.commit()
            flash('Student record deleted successfully.', 'success')
    except Exception:
        c.rollback()
        flash('Unable to remove this student because the record is still required by another transaction.', 'danger')
    finally:
        cur.close()
        c.close()
    return redirect(url_for('users'))


@app.route('/users/faculty/<int:user_id>/delete', methods=['POST'])
@admin_required('admin')
def delete_faculty_account(user_id):
    """Delete faculty accounts using the same rules as student accounts.

    Faculty accounts with no borrowing history are deleted completely. If
    borrowing history exists, the account is deactivated instead so all old
    borrowing/return records remain available in reports.
    """
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400

    faculty = query(
        "SELECT id,school_id,full_name,role,active FROM users WHERE id=%s AND role='faculty' LIMIT 1",
        (user_id,), one=True
    )
    if not faculty:
        flash('Faculty account was not found.', 'danger')
        return redirect(url_for('users'))

    c = db()
    cur = c.cursor(dictionary=True)
    try:
        cur.execute('SELECT COUNT(*) n FROM borrow_requests WHERE borrower_id=%s', (user_id,))
        history_count = int(cur.fetchone()['n'])

        if history_count:
            cur.execute("UPDATE users SET active=0,activation_required=0 WHERE id=%s AND role='faculty'", (user_id,))
            try:
                cur.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=%s', (user_id,))
            except psycopg.Error:
                pass
            c.commit()
            flash('Faculty removed from active records. Existing borrowing history was preserved.', 'success')
        else:
            cur.execute("DELETE FROM users WHERE id=%s AND role='faculty'", (user_id,))
            c.commit()
            flash('Faculty account deleted successfully.', 'success')
    except Exception:
        c.rollback()
        flash('Unable to remove this faculty account because the record is still required by another transaction.', 'danger')
    finally:
        cur.close()
        c.close()
    return redirect(url_for('users'))


@app.route('/users/account/<int:user_id>/delete', methods=['POST'])
@admin_required('admin')
def delete_managed_account(user_id):
    """Remove faculty/personnel accounts safely while preserving historical records."""
    if not verify_csrf():
        return 'Invalid security token. Refresh the page and try again.', 400

    target = query(
        "SELECT id,school_id,full_name,role,active FROM users WHERE id=%s AND role IN ('admin','staff','faculty') LIMIT 1",
        (user_id,), one=True
    )
    if not target:
        flash('Faculty or personnel account was not found.', 'danger')
        return redirect(url_for('users'))

    # Never allow the signed-in administrator to remove the account that is
    # currently authorizing this action.
    if int(target['id']) == int(g.current_user['id']):
        flash('You cannot delete the administrator account you are currently using.', 'danger')
        return redirect(url_for('users'))

    # The system must always retain at least one active administrator.
    if target['role'] == 'admin':
        active_admins = query("SELECT COUNT(*) n FROM users WHERE role='admin' AND active=1", one=True)
        if int(active_admins['n']) <= 1:
            flash('The last active administrator cannot be deleted.', 'danger')
            return redirect(url_for('users'))

    c = db()
    cur = c.cursor(dictionary=True)
    try:
        # Accounts referenced by operational records are archived/deactivated
        # instead of being physically deleted. This keeps reports, reviewer
        # attribution, responsibility records and payment records intact.
        cur.execute(
            'SELECT COUNT(*) n FROM borrow_requests WHERE borrower_id=%s OR reviewed_by=%s',
            (user_id, user_id)
        )
        request_history = int(cur.fetchone()['n'])

        damage_history = 0
        try:
            cur.execute(
                'SELECT COUNT(*) n FROM equipment_damage WHERE reported_by=%s OR assessed_by=%s OR paid_by=%s',
                (user_id, user_id, user_id)
            )
            damage_history = int(cur.fetchone()['n'])
        except psycopg.Error:
            # Compatibility with an older database before the support table
            # was added. No deletion decision depends on a missing table.
            damage_history = 0

        has_history = bool(request_history or damage_history)
        role_label = 'Faculty' if target['role'] == 'faculty' else ('Administrator' if target['role'] == 'admin' else 'Staff')

        if has_history:
            cur.execute('UPDATE users SET active=0 WHERE id=%s', (user_id,))
            try:
                cur.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=%s', (user_id,))
            except psycopg.Error:
                pass
            c.commit()
            flash(f'{role_label} account removed from the active directory. Existing system history was safely preserved.', 'success')
        else:
            cur.execute('DELETE FROM users WHERE id=%s', (user_id,))
            c.commit()
            flash(f'{role_label} account deleted successfully.', 'success')
    except psycopg.Error:
        c.rollback()
        flash('Unable to delete this account because it is still required by a system record.', 'danger')
    finally:
        cur.close()
        c.close()
    return redirect(url_for('users'))


@app.route('/notifications')
@admin_required('admin', 'staff')
def notifications():
    uid = g.current_user['id']
    rows = query('SELECT * FROM notifications WHERE user_id=%s ORDER BY id DESC', (uid,))
    return render_template('notifications.html', rows=rows)


@app.route('/notifications/read-all', methods=['POST'])
@admin_required('admin', 'staff')
def notifications_read_all():
    mark_all_notifications_read()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))


@app.route('/notifications/<int:id>')
@admin_required('admin', 'staff')
def notification_detail(id):
    return render_notification_detail(id)


@app.route('/api/notifications')
@admin_required('admin', 'staff')
def notifications_api():
    return jsonify(notification_payload(g.current_user['id']))


@app.route('/reports')
@admin_required('admin', 'staff')
def reports():
    summary = query("SELECT status,COUNT(*) total FROM borrow_requests GROUP BY status")
    recent = query('SELECT b.*,u.full_name,u.role borrower_role,e.name,e.model,e.serial_number FROM borrow_requests b JOIN users u ON u.id=b.borrower_id JOIN equipment e ON e.id=b.equipment_id ORDER BY b.id DESC')
    return render_template('reports.html', summary=summary, recent=attach_unit_serials(recent))


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/logout')
def logout_legacy():
    if _admin_identity():
        return redirect(url_for('admin_logout'))
    return redirect(url_for('student_login'))


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1')
