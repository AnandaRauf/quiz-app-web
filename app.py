from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pony.orm import Database, Required, db_session, select, delete
from flask import send_file
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database setup
db = Database()
db.bind(provider='mysql', host='localhost', user='root', passwd='', db='quiz_app')


class User(db.Entity, UserMixin):
    username = Required(str, unique=True)
    password = Required(str)
    role = Required(str, default="User")  # Role can be 'User' or 'Admin'


class Question(db.Entity):
    category = Required(str)
    text = Required(str)
    option_a = Required(str)
    option_b = Required(str)


# Mapping with option to create tables
db.generate_mapping(create_tables=True)


@login_manager.user_loader
@db_session
def load_user(user_id):
    return User.get(id=int(user_id))


@app.route('/')
@db_session
def home():
    categories = []
    if current_user.is_authenticated and current_user.role == 'User':
        # Fetch unique categories from the Question table for users
        categories = select(q.category for q in Question).distinct()[:]
    return render_template('home.html', categories=categories)


@app.route('/register', methods=['GET', 'POST'])
@db_session
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form.get('role', 'User')  # Default to User if no role is selected

        # Add new user with the selected role
        User(username=username, password=password, role=role)
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@db_session
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.get(username=username)

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('home'))

        flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
@db_session
def admin_dashboard():
    if current_user.role != 'Admin':
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('home'))

    # Handle form submission for adding a question
    if request.method == 'POST':
        category = request.form['category']
        text = request.form['text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']

        # Add question to the database
        Question(category=category, text=text, option_a=option_a, option_b=option_b)
        flash('Quiz has been successfully added!', 'success')

    # Fetch unique categories and questions to display
    categories = select(q.category for q in Question).distinct()[:]
    questions = select(q for q in Question)[:]
    users = select(u for u in User)[:]  # Fetch all users to allow role management
    return render_template('admin_dashboard.html', questions=questions, categories=categories, users=users)

@app.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
@db_session
def delete_question(question_id):
    if current_user.role != 'Admin':
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('home'))

    question = Question.get(id=question_id)
    if question:
        question.delete()
        flash('Question deleted successfully!', 'success')
    else:
        flash('Question not found.', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/change_role/<int:user_id>', methods=['POST'])
@login_required
@db_session
def change_role(user_id):
    if current_user.role != 'Admin':
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('home'))

    user = User.get(id=user_id)
    if user:
        # Toggle user role between 'User' and 'Admin'
        user.role = 'User' if user.role == 'Admin' else 'Admin'
        flash(f"Role for {user.username} changed to {user.role} successfully!", 'success')
    else:
        flash("User not found.", 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/quiz/<category>', methods=['GET', 'POST'])
@db_session
def quiz(category):
    # Retrieve questions for the specified category
    questions = select(q for q in Question if q.category == category)[:]

    if request.method == 'POST':
        # Collect user's answers
        answers = request.form.getlist('answer')
        score_a = answers.count('A')
        score_b = answers.count('B')

        # Determine the result based on the majority answers for known categories
        if category == 'Narsistic vs Empathy':
            result = 'ANDA EMPATI' if score_a > score_b else 'ANDA NARSISTIC'
        elif category == 'Introvert vs Ekstrovert':
            result = 'ANDA EKSTROVERT' if score_a > score_b else 'ANDA INTROVERT'
        elif category == 'Thinker vs Feeler':
            result = 'ANDA FEELER' if score_a > score_b else 'ANDA THINKER'
        else:
            # If the category is unknown, provide a more general message
            result = 'Hasil tidak tersedia untuk kategori yang dipilih.'

        # Render the result template with the calculated result
        return render_template('result.html', result=result)

    # Render the quiz template with the questions
    return render_template('quiz.html', questions=questions)


@app.route('/download_result', methods=['POST'])
def download_result():
    result_text = request.form['result']
    file_content = f"Your quiz result: {result_text}\nThank you for taking the quiz!"
    return send_file(
        io.BytesIO(file_content.encode()),
        mimetype="text/plain",
        as_attachment=True,
        download_name="quiz_result.txt"
    )


if __name__ == '__main__':
    app.run(debug=True)
