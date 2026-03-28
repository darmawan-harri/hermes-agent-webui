import json
import os
import secrets
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import config

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

JOBS_FILE = os.path.join(config.ROOT_HERMES_FOLDER, "cron/jobs.json")
SKILLS_FOLDER = os.path.join(config.ROOT_HERMES_FOLDER, "skills")
SCRIPTS_FOLDER = config.SCRIPTS_FOLDER
MEMORIES_FOLDER = config.MEMORIES_FOLDER
IMAGE_CACHE_FOLDER = config.IMAGE_CACHE_FOLDER
BROWSER_SCREENSHOTS_FOLDER = config.BROWSER_SCREENSHOTS_FOLDER
SESSIONS_FOLDER = config.SESSIONS_FOLDER

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def load_jobs():
    with open(JOBS_FILE, "r") as f:
        return json.load(f)

def get_file_list(path, base_path):
    items = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            rel_path = os.path.relpath(item_path, base_path)
            is_dir = os.path.isdir(item_path)
            if is_dir:
                items.append({
                    'name': item,
                    'path': rel_path,
                    'is_dir': is_dir,
                    'size': '-',
                    'date': '-'
                })
            else:
                stat = os.stat(item_path)
                size = stat.st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                import datetime
                date_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                items.append({
                    'name': item,
                    'path': rel_path,
                    'is_dir': is_dir,
                    'size': size_str,
                    'date': date_str
                })
    except:
        pass
    return items

def read_file_content(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    pretty_types = ['.json', '.jsonl', '.py', '.yaml', '.yml', '.md']
    
    try:
        if ext in pretty_types:
            if ext == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return json.dumps(data, indent=2), 'code'
            elif ext == '.jsonl':
                lines = []
                with open(file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                lines.append(json.loads(line))
                            except:
                                lines.append(line)
                return json.dumps(lines, indent=2), 'code'
            elif ext in ['.yaml', '.yml']:
                import yaml
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                return yaml.dump(data, default_flow_style=False), 'code'
            elif ext == '.md':
                import markdown
                with open(file_path, 'r') as f:
                    content = f.read()
                html = markdown.markdown(content, extensions=['tables', 'fenced_code'])
                return html, 'markdown'
            elif ext == '.py':
                with open(file_path, 'r') as f:
                    return f.read(), 'code'
        else:
            with open(file_path, 'r') as f:
                return f.read(), 'text'
    except Exception as e:
        return str(e), 'error'
    return '', 'text'

STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; font-size: 16px; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; flex-shrink: 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; transition: 0.2s; font-size: 15px; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.menu-logout { margin-top: auto; border-top: 1px solid #334155; padding-top: 10px; }
.main { flex: 1; padding: 24px; overflow: auto; }
.container { max-width: 1000px; }
h1 { color: #f1f5f9; margin-bottom: 20px; font-size: 28px; }
.updated { color: #64748b; font-size: 15px; margin-bottom: 20px; }
.job { background: #1e293b; border-radius: 8px; padding: 24px; margin-bottom: 16px; border: 1px solid #334155; }
.job-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.job-name { font-size: 22px; font-weight: 600; color: #f1f5f9; }
.job-id { font-size: 13px; color: #64748b; font-family: monospace; }
.status { padding: 6px 14px; border-radius: 12px; font-size: 13px; font-weight: 500; }
.status-scheduled { background: #1e3a5f; color: #60a5fa; }
.status-running { background: #451a03; color: #fb923c; }
.status-completed { background: #14532d; color: #4ade80; }
.status-failed { background: #450a0a; color: #f87171; }
.enabled-true { color: #4ade80; margin-left: 10px; }
.enabled-false { color: #f87171; margin-left: 10px; }
.field { margin-bottom: 10px; }
.field-label { font-weight: 500; color: #94a3b8; font-size: 14px; }
.field-value { color: #e2e8f0; font-size: 15px; }
.prompt { background: #0f172a; padding: 14px; border-radius: 4px; font-size: 15px; white-space: pre-wrap; margin-top: 10px; border: 1px solid #334155; }
.origin { display: inline-block; background: #334155; padding: 4px 10px; border-radius: 4px; font-size: 13px; margin-right: 8px; }
.schedule { background: #14532d; padding: 6px 10px; border-radius: 4px; font-family: monospace; font-size: 14px; color: #4ade80; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
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
.file-explorer { background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 20px; border: 1px solid #334155; }
.breadcrumb { color: #64748b; margin-bottom: 16px; font-size: 14px; }
.breadcrumb a { color: #60a5fa; text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.file-list { list-style: none; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.file-item { padding: 10px 12px; border-radius: 4px; }
.file-item:hover { background: #334155; }
.file-item a { color: #e2e8f0; text-decoration: none; display: block; }
.file-item.folder a { color: #fb923c; }
.file-item.file a { color: #e2e8f0; }
.file-viewer { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
.file-viewer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #334155; }
.file-viewer-title { font-size: 18px; font-weight: 600; color: #f1f5f9; }
.file-viewer-meta { color: #64748b; font-size: 13px; }
.file-content { background: #0f172a; padding: 16px; border-radius: 4px; overflow-x: auto; }
.file-content pre { margin: 0; white-space: pre-wrap; word-wrap: break-word; font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; line-height: 1.6; color: #e2e8f0; }
.code-keyword { color: #c792ea; }
.code-string { color: #c3e88d; }
.code-number { color: #f78c6c; }
.code-comment { color: #546e7a; }
.code-tag { color: #f07178; }
.code-attr { color: #ffcb6b; }
.view-toggle { background: #334155; color: #e2e8f0; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; margin-left: 12px; }
.view-toggle:hover { background: #475569; }
.view-toggle.active { background: #3b82f6; }
.table-view { overflow-x: auto; }
.table-view table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table-view th, .table-view td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }
.table-view th { background: #334155; color: #f1f5f9; font-weight: 600; }
.table-view td { color: #e2e8f0; }
.table-view tr:hover { background: #1e293b; }
.table-view .json-key { color: #ffcb6b; }
.table-view .json-string { color: #c3e88d; }
.table-view .json-number { color: #f78c6c; }
.table-view .json-boolean { color: #c792ea; }
.table-view .json-null { color: #546e7a; }
.json-grid { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; font-family: 'Consolas', 'Monaco', monospace; border: 1px solid #334155; border-radius: 8px; overflow: hidden; margin: 10px 0; }
.json-grid th { background: #1e3a5f; color: #60a5fa; font-weight: 600; padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; white-space: nowrap; }
.json-grid td { padding: 10px 16px; border-bottom: 1px solid #1e293b; color: #e2e8f0; background: #0f172a; vertical-align: top; }
.json-grid tr:last-child td { border-bottom: none; }
.json-grid tr:hover td { background: #1e293b; }
.json-grid .json-key { color: #ffcb6b; font-weight: 500; }
.json-grid .json-index { color: #64748b; font-weight: 500; min-width: 40px; }
.json-grid .json-string { color: #c3e88d; }
.json-grid .json-number { color: #f78c6c; }
.json-grid .json-boolean { color: #c792ea; }
.json-grid .json-null { color: #546e7a; font-style: italic; }
.json-grid .json-object, .json-grid .json-array { color: #60a5fa; }
.json-empty { color: #64748b; font-style: italic; padding: 20px; text-align: center; }
.json-toggle { cursor: pointer; color: #60a5fa; font-size: 12px; margin-right: 4px; user-select: none; }
.json-toggle.expanded { transform: rotate(90deg); }
.json-object, .json-array { color: #60a5fa; cursor: pointer; }
.json-collapsed { border-left: 2px solid #334155; padding-left: 8px; }
.markdown-content { line-height: 1.7; color: #e2e8f0; }
.markdown-content h1 { color: #f1f5f9; font-size: 2em; margin: 0.67em 0; border-bottom: 1px solid #334155; padding-bottom: 0.3em; }
.markdown-content h2 { color: #f1f5f9; font-size: 1.5em; margin: 0.83em 0; border-bottom: 1px solid #334155; padding-bottom: 0.3em; }
.markdown-content h3 { color: #f1f5f9; font-size: 1.17em; margin: 1em 0; }
.markdown-content p { margin: 1em 0; }
.markdown-content ul, .markdown-content ol { margin: 1em 0; padding-left: 2em; }
.markdown-content li { margin: 0.5em 0; }
.markdown-content code { background: #334155; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; font-size: 0.9em; }
.markdown-content pre { background: #0f172a; padding: 16px; border-radius: 6px; overflow-x: auto; margin: 1em 0; }
.markdown-content pre code { background: none; padding: 0; }
.markdown-content blockquote { border-left: 4px solid #3b82f6; margin: 1em 0; padding-left: 1em; color: #94a3b8; }
.markdown-content table { width: 100%; border-collapse: collapse; margin: 1em 0; }
.markdown-content th, .markdown-content td { border: 1px solid #334155; padding: 8px 12px; text-align: left; }
.markdown-content th { background: #1e293b; }
.markdown-content a { color: #60a5fa; text-decoration: none; }
.markdown-content a:hover { text-decoration: underline; }
.markdown-content hr { border: none; border-top: 1px solid #334155; margin: 1em 0; }
"""

def highlight_syntax(content, ext):
    if ext not in ['.py', '.json', '.yaml', '.yml', '.md']:
        return content
    
    import re
    from html import escape
    
    content = escape(content)
    
    try:
        if ext in ['.py']:
            content = re.sub(r'(&#39;#.*)$', r'<span class="code-comment">\1</span>', content, flags=re.MULTILINE)
            content = re.sub(r'\b(def|class|if|elif|else|for|while|return|import|from|as|try|except|finally|with|lambda|yield|pass|break|continue|and|or|not|in|is|True|False|None|self|print)\b', r'<span class="code-keyword">\1</span>', content)
            content = re.sub(r'(&quot;&quot;&quot;[\s\S]*?&quot;&quot;&quot;)', r'<span class="code-string">\1</span>', content)
            content = re.sub(r"(&#39;&#39;&#39;[\s\S]*?&#39;&#39;&#39;)", r'<span class="code-string">\1</span>', content)
            content = re.sub(r'(&quot;[^&quot;]*&quot;)', r'<span class="code-string">\1</span>', content)
            content = re.sub(r'(&#39;[^&#39;]*&#39;)', r'<span class="code-string">\1</span>', content)
            content = re.sub(r'\b(\d+)\b', r'<span class="code-number">\1</span>', content)
        
        elif ext == '.json':
            content = re.sub(r'(&quot;[\w-]*&quot;:)', r'<span class="code-attr">\1</span>', content)
            content = re.sub(r': (&quot;[^&quot;]*&quot;)', r': <span class="code-string">\1</span>', content)
            content = re.sub(r': (\d+)', r': <span class="code-number">\1</span>', content)
        
        elif ext in ['.yaml', '.yml']:
            content = re.sub(r'^(\s*[\w-]+):', r'<span class="code-keyword">\1</span>:', content, flags=re.MULTILINE)
            content = re.sub(r'(#.*)$', r'<span class="code-comment">\1</span>', content, flags=re.MULTILINE)
            content = re.sub(r'(&quot;[\w-]*&quot;:)', r'<span class="code-attr">\1</span>', content)
    except:
        pass
    
    return content

SIDEBAR = """
<div class="sidebar">
    <div class="sidebar-logo"><h2>Hermes</h2></div>
    <a href="/" class="menu-item {{ 'active' if active_page == 'jobs' else '' }}">Cron Jobs</a>
    <a href="{{ url_for('skills') }}" class="menu-item {{ 'active' if active_page == 'skills' else '' }}">List Skill</a>
    <a href="{{ url_for('scripts') }}" class="menu-item {{ 'active' if active_page == 'scripts' else '' }}">Scripts</a>
    <a href="{{ url_for('memories') }}" class="menu-item {{ 'active' if active_page == 'memories' else '' }}">Memories</a>
    <a href="{{ url_for('image_cache') }}" class="menu-item {{ 'active' if active_page == 'image_cache' else '' }}">Image Cache</a>
    <a href="{{ url_for('browser_screenshots') }}" class="menu-item {{ 'active' if active_page == 'browser_screenshots' else '' }}">Browser Screenshots</a>
    <a href="{{ url_for('sessions') }}" class="menu-item {{ 'active' if active_page == 'sessions' else '' }}">Sessions</a>
    <a href="{{ url_for('soul') }}" class="menu-item {{ 'active' if active_page == 'soul' else '' }}">SOUL.md</a>
    <a href="{{ url_for('state_db') }}" class="menu-item {{ 'active' if active_page == 'state_db' else '' }}">state.db</a>
    <a href="{{ url_for('settings') }}" class="menu-item {{ 'active' if active_page == 'settings' else '' }}">config.yaml</a>
    <a href="{{ url_for('change_password') }}" class="menu-item">Change Password</a>
    <a href="{{ url_for('logout') }}" class="menu-item menu-logout">Logout</a>
</div>
"""

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes - Cron Jobs</title>
<style>""" + STYLE + """</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <div class="container">
        <h1>Hermes Cron Jobs</h1>
        <p class="updated">Last updated: {{ updated_at }}</p>
        {% for job in jobs %}
        <div class="job">
            <div class="job-header">
                <div>
                    <div class="job-name">{{ job.name }}</div>
                    <div class="job-id">{{ job.id }}</div>
                </div>
                <div>
                    <span class="status status-{{ job.state }}">{{ job.state }}</span>
                    <span class="enabled-{{ job.enabled }}">{{ 'Enabled' if job.enabled else 'Disabled' }}</span>
                </div>
            </div>
            <div class="grid">
                <div class="field"><div class="field-label">Schedule</div><div class="schedule">{{ job.schedule_display }}</div></div>
                <div class="field"><div class="field-label">Next Run</div><div class="field-value">{{ job.next_run_at or 'N/A' }}</div></div>
                <div class="field"><div class="field-label">Last Run</div><div class="field-value">{{ job.last_run_at or 'Never' }}</div></div>
                <div class="field"><div class="field-label">Skill</div><div class="field-value">{{ job.skill }}</div></div>
            </div>
            {% if job.prompt %}
            <div class="field" style="margin-top:12px;"><div class="field-label">Prompt</div><div class="prompt">{{ job.prompt }}</div></div>
            {% endif %}
            <div class="field" style="margin-top:12px;"><div class="field-label">Origin</div><div><span class="origin">{{ job.origin.platform }}</span> {{ job.origin.chat_name }} ({{ job.origin.chat_id }})</div></div>
            {% if job.last_status or job.last_error %}
            <div class="grid" style="margin-top:12px;">
                {% if job.last_status %}<div class="field"><div class="field-label">Last Status</div><div class="field-value">{{ job.last_status }}</div></div>{% endif %}
                {% if job.last_error %}<div class="field"><div class="field-label">Last Error</div><div class="field-value" style="color:#f87171;">{{ job.last_error }}</div></div>{% endif %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</div>
</body>
</html>
"""

SKILLS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes - Skills</title>
<style>""" + STYLE + """</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>{{ 'Scripts' if active_page == 'scripts' else ('Memories' if active_page == 'memories' else ('Image Cache' if active_page == 'image_cache' else ('Browser Screenshots' if active_page == 'browser_screenshots' else ('Sessions' if active_page == 'sessions' else 'Skills')))) }} Explorer</h1>
    <div class="file-explorer">
        <div class="breadcrumb">
            <a href="{{ url_for('sessions') if active_page == 'sessions' else url_for('browser_screenshots') if active_page == 'browser_screenshots' else url_for('image_cache') if active_page == 'image_cache' else url_for('memories') if active_page == 'memories' else url_for('scripts') if active_page == 'scripts' else url_for('skills') }}">{{ 'sessions' if active_page == 'sessions' else 'browser_screenshots' if active_page == 'browser_screenshots' else 'image_cache' if active_page == 'image_cache' else 'memories' if active_page == 'memories' else ('scripts' if active_page == 'scripts' else 'skills') }}</a>
            {% if current_path %}/{% for p in current_path.split('/') %}<a href="{{ url_for('sessions', path=current_path.split('/')[:loop.index]|join('/')) if active_page == 'sessions' else url_for('browser_screenshots', path=current_path.split('/')[:loop.index]|join('/')) if active_page == 'browser_screenshots' else url_for('image_cache', path=current_path.split('/')[:loop.index]|join('/')) if active_page == 'image_cache' else url_for('memories', path=current_path.split('/')[:loop.index]|join('/')) if active_page == 'memories' else url_for('scripts', path=current_path.split('/')[:loop.index]|join('/')) if active_page == 'scripts' else url_for('skills', path=current_path.split('/')[:loop.index]|join('/')) }}">{{ p }}</a>{% if not loop.last %}/{% endif %}{% endfor %}{% endif %}
        </div>
        <ul class="file-list">
            {% if parent_path %}
            <li class="file-item folder"><a href="{{ url_for('sessions', path=parent_path) if active_page == 'sessions' else url_for('browser_screenshots', path=parent_path) if active_page == 'browser_screenshots' else url_for('image_cache', path=parent_path) if active_page == 'image_cache' else url_for('memories', path=parent_path) if active_page == 'memories' else url_for('scripts', path=parent_path) if active_page == 'scripts' else url_for('skills', path=parent_path) }}">..</a></li>
            {% endif %}
            {% for item in items %}
            <li class="file-item {{ 'folder' if item.is_dir else 'file' }}">
                <a href="{{ url_for('sessions', path=item.path) if active_page == 'sessions' else url_for('browser_screenshots', path=item.path) if active_page == 'browser_screenshots' else url_for('image_cache', path=item.path) if active_page == 'image_cache' else url_for('memories', path=item.path) if active_page == 'memories' else url_for('scripts', path=item.path) if active_page == 'scripts' else url_for('skills', path=item.path) if item.is_dir else url_for('view_file', path=item.path) }}">{{ item.name }}{% if item.is_dir %}/{% endif %}</a>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% if file_content %}
    <div class="file-viewer">
        <div class="file-viewer-header">
            <div class="file-viewer-title">{{ file_name }}</div>
            <div>
                <span class="file-viewer-meta">{{ file_type }}</span>
                {% if is_json %}
                <button class="view-toggle" onclick="toggleView()">View as Table</button>
                {% endif %}
            </div>
        </div>
        <div id="code-view" class="file-content{% if is_markdown %} markdown-content{% endif %}">
            {% if is_markdown %}
            {{ file_content|safe }}
            {% else %}
            <pre>{{ file_content|safe }}</pre>
            {% endif %}
        </div>
        {% if is_json and json_table %}
        <div id="table-view" class="file-content table-view" style="display:none;">{{ json_table|safe }}</div>
        {% endif %}
    </div>
    {% endif %}
    <script>
    function toggleView() {
        var codeView = document.getElementById('code-view');
        var tableView = document.getElementById('table-view');
        var btn = document.querySelector('.view-toggle');
        if (codeView.style.display === 'none') {
            codeView.style.display = 'block';
            tableView.style.display = 'none';
            btn.textContent = 'View as Table';
            btn.classList.remove('active');
        } else {
            codeView.style.display = 'none';
            tableView.style.display = 'block';
            btn.textContent = 'View as Code';
            btn.classList.add('active');
        }
    }
    function toggleJson(id) {
        var el = document.getElementById(id);
        var toggle = el.previousElementSibling.previousElementSibling;
        if (el.style.display === 'none') {
            el.style.display = 'block';
            if (toggle && toggle.classList.contains('json-toggle')) {
                toggle.textContent = '▼';
            }
        } else {
            el.style.display = 'none';
            if (toggle && toggle.classList.contains('json-toggle')) {
                toggle.textContent = '▶';
            }
        }
    }
    </script>
</div>
</body>
</html>
"""

IMAGE_VIEWER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Image Viewer</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; font-size: 16px; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; flex-shrink: 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; transition: 0.2s; font-size: 15px; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.menu-logout { margin-top: auto; border-top: 1px solid #334155; padding-top: 10px; }
.main { flex: 1; padding: 24px; overflow: auto; }
.file-list { list-style: none; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.file-item { padding: 10px 12px; border-radius: 4px; }
.file-item:hover { background: #334155; }
.file-item a { color: #e2e8f0; text-decoration: none; display: block; }
.breadcrumb { color: #64748b; margin-bottom: 16px; font-size: 14px; }
.breadcrumb a { color: #60a5fa; text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.image-container { background: #1e293b; border-radius: 8px; padding: 20px; text-align: center; }
.image-container img { max-width: 100%; max-height: 80vh; border-radius: 4px; }
.image-name { margin-top: 16px; color: #94a3b8; font-size: 14px; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>Image Cache Explorer</h1>
    <div class="breadcrumb">
        <a href="{{ url_for('image_cache') }}">image_cache</a>
    </div>
    <div class="image-container">
        <img src="{{ url_for('serve_image', path=image_path) }}" alt="{{ image_path }}">
        <div class="image-name">{{ image_path }}</div>
    </div>
</div>
</body>
</html>
"""

IMAGE_TABLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Image Explorer</title>
<style>
""" + STYLE + """
.image-table { width: 100%; border-collapse: collapse; }
.image-table th, .image-table td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
.image-table th { background: #1e293b; color: #f1f5f9; font-weight: 600; }
.image-table tr:hover { background: #1e293b; }
.image-table td a { color: #e2e8f0; text-decoration: none; }
.image-table td a:hover { color: #60a5fa; }
.image-thumb { width: 60px; height: 60px; object-fit: cover; border-radius: 4px; }
.pagination { margin-top: 20px; display: flex; gap: 8px; justify-content: center; }
.pagination a { padding: 8px 12px; background: #334155; color: #e2e8f0; text-decoration: none; border-radius: 4px; }
.pagination a:hover { background: #3b82f6; }
.pagination span { padding: 8px 12px; background: #3b82f6; color: white; border-radius: 4px; }
.modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); }
.modal-content { margin: auto; display: block; max-width: 90%; max-height: 90vh; margin-top: 2%; }
.modal-close { position: absolute; top: 20px; right: 35px; color: #f1f1f1; font-size: 40px; font-weight: bold; cursor: pointer; }
.modal-close:hover { color: #3b82f6; }
.modal-info { position: absolute; bottom: 20px; left: 20px; color: #f1f1f1; font-size: 16px; }
.modal-img { cursor: pointer; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>{{ 'Image Cache' if active_page == 'image_cache' else 'Browser Screenshots' }} Explorer</h1>
    <div class="breadcrumb">
        <a href="{{ url_for('image_cache') if active_page == 'image_cache' else url_for('browser_screenshots') }}">{{ 'image_cache' if active_page == 'image_cache' else 'browser_screenshots' }}</a>
    </div>
    <table class="image-table">
        <thead>
            <tr>
                <th>Preview</th>
                <th>Name</th>
                <th>Size</th>
                <th>Date</th>
            </tr>
        </thead>
        <tbody>
        {% for item in items %}
        <tr>
            <td>
                {% if not item.is_dir and item.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')) %}
                <img src="{{ url_for('serve_image', path=item.path) }}" class="image-thumb modal-img" onclick="openModal('{{ url_for('serve_image', path=item.path) }}', '{{ item.name }}', '{{ item.size }}', '{{ item.date }}')" alt="{{ item.name }}">
                {% else %}-{% endif %}
            </td>
            <td>
                {% if item.is_dir %}
                <a href="{{ url_for('image_cache', path=item.path) if active_page == 'image_cache' else url_for('browser_screenshots', path=item.path) }}">{{ item.name }}/</a>
                {% else %}
                <a href="#" onclick="openModal('{{ url_for('serve_image', path=item.path) }}', '{{ item.name }}', '{{ item.size }}', '{{ item.date }}'); return false;">{{ item.name }}</a>
                {% endif %}
            </td>
            <td>{{ item.size }}</td>
            <td>{{ item.date }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
<div id="imageModal" class="modal" onclick="closeModal()">
    <span class="modal-close" onclick="closeModal()">&times;</span>
    <img class="modal-content" id="modalImg">
    <div class="modal-info" id="modalInfo"></div>
</div>
<script>
var modal = document.getElementById('imageModal');
var modalImg = document.getElementById('modalImg');
var modalInfo = document.getElementById('modalInfo');
function openModal(src, name, size, date) {
    modal.style.display = 'block';
    modalImg.src = src;
    modalInfo.innerHTML = name + ' | ' + size + ' | ' + date;
}
function closeModal() {
    modal.style.display = 'none';
}
</script>
</body>
</html>
"""

SESSION_TABLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sessions Explorer</title>
<style>
""" + STYLE + """
.image-table { width: 100%; border-collapse: collapse; }
.image-table th, .image-table td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
.image-table th { background: #1e293b; color: #f1f5f9; font-weight: 600; }
.image-table tr:hover { background: #1e293b; }
.image-table td a { color: #e2e8f0; text-decoration: none; }
.image-table td a:hover { color: #60a5fa; }
.modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); }
.modal-content { margin: auto; display: block; max-width: 90%; max-height: 90vh; margin-top: 2%; }
.modal-close { position: absolute; top: 20px; right: 35px; color: #f1f1f1; font-size: 40px; font-weight: bold; cursor: pointer; }
.modal-close:hover { color: #3b82f6; }
.modal-info { position: absolute; bottom: 20px; left: 20px; color: #f1f1f1; font-size: 16px; }
.modal-body { position: absolute; top: 60px; left: 20px; right: 20px; bottom: 80px; overflow: auto; background: #1e293b; border-radius: 8px; padding: 20px; }
.modal-body pre { margin: 0; white-space: pre-wrap; color: #e2e8f0; font-size: 14px; }
.view-btn, .delete-btn { padding: 6px 12px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; margin-right: 4px; }
.view-btn { background: #3b82f6; color: white; }
.delete-btn { background: #dc2626; color: white; }
.delete-btn:hover { background: #b91c1c; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>Sessions Explorer</h1>
    <div class="breadcrumb">
        <a href="{{ url_for('sessions') }}">sessions</a>
    </div>
    <table class="image-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Date</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
        {% for item in items %}
        <tr>
            <td><a href="{{ url_for('view_file', path=item.path) }}">{{ item.name }}</a></td>
            <td>{{ item.size }}</td>
            <td>{{ item.date }}</td>
            <td>
                <a href="{{ url_for('view_file', path=item.path) }}" class="view-btn" style="text-decoration:none;">View</a>
                <button class="delete-btn" onclick="deleteFile('{{ item.path }}', '{{ item.name }}')">Delete</button>
            </td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% if total_pages > 1 %}
    <div class="pagination">
        {% if page > 1 %}
        <a href="{{ url_for('sessions', path=current_path, page=page-1) }}">Previous</a>
        {% endif %}
        <span>Page {{ page }} of {{ total_pages }} ({{ total }} items)</span>
        {% if page < total_pages %}
        <a href="{{ url_for('sessions', path=current_path, page=page+1) }}">Next</a>
        {% endif %}
    </div>
    {% endif %}
</div>
<div id="fileModal" class="modal" onclick="if(event.target === this) closeModal()">
    <span class="modal-close" onclick="closeModal()">&times;</span>
    <div class="modal-info" id="modalInfo"></div>
    <div class="modal-body" id="modalBody"></div>
    <div style="position:absolute;bottom:20px;right:20px;">
        <button class="view-btn" onclick="toggleViewMode()">Toggle View</button>
    </div>
</div>
<script>
var modal = document.getElementById('fileModal');
var modalBody = document.getElementById('modalBody');
var modalInfo = document.getElementById('modalInfo');
var currentFile = '';
var jsonData = null;
var viewMode = 'code';

function viewFile(path, name, size, date) {
    currentFile = path;
    modalInfo.innerHTML = name + ' | ' + size + ' | ' + date;
    modal.style.display = 'block';
    viewMode = 'code';
    
    fetch('/view_json/' + path)
        .then(r => r.text())
        .then(data => {
            jsonData = data;
            modalBody.innerHTML = '<pre>' + data.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre>';
        })
        .catch(e => {
            modalBody.innerHTML = '<pre>Error loading file</pre>';
        });
}

function toggleViewMode() {
    if (viewMode === 'code') {
        viewMode = 'table';
        modalBody.innerHTML = '<div class="table-view">' + convertToTable(jsonData) + '</div>';
    } else {
        viewMode = 'code';
        modalBody.innerHTML = '<pre>' + jsonData.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre>';
    }
}

function convertToTable(jsonStr) {
    try {
        var data = JSON.parse(jsonStr);
        return jsonToHTMLTable(data);
    } catch(e) {
        return '<pre>' + jsonStr + '</pre>';
    }
}

function jsonToHTMLTable(data) {
    if (Array.isArray(data)) {
        if (data.length === 0) return 'Empty array';
        var html = '<table><thead><tr>';
        var keys = Object.keys(data[0]);
        keys.forEach(function(k) { html += '<th>' + k + '</th>'; });
        html += '</tr></thead><tbody>';
        data.forEach(function(row) {
            html += '<tr>';
            keys.forEach(function(k) {
                var val = row[k];
                if (typeof val === 'object') val = JSON.stringify(val);
                html += '<td>' + val + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        return html;
    } else if (typeof data === 'object') {
        var html = '<table>';
        for (var k in data) {
            var val = data[k];
            if (typeof val === 'object') val = JSON.stringify(val);
            html += '<tr><td style="color:#ffcb6b;font-weight:bold;">' + k + '</td><td>' + val + '</td></tr>';
        }
        html += '</table>';
        return html;
    }
    return '<pre>' + jsonStr + '</pre>';
}

function deleteFile(path, name) {
    if (confirm('Delete ' + name + '?')) {
        fetch('/delete_file/' + path, { method: 'POST' })
            .then(r => r.json())
            .then(d => {
                if (d.success) location.reload();
                else alert(d.error);
            });
    }
}

function closeModal() {
    modal.style.display = 'none';
}
</script>
</body>
</html>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login - Hermes</title>
<style>""" + STYLE + """</style>
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

def json_to_table(data, prefix="", expanded=False):
    from html import escape
    
    def get_type(v):
        if isinstance(v, bool): return 'boolean'
        if isinstance(v, int) or isinstance(v, float): return 'number'
        if v is None: return 'null'
        if isinstance(v, str): return 'string'
        if isinstance(v, dict): return 'object'
        if isinstance(v, list): return 'array'
        return 'string'
    
    def format_value(v, depth=0):
        t = get_type(v)
        if t == 'object':
            count = len(v) if isinstance(v, dict) else 0
            uid = f"obj_{secrets.token_hex(8)}"
            content = json_to_table(v, prefix, expanded)
            return f"<span class='json-toggle' onclick=\"toggleJson('{uid}')\">▶</span> <span class='json-object'>Object [{count} keys]</span><div id='{uid}' class='json-collapsed' style='display:{"none" if not expanded else "block"};margin-left:20px;margin-top:8px;'>{content}</div>"
        elif t == 'array':
            count = len(v) if isinstance(v, list) else 0
            uid = f"arr_{secrets.token_hex(8)}"
            content = json_to_table(v, prefix, expanded)
            return f"<span class='json-toggle' onclick=\"toggleJson('{uid}')\">▶</span> <span class='json-array'>Array [{count} items]</span><div id='{uid}' class='json-collapsed' style='display:{"none" if not expanded else "block"};margin-left:20px;margin-top:8px;'>{content}</div>"
        elif t == 'string':
            return f"<span class='json-string'>\"{escape(str(v))}\"</span>"
        elif t == 'number':
            return f"<span class='json-number'>{v}</span>"
        elif t == 'boolean':
            return f"<span class='json-boolean'>{str(v).lower()}</span>"
        elif t == 'null':
            return f"<span class='json-null'>null</span>"
        return escape(str(v))
    
    if isinstance(data, dict):
        rows = []
        for k, v in data.items():
            t = get_type(v)
            if t in ['object', 'array']:
                rows.append(f"<tr><td class='json-key'>{escape(str(k))}</td><td>{format_value(v)}</td></tr>")
            else:
                rows.append(f"<tr><td class='json-key'>{escape(str(k))}</td><td>{format_value(v)}</td></tr>")
        return "<table class='json-grid'><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    elif isinstance(data, list):
        if len(data) == 0:
            return "<div class='json-empty'>Empty array</div>"
        first = data[0]
        if isinstance(first, dict):
            keys = list(first.keys())
            header = "<tr><th>#</th>" + "".join(f"<th>{escape(str(k))}</th>" for k in keys) + "</tr>"
            rows = []
            for i, item in enumerate(data):
                row = f"<tr><td class='json-index'>{i}</td>"
                for k in keys:
                    v = item.get(k)
                    t = get_type(v)
                    if t in ['object', 'array']:
                        row += f"<td>{format_value(v, i)}</td>"
                    else:
                        row += f"<td>{format_value(v)}</td>"
                row += "</tr>"
                rows.append(row)
            return "<table class='json-grid'><thead>" + header + "</thead><tbody>" + "".join(rows) + "</tbody></table>"
        else:
            rows = []
            for i, item in enumerate(data):
                rows.append(f"<tr><td class='json-index'>{i}</td><td>{format_value(item)}</td></tr>")
            return "<table class='json-grid'><thead><tr><th>#</th><th>Value</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    return escape(str(data))

@app.route("/")
@login_required
def index():
    data = load_jobs()
    return render_template_string(INDEX_HTML, jobs=data.get("jobs", []), updated_at=data.get("updated_at", "Unknown"), active_page='jobs')

def explorer(path, folder, active):
    full_path = os.path.join(folder, path)
    
    if not os.path.exists(full_path):
        return "Path not found", 404
    
    if os.path.isfile(full_path):
        return file_viewer(path, folder, active)
    
    items = get_file_list(full_path, folder)
    parent_path = '/'.join(path.split('/')[:-1]) if path else ""
    
    return render_template_string(
        SKILLS_HTML,
        items=items,
        current_path=path,
        parent_path=parent_path,
        file_content=None,
        active_page=active
    )

def file_viewer(path, folder, active):
    full_path = os.path.join(folder, path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return "File not found", 404
    
    content, file_type = read_file_content(full_path)
    ext = os.path.splitext(full_path)[1].lower()
    
    is_json = ext in ['.json', '.jsonl']
    is_markdown = ext == '.md'
    json_table = ""
    if is_json:
        try:
            if ext == '.json':
                with open(full_path, 'r') as f:
                    json_data = json.load(f)
            else:  # .jsonl
                json_data = []
                with open(full_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                json_data.append(json.loads(line))
                            except:
                                pass
            json_table = json_to_table(json_data)
        except Exception as e:
            is_json = False
    
    if file_type == 'code' and not is_json:
        content = highlight_syntax(content, ext)
    
    items = []
    current_path = os.path.dirname(path)
    parent_path = '/'.join(current_path.split('/')[:-1]) if current_path else ""
    
    if current_path:
        items = get_file_list(os.path.join(folder, current_path), folder)
    
    return render_template_string(
        SKILLS_HTML,
        items=items,
        current_path=current_path,
        parent_path=parent_path,
        file_content=content,
        file_name=os.path.basename(path),
        file_type=file_type,
        is_json=is_json,
        is_markdown=is_markdown,
        json_table=json_table,
        active_page=active
    )

@app.route("/skills")
@app.route("/skills/<path:path>")
@login_required
def skills(path=""):
    return explorer(path, SKILLS_FOLDER, 'skills')

@app.route("/scripts")
@app.route("/scripts/<path:path>")
@login_required
def scripts(path=""):
    return explorer(path, SCRIPTS_FOLDER, 'scripts')

@app.route("/memories")
@app.route("/memories/<path:path>")
@login_required
def memories(path=""):
    return explorer(path, MEMORIES_FOLDER, 'memories')

@app.route("/image_cache")
@app.route("/image_cache/<path:path>")
@login_required
def image_cache(path=""):
    if path:
        full_path = os.path.join(IMAGE_CACHE_FOLDER, path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            ext = os.path.splitext(full_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                return render_template_string(IMAGE_VIEWER_HTML, 
                    image_path=path, 
                    active_page='image_cache')
    
    items = get_file_list(os.path.join(IMAGE_CACHE_FOLDER, path), IMAGE_CACHE_FOLDER)
    parent_path = '/'.join(path.split('/')[:-1]) if path else ""
    return render_template_string(
        IMAGE_TABLE_HTML,
        items=items,
        current_path=path,
        parent_path=parent_path,
        active_page='image_cache'
    )

@app.route("/serve_image/<path:path>")
@login_required
def serve_image(path):
    # Try image_cache first
    full_path = os.path.join(IMAGE_CACHE_FOLDER, path)
    if not os.path.exists(full_path):
        # Try browser_screenshots
        full_path = os.path.join(BROWSER_SCREENSHOTS_FOLDER, path)
    if not os.path.exists(full_path):
        return "File not found", 404
    
    ext = os.path.splitext(full_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml'
    }
    mime = mime_types.get(ext, 'application/octet-stream')
    
    from flask import send_file
    return send_file(full_path, mimetype=mime)

@app.route("/browser_screenshots")
@app.route("/browser_screenshots/<path:path>")
@login_required
def browser_screenshots(path=""):
    if path:
        full_path = os.path.join(BROWSER_SCREENSHOTS_FOLDER, path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            ext = os.path.splitext(full_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                return render_template_string(IMAGE_VIEWER_HTML, 
                    image_path=path, 
                    active_page='browser_screenshots')
    
    items = get_file_list(os.path.join(BROWSER_SCREENSHOTS_FOLDER, path), BROWSER_SCREENSHOTS_FOLDER)
    parent_path = '/'.join(path.split('/')[:-1]) if path else ""
    return render_template_string(
        IMAGE_TABLE_HTML,
        items=items,
        current_path=path,
        parent_path=parent_path,
        active_page='browser_screenshots'
    )

@app.route("/sessions")
@app.route("/sessions/<path:path>")
@login_required
def sessions(path=""):
    page = int(request.args.get('page', 1))
    per_page = 20
    
    all_items = get_file_list(os.path.join(SESSIONS_FOLDER, path), SESSIONS_FOLDER)
    total = len(all_items)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    items = all_items[start:end]
    
    parent_path = '/'.join(path.split('/')[:-1]) if path else ""
    return render_template_string(
        SESSION_TABLE_HTML,
        items=items,
        current_path=path,
        parent_path=parent_path,
        active_page='sessions',
        page=page,
        total_pages=total_pages,
        total=total
    )

@app.route("/view_json/<path:path>")
@login_required
def view_json(path):
    full_path = os.path.join(SESSIONS_FOLDER, path)
    if not os.path.exists(full_path):
        return "File not found", 404
    
    content, file_type = read_file_content(full_path)
    return content

@app.route("/delete_file/<path:path>", methods=["POST"])
@login_required
def delete_file(path):
    full_path = os.path.join(SESSIONS_FOLDER, path)
    if not os.path.exists(full_path):
        return '{"error": "File not found"}', 404
    
    try:
        os.remove(full_path)
        return '{"success": true}'
    except Exception as e:
        return '{"error": "' + str(e) + '"}', 500

@app.route("/view/<path:path>")
@login_required
def view_file(path):
    # Try browser_screenshots folder first
    full_path = os.path.join(BROWSER_SCREENSHOTS_FOLDER, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        ext = os.path.splitext(full_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
            return render_template_string(IMAGE_VIEWER_HTML, image_path=path, active_page='browser_screenshots')
    
    # Try scripts folder
    full_path = os.path.join(SCRIPTS_FOLDER, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return file_viewer(path, SCRIPTS_FOLDER, 'scripts')
    
    # Try memories folder
    full_path = os.path.join(MEMORIES_FOLDER, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return file_viewer(path, MEMORIES_FOLDER, 'memories')
    
    # Try sessions folder
    full_path = os.path.join(SESSIONS_FOLDER, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return file_viewer(path, SESSIONS_FOLDER, 'sessions')
    
    # Try skills folder
    full_path = os.path.join(SKILLS_FOLDER, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return file_viewer(path, SKILLS_FOLDER, 'skills')
    
    return "File not found", 404

CONFIG_YAML_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "config.yaml")

@app.route("/settings")
@login_required
def settings():
    if not os.path.exists(CONFIG_YAML_PATH):
        return "Config file not found", 404
    
    import yaml
    with open(CONFIG_YAML_PATH, 'r') as f:
        content = yaml.safe_load(f)
    
    yaml_content = yaml.dump(content, default_flow_style=False, sort_keys=False)
    
    import re
    from html import escape
    
    def highlight_yaml(content):
        content = escape(content)
        content = re.sub(r'^(\s*[\w-]+):', r'<span class="yaml-key">\1</span>:', content, flags=re.MULTILINE)
        content = re.sub(r'(#.*)$', r'<span class="yaml-comment">\1</span>', content, flags=re.MULTILINE)
        content = re.sub(r': (&quot;[^&quot;]*&quot;)', r': <span class="yaml-string">\1</span>', content)
        content = re.sub(r": ('[^']*')", r": <span class='yaml-string'>\1</span>", content)
        content = re.sub(r': (\d+)', r': <span class="yaml-number">\1</span>', content)
        content = re.sub(r': (true|false)', r': <span class="yaml-boolean">\1</span>', content)
        content = re.sub(r': (null|~)', r': <span class="yaml-null">\1</span>', content)
        return content
    
    yaml_highlighted = highlight_yaml(yaml_content)
    
    return render_template_string(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>config.yaml - Hermes</title>
<style>
""" + STYLE + """
.config-viewer { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; overflow-x: auto; }
.config-viewer pre { margin: 0; font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; line-height: 1.6; color: #e2e8f0; }
.yaml-key { color: #ffcb6b; font-weight: 500; }
.yaml-string { color: #c3e88d; }
.yaml-number { color: #f78c6c; }
.yaml-boolean { color: #c792ea; }
.yaml-null { color: #546e7a; font-style: italic; }
.yaml-comment { color: #546e7a; font-style: italic; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>config.yaml</h1>
    <div style="margin-bottom: 16px;"><a href="""" + url_for('change_password') + """" style="color: #60a5fa; text-decoration: none; font-size: 14px;">🔐 Change Password</a></div>
    <div class="config-viewer">
        <pre>""" + yaml_highlighted + """</pre>
    </div>
</div>
</body>
</html>
""",
        active_page='settings'
    )

SOUL_MD_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "SOUL.md")

@app.route("/soul")
@login_required
def soul():
    if not os.path.exists(SOUL_MD_PATH):
        return "SOUL.md not found", 404
    
    import markdown
    with open(SOUL_MD_PATH, 'r') as f:
        content = f.read()
    
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'toc'])
    
    return render_template_string(
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOUL.md - Hermes</title>
<style>
""" + STYLE + """
.markdown-body { background: #1e293b; border-radius: 8px; padding: 32px; border: 1px solid #334155; max-width: 900px; }
.markdown-body h1 { color: #f1f5f9; font-size: 2em; margin: 0 0 24px 0; border-bottom: 2px solid #3b82f6; padding-bottom: 12px; }
.markdown-body h2 { color: #f1f5f9; font-size: 1.5em; margin: 32px 0 16px 0; border-bottom: 1px solid #334155; padding-bottom: 8px; }
.markdown-body h3 { color: #f1f5f9; font-size: 1.25em; margin: 24px 0 12px 0; }
.markdown-body p { margin: 16px 0; line-height: 1.7; color: #e2e8f0; }
.markdown-body ul, .markdown-body ol { margin: 16px 0; padding-left: 28px; }
.markdown-body li { margin: 8px 0; color: #e2e8f0; }
.markdown-body code { background: #0f172a; padding: 3px 8px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 0.9em; color: #fb923c; }
.markdown-body pre { background: #0f172a; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 16px 0; }
.markdown-body pre code { background: none; padding: 0; color: #e2e8f0; }
.markdown-body blockquote { border-left: 4px solid #3b82f6; margin: 16px 0; padding: 8px 20px; background: #0f172a; border-radius: 0 8px 8px 0; }
.markdown-body blockquote p { color: #94a3b8; margin: 0; }
.markdown-body a { color: #60a5fa; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body hr { border: none; border-top: 1px solid #334155; margin: 24px 0; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 16px 0; }
.markdown-body th, .markdown-body td { border: 1px solid #334155; padding: 10px 14px; text-align: left; }
.markdown-body th { background: #0f172a; color: #60a5fa; }
.markdown-body td { color: #e2e8f0; }
.markdown-body tr:hover { background: #0f172a; }
.comment { color: #64748b; font-style: italic; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>SOUL.md</h1>
    <div class="markdown-body">
        """ + html + """
    </div>
</div>
</body>
</html>
""",
        active_page='soul'
    )

STATE_DB_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "state.db")

def get_db_connection():
    import sqlite3
    conn = sqlite3.connect(STATE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/state_db")
@app.route("/state_db/<table_name>")
@login_required
def state_db(table_name=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    if not table_name:
        table_html = ""
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            table_html += f"<tr><td><a href='{url_for('state_db', table_name=t)}'>{t}</a></td><td>{count}</td></tr>"
        
        conn.close()
        return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>state.db - Hermes</title>
<style>
""" + STYLE + """
.db-header { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
.db-header h2 { color: #f1f5f9; margin: 0 0 8px 0; font-size: 20px; }
.db-header a { color: #60a5fa; text-decoration: none; font-size: 14px; }
.db-header a:hover { text-decoration: underline; }
.db-table { width: 100%; border-collapse: collapse; }
.db-table th, .db-table td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
.db-table th { background: #1e3a5f; color: #60a5fa; font-weight: 600; }
.db-table td { color: #e2e8f0; }
.db-table td a { color: #60a5fa; text-decoration: none; }
.db-table td a:hover { text-decoration: underline; }
.db-table tr:hover { background: #1e293b; }
.db-info { color: #64748b; font-size: 13px; margin-top: 16px; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>state.db</h1>
    <div class="db-header">
        <h2>Tables</h2>
        <a href=""" + url_for('state_db') + """>↑ Back to database</a>
    </div>
    <table class="db-table">
        <thead><tr><th>Table</th><th>Rows</th></tr></thead>
        <tbody>
""" + table_html + """
        </tbody>
    </table>
</div>
</body>
</html>
""", active_page='state_db')
    
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 100")
    rows = cursor.fetchall()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    
    conn.close()
    
    rows_html = ""
    for row in rows:
        rows_html += "<tr>"
        for col in columns:
            val = row[col]
            if val is None:
                val_str = "<span style='color:#546e7a;'>NULL</span>"
            elif isinstance(val, str) and len(val) > 100:
                val_str = val[:100] + "..."
            else:
                val_str = str(val)
            rows_html += f"<td>{val_str}</td>"
        rows_html += "</tr>"
    
    cols_html = "".join(f"<th>{c}</th>" for c in columns)
    
    return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>""" + table_name + """ - Hermes</title>
<style>
""" + STYLE + """
.db-header { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
.db-header h2 { color: #f1f5f9; margin: 0 0 8px 0; font-size: 20px; }
.db-header a { color: #60a5fa; text-decoration: none; font-size: 14px; }
.db-header a:hover { text-decoration: underline; }
.db-table { width: 100%; border-collapse: collapse; }
.db-table th, .db-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 13px; }
.db-table th { background: #1e3a5f; color: #60a5fa; font-weight: 600; white-space: nowrap; }
.db-table td { color: #e2e8f0; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.db-table tr:hover { background: #1e293b; }
.db-table tr:hover td { white-space: normal; }
.pagination { margin-top: 20px; color: #64748b; font-size: 14px; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>""" + table_name + """</h1>
    <div class="db-header">
        <h2>""" + table_name + """</h2>
        <a href=""" + url_for('state_db') + """>↑ Back to tables</a>
    </div>
    <table class="db-table">
        <thead><tr>""" + cols_html + """</tr></thead>
        <tbody>
""" + rows_html + """
        </tbody>
    </table>
    <div class="pagination">Showing first 100 rows</div>
</div>
</body>
</html>
""", active_page='state_db')

@app.route("/login", methods=["GET", "POST"])
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

@app.route("/change_password", methods=["GET", "POST"])
@login_required
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
    
    return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Change Password - Hermes</title>
<style>
""" + STYLE + """
.change-password-box { background: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; max-width: 400px; margin: 40px auto; }
.change-password-box h2 { text-align: center; margin-bottom: 30px; font-size: 24px; color: #f1f5f9; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #94a3b8; }
.form-group input { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.form-group input:focus { outline: none; border-color: #3b82f6; }
.btn { width: 100%; padding: 12px; border-radius: 6px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.btn:hover { background: #2563eb; }
.btn-secondary { background: #334155; margin-top: 10px; }
.btn-secondary:hover { background: #475569; }
.flash { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
.flash-error { background: #450a0a; color: #f87171; }
.flash-success { background: #14532d; color: #4ade80; }
</style>
</head>
<body>
""" + SIDEBAR + """
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
            <a href="""" + url_for('index') + """" class="btn btn-secondary" style="display:block;text-align:center;text-decoration:none;padding:12px;border-radius:6px;background:#334155;color:white;margin-top:10px;">Cancel</a>
        </form>
    </div>
</div>
</body>
</html>
""", active_page='')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/setup", methods=["GET", "POST"])
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1", port=5000)
