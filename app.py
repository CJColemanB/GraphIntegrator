from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename
from openpyxl import load_workbook


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB limit
DB_NAME = 'people.db'


def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE person (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forename TEXT NOT NULL,
                middle_name TEXT,
                surname TEXT NOT NULL,
                dob TEXT NOT NULL,
                subject TEXT NOT NULL,
                grade TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    # Create upload folder if not exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

init_db()


@app.route('/')
def index():
    return render_template('home.html')

@app.route('/add', methods=['GET', 'POST'])
def add_person():
    grades = ['A*', 'A', 'B', 'C', 'D', 'E', 'F', 'U']
    subjects = ['Math', 'English', 'Science', 'History', 'Geography']
    if request.method == 'POST':
        forename = request.form['forename']
        middle_name = request.form.get('middle_name', '')
        surname = request.form['surname']
        dob = request.form['dob']
        subject = request.form['subject']
        grade = request.form['grade']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO person (forename, middle_name, surname, dob, subject, grade) VALUES (?, ?, ?, ?, ?, ?)''',
                  (forename, middle_name, surname, dob, subject, grade))
        conn.commit()
        conn.close()
        return redirect(url_for('list_people'))
    return render_template('add_person.html', grades=grades, subjects=subjects)

@app.route('/list')
def list_people():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT forename, middle_name, surname, dob, subject, grade FROM person')
    people = c.fetchall()
    conn.close()
    return render_template('list_people.html', people=people)


# Excel upload route
@app.route('/upload', methods=['GET', 'POST'])
def upload_excel():
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
                            conn = sqlite3.connect(DB_NAME)
                            c = conn.cursor()
                            c.execute('''INSERT INTO person (forename, middle_name, surname, dob, subject, grade) VALUES (?, ?, ?, ?, ?, ?)''',
                                      (data['forename'], data.get('middle_name', ''), data['surname'], data['dob'], data['subject'], data['grade']))
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
