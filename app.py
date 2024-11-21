import csv
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
from flask.json import jsonify
from sqlalchemy import and_
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///late_attendance.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Flask-Login required attributes and methods
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    
class Student(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(1), nullable=False)
    parent_email = db.Column(db.String(100), nullable=False)
    parent_mobile = db.Column(db.String(15), nullable=False)
    late_count = db.Column(db.Integer, default=0)
    week_late_count = db.Column(db.Integer, default=0)
    month_late_count = db.Column(db.Integer, default=0)

    def get_id(self):
        return str(self.id)

class DisciplineIncharge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Faculty(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(1), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class HOD(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class Principal(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class LateAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    date = db.Column(db.Date, nullable=False)
    student = db.relationship('Student', backref='late_attendance_records')

@login_manager.user_loader
def load_user(user_id):
    # Load user from any role
    user = Student.query.get(int(user_id)) or Faculty.query.get(int(user_id)) or \
           HOD.query.get(int(user_id)) or Principal.query.get(int(user_id)) or Admin.query.get(int(user_id))
    return user

def reset_attendance_counts():
    today = datetime.now()
    if today.weekday() == 0:  # Monday
        students = Student.query.all()
        for student in students:
            student.week_late_count = 0
    if today.day == 1:  # First day of the month
        students = Student.query.all()
        for student in students:
            student.month_late_count = 0
    db.session.commit()

# Start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=reset_attendance_counts, trigger="interval", days=1)
scheduler.start()

# Load students from CSV
def load_students_from_csv(file_path):
    with open(file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            new_student = Student(
                name=row['name'],
                roll_no=row['roll_no'],
                year=int(row['year']),
                department=row['department'],
                section=row['section'],
                parent_email=row['parent_email'],
                parent_mobile=row['parent_mobile']
            )
            db.session.add(new_student)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html', title="Late Attendance System")

# Route for Student Login
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate Student credentials
        student = Student.query.filter_by(roll_no=username).first()
        if student and student.roll_no == password:
            login_user(student)
            return redirect(url_for('student_dashboard'))

        # Invalid credentials
        flash('Invalid login credentials', 'danger')
    
    return render_template('student_login.html', title="Student Login")

# Route for Shared Login for all other roles
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate Discipline Incharge
        discipline_incharge = DisciplineIncharge.query.filter_by(name=username).first()
        if discipline_incharge and discipline_incharge.password == password:
            session['user_type'] = 'DisciplineIncharge'
            return redirect(url_for('discipline_incharge_dashboard'))

        # Validate Faculty
        faculty = Faculty.query.filter_by(name=username).first()
        if faculty and faculty.password == password:
            login_user(faculty)
            session['user_type'] = 'Faculty'
            return redirect(url_for('faculty_dashboard'))

        # Validate HOD
        hod = HOD.query.filter_by(name=username).first()
        if hod and hod.password == password:
            login_user(hod)
            session['user_type'] = 'HOD'
            return redirect(url_for('hod_dashboard'))

        # Validate Principal
        principal = Principal.query.filter_by(name=username).first()
        if principal and principal.password == password:
            login_user(principal)
            session['user_type'] = 'Principal'
            return redirect(url_for('principal_dashboard'))

        # Validate Admin
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.password == password:
            login_user(admin)
            session['user_type'] = 'Admin'
            return redirect(url_for('admin_dashboard'))

        # Invalid credentials
        flash('Invalid login credentials', 'danger')

    return render_template('login.html', title="Login")


@app.route('/logout')
def logout():
    session.clear()
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if session.get('user_type') != 'Admin':
        return redirect(url_for('index'))

    return render_template('admin_dashboard.html')
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    student = current_user
    late_records = LateAttendance.query.filter_by(student_id=student.id).all()
    return render_template('student_dashboard.html', student=student, late_records=late_records, title="Student Dashboard")

@app.route('/discipline_incharge_register', methods=['GET', 'POST'])
def discipline_incharge_register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        new_incharge = DisciplineIncharge(name=name, password=password)
        db.session.add(new_incharge)
        db.session.commit()
        flash('Discipline Incharge registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('discipline_incharge_register.html', title="Discipline Incharge Register")

@app.route('/discipline_incharge_dashboard', methods=['GET', 'POST'])
def discipline_incharge_dashboard():
    today = date.today()

    # Fetch late records only for today
    late_records_today = LateAttendance.query.filter_by(date=today).all()
    
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        student = Student.query.filter_by(roll_no=roll_no).first()
        
        if student:
            existing_record = LateAttendance.query.filter_by(student_id=student.id, date=today).first()
            if existing_record:
                flash('Student has already been marked late today.', 'danger')
            else:
                late_record = LateAttendance(student_id=student.id, date=today)
                db.session.add(late_record)
                student.late_count += 1
                student.week_late_count += 1
                student.month_late_count += 1
                db.session.commit()
                flash(f"{student.name} marked late for today", 'success')
                if student.late_count % 3 == 0:
                    send_email_notification(student.parent_email, student.name)
                    send_sms_notification(student.parent_mobile, student.name)
        else:
            flash('Student not found', 'danger')

    # Preparing late records for the display
    students = []
    for record in late_records_today:
        student = Student.query.get(record.student_id)
        if student:
            students.append({
                'name': student.name,
                'roll_no': student.roll_no,
                'year': student.year,
                'department': student.department,
                'total_late': student.late_count,
                'late_this_week': student.week_late_count,
                'late_this_month': student.month_late_count,
                'record_id': record.id
            })

    return render_template('discipline_incharge.html', title="Discipline In-Charge Dashboard", students=students, today=today)

@app.route('/delete_late_record/<int:record_id>', methods=['POST'])
def delete_late_record(record_id):
    record = LateAttendance.query.get(record_id)
    if record:
        student = Student.query.get(record.student_id)
        if student:
            # Decrement the counts
            student.late_count = max(0, student.late_count - 1)
            student.week_late_count = max(0, student.week_late_count - 1)
            student.month_late_count = max(0, student.month_late_count - 1)
            db.session.delete(record)
            db.session.commit()
            flash('Today\'s late attendance record deleted successfully.', 'success')
        else:
            flash('Student not found.', 'danger')
    else:
        flash('Record not found.', 'danger')
    return redirect(url_for('discipline_incharge_dashboard'))

# Route to view previous days' late attendance
@app.route('/view_previous_attendance', methods=['GET'])
def view_previous_attendance():
    # Fetch all late attendance records that are not for today
    today = date.today()
    previous_records = LateAttendance.query.filter(LateAttendance.date < today).all()

    # Prepare data for display
    previous_students = []
    for record in previous_records:
        student = Student.query.get(record.student_id)
        if student:
            previous_students.append({
                'name': student.name,
                'roll_no': student.roll_no,
                'year': student.year,
                'department': student.department,
                'date': record.date,
                'record_id': record.id
            })

    return render_template('view_previous_attendance.html', title="Previous Late Attendance", students=previous_students)


@app.route('/faculty_register', methods=['GET', 'POST'])
def faculty_register():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        year = int(request.form['year'])
        section = request.form['section']
        password = request.form['password']
        new_faculty = Faculty(name=name, department=department, year=year, section=section, password=password)
        db.session.add(new_faculty)
        db.session.commit()
        flash('Faculty registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('faculty_register.html', title="Faculty Register")

@app.route('/faculty_dashboard', methods=['GET'])
@login_required
def faculty_dashboard():
    # Check if the logged-in user is a faculty member
    if session.get('user_type') != 'Faculty':
        return redirect(url_for('index'))
    
    # Retrieve the faculty member's details
    faculty = Faculty.query.get(current_user.id)
    if not faculty:
        flash("Faculty member not found!", "danger")
        return redirect(url_for('index'))

    # Extract faculty details
    department = faculty.department
    year = faculty.year
    section = faculty.section
    name = faculty.name

    # Fetch students from the faculty's department, year, and section
    students = Student.query.filter_by(department=department, year=year, section=section).all()

    # Get today's date and the start and end of the current week
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    # Collect late attendance data for the week
    attendance_data = []
    total_late_students_today = 0

    for student in students:
        week_status = []
        lifetime_late_count = LateAttendance.query.filter_by(student_id=student.id).count()  # Total lifetime late count

        # Check each date in the week
        for day in week_dates:
            record = LateAttendance.query.filter_by(student_id=student.id, date=day).first()
            week_status.append('Yes' if record else 'No')

        # Increment today's late count if the student is late today
        if LateAttendance.query.filter_by(student_id=student.id, date=today).first():
            total_late_students_today += 1

        attendance_data.append({
            'roll_no': student.roll_no,
            'name': student.name,
            'week_status': week_status,
            'lifetime_late_count': lifetime_late_count
        })

    # Filter late students for today
    late_students_today = [student for student in students if LateAttendance.query.filter_by(student_id=student.id, date=today).first()]

    return render_template(
        'faculty_dashboard.html',
        faculty_name=name,
        department=department,
        year=year,
        section=section,
        today=today,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
        week_dates=week_dates,
        attendance_data=attendance_data,
        late_students_today=late_students_today,
        total_late_students_today=total_late_students_today,
        title="Faculty Dashboard"
    )



# HOD Registration and Dashboard
@app.route('/hod_register', methods=['GET', 'POST'])
def hod_register():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        password = request.form['password']
        new_hod = HOD(name=name, department=department, password=password)
        db.session.add(new_hod)
        db.session.commit()
        flash('HOD registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('hod_register.html', title="HOD Register")

@app.route('/hod_dashboard', methods=['GET', 'POST'])
@login_required
def hod_dashboard():
    # Check if the logged-in user is an HOD
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = HOD.query.get(current_user.id)
    if not hod:
        flash("HOD not found!", "danger")
        return redirect(url_for('index'))

    department = hod.department

    # Debug: Check if department is correctly captured
    print("HOD Department:", department)

    # Fetch students only from the HOD's department
    # Use case-insensitive filter if needed
    students = Student.query.filter(Student.department.ilike(department)).all()
 

    # Debug: Check if students are fetched correctly
    print("Students in department:", len(students))

    # Define all years and sections
    all_years = [1, 2, 3, 4]  # Adjust for your college structure
    all_sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']  # Adjust based on your sections

    # Initialize late attendance summary
    attendance_summary = {year: {section: 0 for section in all_sections} for year in all_years}
    late_students_detail = {year: {section: [] for section in all_sections} for year in all_years}

    # Handle the date filter for the calendar
    selected_date = date.today()
    if request.method == 'POST':
        date_str = request.form.get('date')
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Update counts and details for the selected date
    for student in students:
        year = student.year
        section = student.section

        # Check if the section is in the defined sections
        if section not in all_sections:
            continue  # Skip if the section is not recognized

        # Check if there is a LateAttendance record for the student on the selected date
        late_record = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).first()
        
        if late_record:  # If a late record exists, the student is considered late
            attendance_summary[year][section] += 1
            late_students_detail[year][section].append({
                'roll_no': student.roll_no,
                'name': student.name
            })

    return render_template(
        'hod_dashboard.html',
        hod_name=hod.name,
        department=department,
        attendance_summary=attendance_summary,
        late_students_detail=late_students_detail,
        selected_date=selected_date
    )



@app.route('/calendar_view')
@login_required
def calendar_view():
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = HOD.query.get(current_user.id)
    if not hod:
        flash("HOD not found!", "danger")
        return redirect(url_for('index'))

    department = hod.department
    all_years = [1, 2, 3, 4]
    all_sections = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

    # Get attendance for a selected date
    selected_date = request.args.get('date')
    if not selected_date:
        selected_date = date.today()
    else:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()

    attendance_summary = {year: {section: 0 for section in all_sections} for year in all_years}
    present_students_detail = {year: {section: [] for section in all_sections} for year in all_years}

    students = Student.query.filter_by(department=department).all()
    for student in students:
        year = student.year
        section = student.section
        # Check if there is no LateAttendance record for the student on the selected date
        late_record = LateAttendance.query.filter_by(student_id=student.id, date=selected_date).first()

        if not late_record:  # If no late record exists, the student is considered present
            attendance_summary[year][section] += 1
            present_students_detail[year][section].append({
                'roll_no': student.roll_no,
                'name': student.name
            })

    return render_template(
        'calendar_view.html',
        hod_name=hod.name,
        department=department,
        attendance_summary=attendance_summary,
        present_students_detail=present_students_detail,
        selected_date=selected_date
    )


@app.route('/get_late_students/<int:year>/<string:section>', methods=['GET'])
@login_required
def get_late_students(year, section):
    if session.get('user_type') != 'HOD':
        return redirect(url_for('index'))

    hod = current_user
    department = hod.department

    # Fetch students of the specified year, section, and department
    students = Student.query.filter_by(department=department, year=year, section=section).all()
    late_students = [
        {'roll_no': student.roll_no, 'name': student.name}
        for student in students if student.month_late_count > 0
    ]

    return jsonify(late_students)

# Principal Registration and Dashboard
@app.route('/principal_register', methods=['GET', 'POST'])
def principal_register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        new_principal = Principal(name=name, password=password)
        db.session.add(new_principal)
        db.session.commit()
        flash('Principal registered successfully', 'success')
        return redirect(url_for('index'))
    return render_template('principal_register.html', title="Principal Register")



@app.route('/principal_dashboard', methods=['GET', 'POST'])
@login_required
def principal_dashboard():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    # Handling date navigation
    selected_date = request.form.get('selected_date')
    if selected_date:
        selected_date = date.fromisoformat(selected_date)
    else:
        selected_date = date.today()

    # Fetch late attendance for the selected date
    late_attendance = (
        db.session.query(Student, LateAttendance)
        .join(LateAttendance, and_(Student.id == LateAttendance.student_id, LateAttendance.date == selected_date))
        .all()
    )

    # Organize attendance summary by department and year
    departments = db.session.query(Student.department).distinct().all()
    department_summary = {}
    for department, in departments:
        department_summary[department] = {'count': 0, 'yearly_counts': {year: 0 for year in range(1, 5)}}

    for student, _ in late_attendance:
        department_summary[student.department]['count'] += 1
        department_summary[student.department]['yearly_counts'][student.year] += 1

    # Button to clear all student data
    if request.method == 'POST' and 'clear_data' in request.form:
        Student.query.delete()
        db.session.commit()
        flash('All student data has been cleared successfully.', 'success')
        return redirect(url_for('principal_dashboard'))

    return render_template(
        'principal_dashboard.html',
        department_summary=department_summary,
        selected_date=selected_date,
        title="Principal Dashboard"
    )
@app.route('/view_students')
@login_required
def view_students():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))
    
    students = Student.query.all()  # Fetch all students
    return render_template('view_students.html', students=students, title="All Students")

@app.route('/view_roles')
@login_required
def view_roles():
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))
    
    faculty = Faculty.query.all()  # Fetch all faculty details
    discipline_incharge = DisciplineIncharge.query.all()  # Fetch discipline in charge details
    hods = HOD.query.all()  # Fetch HOD details
    
    return render_template(
        'view_roles.html',
        faculty=faculty,
        discipline_incharge=discipline_incharge,
        hods=hods,
        title="Registered Roles"
    )
# Routes to delete a specific Faculty, Discipline Incharge, or HOD
@app.route('/delete_faculty/<int:id>', methods=['POST'])
@login_required
def delete_faculty(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    faculty = Faculty.query.get(id)
    if faculty:
        db.session.delete(faculty)
        db.session.commit()
        flash('Faculty member deleted successfully.', 'success')
    else:
        flash('Faculty member not found.', 'danger')
    return redirect(url_for('view_roles'))

@app.route('/delete_discipline_incharge/<int:id>', methods=['POST'])
@login_required
def delete_discipline_incharge(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    incharge = DisciplineIncharge.query.get(id)
    if incharge:
        db.session.delete(incharge)
        db.session.commit()
        flash('Discipline Incharge deleted successfully.', 'success')
    else:
        flash('Discipline Incharge not found.', 'danger')
    return redirect(url_for('view_roles'))

@app.route('/delete_hod/<int:id>', methods=['POST'])
@login_required
def delete_hod(id):
    if session.get('user_type') != 'Principal':
        return redirect(url_for('index'))

    hod = HOD.query.get(id)
    if hod:
        db.session.delete(hod)
        db.session.commit()
        flash('HOD deleted successfully.', 'success')
    else:
        flash('HOD not found.', 'danger')
    return redirect(url_for('view_roles'))

# Load students from CSV
@app.route('/load_students', methods=['GET', 'POST'])
def load_students():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            file_path = os.path.join('uploads', file.filename)
            file.save(file_path)
            load_students_from_csv(file_path)
            flash('Students loaded successfully from CSV', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid file type. Please upload a CSV file.', 'danger')
    return render_template('load_students.html', title="Load Students")
# Notification functions
def send_email_notification(parent_email, student_name):
    sender_email = "your_email@example.com"
    sender_password = "your_email_password"
    subject = "Late Attendance Alert"
    body = f"Your child, {student_name}, has been marked late."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = parent_email

    try:
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_sms_notification(parent_mobile, student_name):
    # Add your SMS API logic here
    print(f"Sending SMS to {parent_mobile}: {student_name} has been marked late.")

if __name__ == '__main__':
    app.run(debug=True)
