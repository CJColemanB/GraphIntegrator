import json
import hashlib
from flask import Flask, render_template, request, redirect, url_for, make_response
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename
from openpyxl import load_workbook

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit

# User table for login
def init_user_db():
    if not os.path.exists('users.db'):
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
init_user_db()

def get_db_name():
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
    return f"people_{user_id}.db", user_id

def init_db(db_name):
    if not os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE person (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forename TEXT NOT NULL,
                middle_name TEXT,
                surname TEXT NOT NULL,
                dob TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade INTEGER NOT NULL CHECK(grade >= 0 AND grade <= 100)
            )
        ''')
        conn.commit()
        conn.close()
    # Create upload folder if not exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

init_db("people.db")

## Duplicate cookie_consent route removed

## Duplicate index route removed

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            error = "Username and password required."
        else:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('SELECT id, password FROM user WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()
            if user and user[1] == hashlib.sha256(password.encode()).hexdigest():
                resp = make_response(redirect(url_for('index')))
                resp.set_cookie('user_id', str(user[0]), max_age=60*60*24*365)
                return resp
            else:
                error = "Invalid credentials."
    return render_template('login.html', error=error)

@app.route('/graphs', methods=['GET', 'POST'])
def graphs():
    db_name, user_id = get_db_name()
    init_db(db_name)
    graph_type = 'line'
    graph_data = None
    if request.method == 'POST':
        graph_type = request.form.get('graph_type', 'line')
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute('SELECT forename, grade FROM person ORDER BY id')
    rows = c.fetchall()
    conn.close()
    labels = [row[0] for row in rows]
    values = [row[1] for row in rows]
    if labels and values:
        graph_data = {
            'labels': json.dumps(labels),
            'values': json.dumps(values)
        }
    return render_template('graphs.html', graph_type=graph_type, graph_data=graph_data)
    conn.commit()
    conn.close()
# Create upload folder if not exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

init_db("people.db")



@app.route('/cookie-consent', methods=['GET', 'POST'])
def cookie_consent():
    if request.method == 'POST':
        user_id = str(uuid.uuid4())
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('user_id', user_id, max_age=60*60*24*365)
        return resp
    return render_template('cookie_consent.html')

@app.route('/')
def index():
    if not request.cookies.get('user_id'):
        return redirect(url_for('cookie_consent'))
    db_name, user_id = get_db_name()
    resp = make_response(render_template('home.html'))
    init_db(db_name)
    return resp

@app.route('/add', methods=['GET', 'POST'])
def add_person():
    db_name, user_id = get_db_name()
    init_db(db_name)
    subjects = ['Math', 'English', 'Science', 'History', 'Geography']
    error = None
    if request.method == 'POST':
        forename = request.form['forename'].strip()
        middle_name = request.form.get('middle_name', '').strip()
        surname = request.form['surname'].strip()
        dob = request.form['dob'].strip()
        subject = request.form['subject'].strip()
        grade = request.form['grade'].strip()
        # Data integrity checks
        if not forename or not surname or not dob or not subject or not grade:
            error = "All required fields must be filled."
        elif not subject in subjects:
            error = "Invalid subject."
        try:
            grade_int = int(grade)
            if not (0 <= grade_int <= 100):
                error = "Grade must be between 0 and 100."
        except ValueError:
            error = "Grade must be a number between 0 and 100."
        # Simple date format check (YYYY-MM-DD)
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
            error = "Date of Birth must be in YYYY-MM-DD format."
        if not error:
            conn = sqlite3.connect(db_name)
            c = conn.cursor()
            c.execute('''INSERT INTO person (forename, middle_name, surname, dob, subject, grade) VALUES (?, ?, ?, ?, ?, ?)''',
                      (forename, middle_name, surname, dob, subject, grade_int))
            conn.commit()
            conn.close()
            return redirect(url_for('list_people'))
    return render_template('add_person.html', subjects=subjects, error=error)

@app.route('/list', methods=['GET', 'POST'])
def list_people():
    db_name, user_id = get_db_name()
    init_db(db_name)
    # Remove person
    if request.method == 'POST':
        person_id = request.form.get('remove_id')
        if person_id:
            conn = sqlite3.connect(db_name)
            c = conn.cursor()
            c.execute('DELETE FROM person WHERE id = ?', (person_id,))
            conn.commit()
            conn.close()
    # Search and sort
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'forename')
    order = request.args.get('order', 'asc')
    valid_sort = ['forename', 'surname', 'dob', 'grade']
    if sort_by not in valid_sort:
        sort_by = 'forename'
    order_sql = 'ASC' if order == 'asc' else 'DESC'
    query = 'SELECT id, forename, middle_name, surname, dob, subject, grade FROM person'
    params = []
    if search:
        query += ' WHERE forename LIKE ? OR surname LIKE ?'
        params.extend([f'%{search}%', f'%{search}%'])
    query += f' ORDER BY {sort_by} {order_sql}'
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query, params)
    people = c.fetchall()
    conn.close()
    return render_template('list_people.html', people=people)


# Excel upload route
@app.route('/upload', methods=['GET', 'POST'])
def upload_excel():
    db_name, user_id = get_db_name()
    init_db(db_name)
    error = None
    success = None
    required_headers = ['forename', 'middle_name', 'surname', 'dob', 'subject', 'grade']
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            error = 'No file part.'
        else:
            file = request.files['excel_file']
            if file.filename == '':
                error = 'No selected file.'
            elif not file.filename.lower().endswith('.xlsx'):
                error = 'File must be .xlsx format.'
            else:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                try:
                    wb = load_workbook(filepath)
                    ws = wb.active
                    headers = [str(cell.value).strip().lower() for cell in next(ws.iter_rows(min_row=1, max_row=1))]
                    missing = [h for h in required_headers if h not in headers]
                    unsupported = [h for h in headers if h not in required_headers]
                    if missing:
                        error = f"Missing required headers: {', '.join(missing)}"
                    elif unsupported:
                        error = f"Unsupported headers found: {', '.join(unsupported)}"
                    else:
                        count = 0
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            data = dict(zip(headers, row))
                            # Data integrity checks
                            try:
                                forename = str(data['forename']).strip()
                                middle_name = str(data.get('middle_name', '')).strip()
                                surname = str(data['surname']).strip()
                                dob = str(data['dob']).strip()
                                subject = str(data['subject']).strip()
                                grade = str(data['grade']).strip()
                                if not forename or not surname or not dob or not subject or not grade:
                                    continue
                                if subject not in ['Math', 'English', 'Science', 'History', 'Geography']:
                                    continue
                                grade_int = int(grade)
                                if not (0 <= grade_int <= 100):
                                    continue
                                import re
                                if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
                                    continue
                            except Exception:
                                continue
                            conn = sqlite3.connect(db_name)
                            c = conn.cursor()
                            c.execute('''INSERT INTO person (forename, middle_name, surname, dob, subject, grade) VALUES (?, ?, ?, ?, ?, ?)''',
                                      (forename, middle_name, surname, dob, subject, grade_int))
                            conn.commit()
                            conn.close()
                            count += 1
                        success = f"Successfully imported {count} records."
                except Exception as e:
                    error = f"Error reading Excel file: {str(e)}"
                finally:
                    os.remove(filepath)
    return render_template('upload_excel.html', error=error, success=success)

if __name__ == '__main__':
    app.run(debug=True)
