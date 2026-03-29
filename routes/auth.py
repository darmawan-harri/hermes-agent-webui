import secrets
from flask import Blueprint, render_template_string, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db

auth_bp = Blueprint('auth', __name__)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - Hermes</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; }
.login-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.login-box { background: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; width: 360px; }
.login-box h2 { text-align: center; margin-bottom: 30px; font-size: 24px; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #94a3b8; }
.form-group input { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.form-group input:focus { outline: none; border-color: #3b82f6; }
.btn { width: 100%; padding: 12px; border-radius: 6px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.btn:hover { background: #2563eb; }
.flash { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
.flash-error { background: #450a0a; color: #f87171; }
.flash-success { background: #14532d; color: #4ade80; }
</style>
</head>
<body>
<div class="login-page">
    <div class="login-box">
        <h2>Hermes Login</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}<div class="flash flash-{{ category }}">{{ message }}</div>{% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit" class="btn">Login</button>
        </form>
    </div>
</div>
</body>
</html>
"""

CHANGE_PASSWORD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Change Password - Hermes</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.main { flex: 1; padding: 24px; }
.change-password-box { background: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; max-width: 400px; margin: 40px auto; }
.change-password-box h2 { text-align: center; margin-bottom: 30px; font-size: 24px; color: #f1f5f9; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #94a3b8; }
.form-group input { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.btn { width: 100%; padding: 12px; border-radius: 6px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.btn:hover { background: #2563eb; }
.btn-secondary { background: #334155; margin-top: 10px; }
.flash { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
.flash-error { background: #450a0a; color: #f87171; }
.flash-success { background: #14532d; color: #4ade80; }
</style>
</head>
<body>
""" + """
<div class="main">
    <div class="change-password-box">
        <h2>Change Password</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}<div class="flash flash-{{ category }}">{{ message }}</div>{% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group"><label>Current Password</label><input type="password" name="current_password" required></div>
            <div class="form-group"><label>New Password</label><input type="password" name="new_password" required></div>
            <div class="form-group"><label>Confirm New Password</label><input type="password" name="confirm_password" required></div>
            <button type="submit" class="btn">Change Password</button>
            <a href="/" class="btn btn-secondary" style="display:block;text-align:center;text-decoration:none;padding:12px;border-radius:6px;background:#334155;color:white;margin-top:10px;">Cancel</a>
        </form>
    </div>
</div>
</body>
</html>
"""

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username")).first()
        if user and check_password_hash(user.password, request.form.get("password", "")):
            login_user(user)
            return redirect(url_for("index"))
        flash("Invalid username or password", "error")
    return render_template_string(LOGIN_HTML)

@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))

@auth_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        user = User.query.get(current_user.id)
        
        if not check_password_hash(user.password, current_password):
            flash("Current password is incorrect", "error")
        elif len(new_password) < 1:
            flash("New password cannot be empty", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match", "error")
        else:
            user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
            db.session.commit()
            flash("Password changed successfully!", "success")
            return redirect(url_for("index"))
    
    return render_template_string(CHANGE_PASSWORD_HTML)

@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.first():
        return redirect(url_for("login"))
    if request.method == "POST":
        hashed = generate_password_hash(request.form.get("password", ""), method="pbkdf2:sha256")
        db.session.add(User(username=request.form.get("username"), password=hashed))
        db.session.commit()
        flash("User created successfully!", "success")
        return redirect(url_for("login"))
    return """<!DOCTYPE html><html><head><title>Setup</title><style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;min-height:100vh}.box{background:#1e293b;padding:40px;border-radius:12px;width:360px}h2{text-align:center;margin-bottom:30px}.form-group{margin-bottom:20px}.form-group label{display:block;margin-bottom:8px;color:#94a3b8}.form-group input{width:100%;padding:12px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0}.btn{width:100%;padding:12px;border-radius:6px;border:none;background:#3b82f6;color:white;cursor:pointer}</style></head><body><div class="box"><h2>Create Admin User</h2><form method="POST"><div class="form-group"><label>Username</label><input type="text" name="username" required></div><div class="form-group"><label>Password</label><input type="password" name="password" required></div><button type="submit" class="btn">Create User</button></form></div></body></html>"""
