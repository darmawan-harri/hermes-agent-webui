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
    <a href="{{ url_for('chat') }}" class="menu-item {{ 'active' if active_page == 'chat' else '' }}">Chat</a>
    <a href="{{ url_for('chat_settings') }}" class="menu-item">Chat Settings</a>
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

CHAT_DB_PATH = "/opt/hermes_webui/chat.db"

def get_chat_db_connection():
    import sqlite3
    conn = sqlite3.connect(CHAT_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    
    # Create tables if not exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        )
    """)
    conn.commit()
    return conn

def get_db_connection():
    import sqlite3
    conn = sqlite3.connect(STATE_DB_PATH, timeout=10)
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

HERMES_API_URL = config.HERMES_API_URL if hasattr(config, 'HERMES_API_URL') else "http://127.0.0.1:8642/v1/chat/completions"
HERMES_API_TIMEOUT = config.HERMES_API_TIMEOUT if hasattr(config, 'HERMES_API_TIMEOUT') else 600
HERMES_STREAMING = config.HERMES_STREAMING if hasattr(config, 'HERMES_STREAMING') else True

@app.route("/chat/settings", methods=["GET", "POST"])
@login_required
def chat_settings():
    config_path = "/opt/hermes_webui/chat_config.json"
    
    if request.method == "POST":
        import json
        data = {
            "api_url": request.form.get("api_url", ""),
            "timeout": int(request.form.get("timeout", 600)),
            "streaming": request.form.get("streaming") == "on"
        }
        with open(config_path, "w") as f:
            json.dump(data, f)
        flash("Settings saved!", "success")
    
    import json
    defaults = {"api_url": "http://127.0.0.1:8642/v1/chat/completions", "timeout": 600, "streaming": True}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            settings = {**defaults, **json.load(f)}
    else:
        settings = defaults
    
    return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat Settings - Hermes</title>
<style>
""" + STYLE + """
.settings-box { background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; max-width: 600px; margin: 20px auto; }
.settings-box h2 { color: #f1f5f9; margin-bottom: 24px; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #94a3b8; font-weight: 500; }
.form-group input { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.form-group input:focus { outline: none; border-color: #3b82f6; }
.form-group .hint { font-size: 12px; color: #64748b; margin-top: 4px; }
.checkbox-group { display: flex; align-items: center; gap: 10px; }
.checkbox-group input { width: auto; }
.checkbox-group label { margin: 0; }
.btn { padding: 12px 24px; border-radius: 6px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.btn:hover { background: #2563eb; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>Chat Settings</h1>
    <div class="settings-box">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}<div class="flash flash-{{ category }}">{{ message }}</div>{% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group">
                <label>API URL</label>
                <input type="text" name="api_url" value=""" + settings['api_url'] + """ required>
                <div class="hint">OpenAI-compatible API endpoint</div>
            </div>
            <div class="form-group">
                <label>Timeout (seconds)</label>
                <input type="number" name="timeout" value=""" + str(settings['timeout']) + """ min="60" max="3600">
                <div class="hint">Max wait time for response (60-3600 seconds)</div>
            </div>
            <div class="form-group checkbox-group">
                <input type="checkbox" name="streaming" """ + ("checked" if settings['streaming'] else "") + """ id="streaming">
                <label for="streaming">Enable Streaming</label>
                <div class="hint" style="margin-left: auto;">Show response as it generates</div>
            </div>
            <button type="submit" class="btn">Save Settings</button>
        </form>
    </div>
</div>
</body>
</html>
""", active_page='')

@app.route("/chat")
@app.route("/chat/<session_id>")
@login_required
def chat(session_id=None):
    import requests
    
    if not session_id:
        conn = get_chat_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, COALESCE(title, id) as name FROM chat_sessions ORDER BY created_at DESC LIMIT 10")
        sessions = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        conn.close()
        
        return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat - Hermes</title>
<style>
""" + STYLE + """
.chat-container { display: flex; height: calc(100vh - 120px); gap: 20px; }
.chat-sidebar { width: 250px; background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; overflow-y: auto; }
.chat-sidebar h3 { color: #f1f5f9; font-size: 16px; margin-bottom: 16px; }
.session-item { padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; }
.session-item:hover { background: #334155; }
.session-item a { color: #e2e8f0; text-decoration: none; display: block; }
.chat-main { flex: 1; background: #1e293b; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.message { margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; max-width: 80%; }
.message.user { background: #3b82f6; margin-left: auto; border-bottom-right-radius: 4px; }
.message.assistant { background: #334155; border-bottom-left-radius: 4px; }
.message .role { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.message .content { color: #e2e8f0; line-height: 1.5; white-space: pre-wrap; }
.chat-input { padding: 16px; border-top: 1px solid #334155; display: flex; gap: 12px; }
.chat-input input { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.chat-input input:focus { outline: none; border-color: #3b82f6; }
.chat-input button { padding: 12px 24px; border-radius: 8px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.chat-input button:hover { background: #2563eb; }
.chat-input button:disabled { background: #475569; cursor: not-allowed; }
.new-chat-btn { display: block; width: 100%; padding: 12px; border-radius: 6px; border: 1px dashed #334155; background: none; color: #60a5fa; cursor: pointer; margin-bottom: 16px; text-align: center; }
.new-chat-btn:hover { background: #334155; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: #64748b; }
.chat-input { padding: 16px; border-top: 1px solid #334155; display: flex; gap: 12px; align-items: flex-end; }
.chat-input .input-wrapper { flex: 1; }
.chat-input textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; font-family: inherit; resize: none; min-height: 48px; max-height: 200px; line-height: 1.5; }
.chat-input textarea:focus { outline: none; border-color: #3b82f6; }
.chat-input button { padding: 12px 24px; border-radius: 8px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.chat-input button:hover { background: #2563eb; }
.chat-input button:disabled { background: #475569; cursor: not-allowed; }
.new-chat-btn { display: block; width: 100%; padding: 12px; border-radius: 6px; border: 1px dashed #334155; background: none; color: #60a5fa; cursor: pointer; margin-bottom: 16px; text-align: center; }
.new-chat-btn:hover { background: #334155; }
.thinking { color: #64748b; font-style: italic; }
.markdown-body { line-height: 1.5; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>Chat</h1>
    <div class="chat-container">
        <div class="chat-sidebar">
            <button class="new-chat-btn" onclick="newChat()">+ New Chat</button>
            <h3>Sessions</h3>
            {% for s in sessions %}
            <div class="session-item">
                <a href="{{ url_for('chat', session_id=s.id) }}">{{ s.name[:20] }}</a>
            </div>
            {% endfor %}
        </div>
        <div class="chat-main">
            <div class="empty-state">Select a session or start new chat</div>
        </div>
    </div>
</div>
<script>
function newChat() {
    fetch('/chat/new', { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            if (d.session_id) window.location.href = '/chat/' + d.session_id;
        });
}
</script>
</body>
</html>
""", sessions=sessions, active_page='chat')
    
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    from html import escape
    cursor.execute("SELECT COALESCE(title, id) FROM chat_sessions WHERE id = ?", (session_id,))
    session_name = cursor.fetchone()
    session_name = escape(session_name[0]) if session_name else "New Session"
    
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? AND content IS NOT NULL ORDER BY timestamp", (session_id,))
    messages = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    conn.close()
    
    return render_template_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat - Hermes</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
""" + STYLE + """
.chat-container { display: flex; height: calc(100vh - 120px); gap: 20px; }
.chat-sidebar { width: 250px; background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; overflow-y: auto; }
.chat-sidebar h3 { color: #f1f5f9; font-size: 16px; margin-bottom: 16px; }
.session-item { padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; }
.session-item:hover { background: #334155; }
.session-item a { color: #e2e8f0; text-decoration: none; display: block; }
.chat-main { flex: 1; background: #1e293b; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column; }
.chat-header { padding: 16px; border-bottom: 1px solid #334155; }
.chat-header h2 { color: #f1f5f9; font-size: 18px; margin: 0; }
.chat-header input:focus { outline: 1px solid #3b82f6; padding: 4px 8px; border-radius: 4px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.message { margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; max-width: 80%; }
.message.user { background: #3b82f6; margin-left: auto; border-bottom-right-radius: 4px; }
.message.assistant { background: #334155; border-bottom-left-radius: 4px; }
.message .role { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.message .content { color: #e2e8f0; line-height: 1.5; white-space: pre-wrap; }
.chat-input { padding: 16px; border-top: 1px solid #334155; display: flex; gap: 12px; align-items: flex-end; }
.chat-input .input-wrapper { flex: 1; }
.chat-input textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; font-family: inherit; resize: none; min-height: 48px; max-height: 200px; line-height: 1.5; }
.chat-input textarea:focus { outline: none; border-color: #3b82f6; }
.chat-input button { padding: 12px 24px; border-radius: 8px; border: none; background: #3b82f6; color: white; font-size: 15px; cursor: pointer; }
.chat-input button:hover { background: #2563eb; }
.chat-input button:disabled { background: #475569; cursor: not-allowed; }
.new-chat-btn { display: block; width: 100%; padding: 12px; border-radius: 6px; border: 1px dashed #334155; background: none; color: #60a5fa; cursor: pointer; margin-bottom: 16px; text-align: center; }
.new-chat-btn:hover { background: #334155; }
.thinking { color: #64748b; font-style: italic; }
.markdown-body { line-height: 1.5; }
.markdown-body h1, .markdown-body h2, .markdown-body h3 { color: #f1f5f9; margin: 12px 0 6px 0; }
.markdown-body h1 { font-size: 1.4em; border-bottom: 1px solid #334155; padding-bottom: 6px; }
.markdown-body h2 { font-size: 1.2em; }
.markdown-body h3 { font-size: 1.1em; }
.markdown-body p { margin: 6px 0; }
.markdown-body ul, .markdown-body ol { margin: 6px 0; padding-left: 20px; }
.markdown-body li { margin: 2px 0; }
.markdown-body code { background: #0f172a; padding: 2px 5px; border-radius: 3px; font-family: monospace; font-size: 0.9em; color: #fb923c; }
.markdown-body pre { background: #0f172a; padding: 10px; border-radius: 6px; overflow-x: auto; margin: 8px 0; position: relative; }
.markdown-body pre code { background: none; padding: 0; color: #e2e8f0; }
.markdown-body pre .copy-btn { position: absolute; top: 6px; right: 6px; background: #334155; border: none; color: #94a3b8; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; }
.markdown-body pre .copy-btn:hover { background: #3b82f6; color: white; }
.markdown-body blockquote { border-left: 3px solid #3b82f6; padding-left: 10px; color: #94a3b8; margin: 6px 0; }
.markdown-body table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; }
.markdown-body th, .markdown-body td { border: 1px solid #475569; padding: 6px 10px; text-align: left; }
.markdown-body th { background: #1e3a5f; color: #60a5fa; font-weight: 600; }
.markdown-body td { background: #0f172a; }
.markdown-body tr:hover td { background: #1e293b; }
.markdown-body a { color: #60a5fa; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body strong { color: #f1f5f9; }
.markdown-body em { color: #94a3b8; }
.markdown-body hr { border: none; border-top: 1px solid #334155; margin: 12px 0; }
.markdown-body img { max-width: 100%; border-radius: 6px; margin: 8px 0; }
.file-preview { display: flex; align-items: center; gap: 8px; background: #334155; padding: 8px 12px; border-radius: 6px; margin-top: 8px; font-size: 13px; color: #e2e8f0; }
.remove-file-btn { background: none; border: none; color: #f87171; cursor: pointer; font-size: 18px; padding: 0 4px; }
.remove-file-btn:hover { color: #ef4444; }
.attach-btn { background: #334155; border: none; color: #e2e8f0; padding: 12px 16px; border-radius: 8px; cursor: pointer; font-size: 18px; }
.attach-btn:hover { background: #475569; }
.chat-input { display: flex; gap: 8px; align-items: flex-end; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>Chat</h1>
    <div class="chat-container">
        <div class="chat-sidebar">
            <button class="new-chat-btn" onclick="newChat()">+ New Chat</button>
            <h3>Sessions</h3>
            <div class="session-item"><a href="{{ url_for('chat') }}">← Back</a></div>
        </div>
        <div class="chat-main">
            <div class="chat-header">
                <div style="display:flex;align-items:center;gap:12px;flex:1;">
                    <input type="text" id="chatTitle" value="{{ session_name[:30]|safe }}" 
                        style="background:none;border:none;color:#f1f5f9;font-size:18px;font-weight:600;flex:1;"
                        onchange='renameChat({{ session_id|tojson }}, this.value)'>
                    <button onclick='deleteChat({{ session_id|tojson }})' 
                        style="background:#dc2626;border:none;color:white;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:13px;">
                        Delete
                    </button>
                </div>
            </div>
            <div class="chat-messages" id="messages">
                {% for msg in messages %}
                <div class="message {{ msg.role }}">
                    <div class="role">{{ msg.role }}</div>
                    <div class="content{% if msg.role == 'assistant' %} markdown-body markdown-render{% endif %}">{{ msg.content }}</div>
                </div>
                {% endfor %}
            </div>
            <div class="chat-input">
                <div class="input-wrapper">
                    <textarea id="userInput" placeholder="Type your message... (Shift+Enter for new line)" autocomplete="off"></textarea>
                    <div id="filePreview" class="file-preview" style="display:none;">
                        <span id="fileName"></span>
                        <button onclick="removeFile()" class="remove-file-btn">×</button>
                    </div>
                </div>
                <input type="file" id="fileInput" style="display:none;" onchange="handleFileSelect(event)">
                <button class="attach-btn" onclick="document.getElementById('fileInput').click()" title="Attach file">📎</button>
                <button id="sendBtn" onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
</div>
<script>
var sessionId = {{ session_id|tojson }};
var messages = {{ messages|tojson }};

document.getElementById('userInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
document.getElementById('userInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

function scrollToBottom() {
    var msgs = document.getElementById('messages');
    msgs.scrollTop = msgs.scrollHeight;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMessage(role, content) {
    var container = document.getElementById('messages');
    var div = document.createElement('div');
    div.className = 'message ' + role;
    
    if (role === 'assistant' && typeof marked !== 'undefined') {
        var rendered = marked.parse(content);
        div.innerHTML = '<div class="role">' + role + '</div><div class="content markdown-body markdown-render">' + rendered + '</div>';
        container.appendChild(div);
        addCopyButtons(div);
    } else {
        div.innerHTML = '<div class="role">' + role + '</div><div class="content">' + escapeHtml(content) + '</div>';
        container.appendChild(div);
    }
    scrollToBottom();
}

function addCopyButtons(container) {
    container.querySelectorAll('pre').forEach(function(pre) {
        if (pre.querySelector('.copy-btn')) return;
        var code = pre.querySelector('code');
        var text = code ? code.textContent : pre.textContent;
        var btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.onclick = function() {
            navigator.clipboard.writeText(text);
            btn.textContent = 'Copied!';
            setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
        };
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
}

var attachedFile = null;
var attachedFileContent = null;

function handleFileSelect(event) {
    var file = event.target.files[0];
    if (file) {
        attachedFile = file;
        var reader = new FileReader();
        reader.onload = function(e) {
            attachedFileContent = e.target.result;
            document.getElementById('filePreview').style.display = 'flex';
            document.getElementById('fileName').textContent = file.name + ' (' + formatFileSize(file.size) + ')';
        };
        reader.readAsText(file);
    }
}

function removeFile() {
    attachedFile = null;
    attachedFileContent = null;
    document.getElementById('filePreview').style.display = 'none';
    document.getElementById('fileInput').value = '';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function sendMessage() {
    var input = document.getElementById('userInput');
    var btn = document.getElementById('sendBtn');
    var message = input.value.trim();
    
    if (!message && !attachedFile) return;
    if (btn.disabled) return;
    
    btn.disabled = true;
    input.disabled = true;
    
    var displayMessage = message;
    var fullMessage = message;
    
    if (attachedFile) {
        var fileExt = attachedFile.name.split('.').pop();
        displayMessage = (message ? message + String.fromCharCode(10, 10) : '') + '📎 ' + attachedFile.name;
        fullMessage = (message ? message + String.fromCharCode(10, 10) : '') + '[Attached file: ' + attachedFile.name + String.fromCharCode(10, 10) + '```' + fileExt + String.fromCharCode(10) + attachedFileContent + String.fromCharCode(10) + '```]';
        removeFile();
    }
    
    input.value = '';
    renderMessage('user', displayMessage);
    
    var thinking = document.createElement('div');
    thinking.className = 'message assistant';
    thinking.id = 'thinking';
    thinking.innerHTML = '<div class="role">assistant</div><div class="content thinking">Thinking...</div>';
    var messagesDiv = document.getElementById('messages');
    messagesDiv.appendChild(thinking);
    scrollToBottom();
    
    try {
        var response = await fetch('/chat/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId, message: fullMessage})
        });
        
        var contentType = response.headers.get('content-type') || '';
        if (contentType.indexOf('event-stream') >= 0) {
            var thinkingEl = document.getElementById('thinking');
            if (thinkingEl) thinkingEl.remove();
            
            var assistantDiv = document.createElement('div');
            assistantDiv.className = 'message assistant';
            assistantDiv.innerHTML = '<div class="role">assistant</div><div class="content markdown-body markdown-render" id="assistant-content"></div>';
            messagesDiv.appendChild(assistantDiv);
            var contentDiv = document.getElementById('assistant-content');
            contentDiv.textContent = '';
            scrollToBottom();
            
            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var fullContent = '';
            var buffer = '';
            
            while (true) {
                var {done, value} = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, {stream: true});
                var parts = buffer.split(String.fromCharCode(10));
                buffer = parts.pop();
                for (var part of parts) {
                    if (part.indexOf('data: ') === 0) {
                        try {
                            var jsonStr = part.substring(6);
                            if (jsonStr) {
                                var data = JSON.parse(jsonStr);
                                if (data.content) {
                                    fullContent += data.content;
                                    contentDiv.textContent = fullContent;
                                    if (typeof marked !== 'undefined') {
                                        contentDiv.innerHTML = marked.parse(fullContent);
                                        addCopyButtons(assistantDiv);
                                    }
                                    scrollToBottom();
                                }
                            }
                        } catch (e) {}
                    }
                }
            }
        } else {
            var data = await response.json();
            var thinkingEl = document.getElementById('thinking');
            if (thinkingEl) thinkingEl.remove();
            
            if (data.error) {
                renderMessage('assistant', 'Error: ' + data.error);
            } else {
                renderMessage('assistant', data.response);
            }
        }
    } catch (e) {
        console.error('Chat error:', e);
        var thinkingEl = document.getElementById('thinking');
        if (thinkingEl) thinkingEl.remove();
        renderMessage('assistant', 'Error: ' + e.message + '. Check browser console for details.');
    }
    
    btn.disabled = false;
    input.disabled = false;
    input.focus();
}

function renameChat(sessionId, title) {
    fetch('/chat/rename/' + sessionId, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title: title})
    });
}

function deleteChat(sessionId) {
    if (confirm('Delete this chat?')) {
        fetch('/chat/delete/' + sessionId, { method: 'POST' })
            .then(r => r.json())
            .then(d => {
                window.location.href = '/chat';
            });
    }
}

scrollToBottom();

// Render markdown for assistant messages
document.querySelectorAll('.markdown-render').forEach(function(el) {
    if (typeof marked !== 'undefined') {
        el.innerHTML = marked.parse(el.textContent);
    }
});
// Add copy buttons
document.querySelectorAll('.markdown-body').forEach(function(el) {
    el.querySelectorAll('pre').forEach(function(pre) {
        if (pre.querySelector('.copy-btn')) return;
        var code = pre.querySelector('code');
        var text = code ? code.textContent : pre.textContent;
        var btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.onclick = function() {
            navigator.clipboard.writeText(text);
            btn.textContent = 'Copied!';
            setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
        };
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
});
</script>
</body>
</html>
""", session_id=session_id, session_name=session_name, messages=messages, active_page='chat', messages_json=messages)

@app.route("/chat/new", methods=["POST"])
@login_required
def chat_new():
    import uuid
    import time
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO chat_sessions (id, title, created_at) VALUES (?, ?, ?)", (session_id, f"New Chat", time.time()))
    conn.commit()
    conn.close()
    return json.dumps({"session_id": session_id})

@app.route("/chat/delete/<session_id>", methods=["POST"])
@login_required
def chat_delete(session_id):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return json.dumps({"success": True})

@app.route("/chat/rename/<session_id>", methods=["POST"])
@login_required
def chat_rename(session_id):
    import time
    data = request.get_json()
    title = data.get("title", "Untitled")
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()
    return json.dumps({"success": True})

@app.route("/chat/send", methods=["POST"])
@login_required
def chat_send():
    import requests
    import time
    import json
    
    config_path = "/opt/hermes_webui/chat_config.json"
    defaults = {"api_url": "http://127.0.0.1:8642/v1/chat/completions", "timeout": 600, "streaming": True}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            settings = {**defaults, **json.load(f)}
    else:
        settings = defaults
    
    data = request.get_json()
    message = data.get("message", "")
    session_id = data.get("session_id", "")
    
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    
    # Ensure session exists
    cursor.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO chat_sessions (id, title, created_at) VALUES (?, ?, ?)", (session_id, f"Chat", time.time()))
        conn.commit()
    
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY timestamp", (session_id,))
    history = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    conn.close()
    
    messages = history + [{"role": "user", "content": message}]
    
    api_url = settings.get("api_url", HERMES_API_URL)
    timeout = settings.get("timeout", HERMES_API_TIMEOUT)
    streaming = settings.get("streaming", HERMES_STREAMING)
    
    try:
        if streaming:
            resp = requests.post(
                api_url,
                json={"model": "hermes-agent", "messages": messages, "stream": True},
                stream=True,
                timeout=timeout
            )
            
            if resp.status_code == 200:
                # Save display message (without file content) to database
                import re
                display_msg = re.sub(r'\[Attached file: [^\]]+\]', lambda m: m.group(0).split('```')[0].strip() + ']', message) if '[Attached file:' in message else message
                
                conn = get_chat_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "user", display_msg, time.time()))
                conn.commit()
                conn.close()
                
                print("STREAM: Collecting full response", flush=True)
                full_response = ""
                try:
                    for chunk in resp.iter_lines(decode_unicode=True):
                        if chunk:
                            line = chunk.strip()
                            if line.startswith('data: '):
                                data_str = line[6:]
                                if data_str.strip() == '[DONE]':
                                    print("STREAM: Received [DONE]", flush=True)
                                    break
                                try:
                                    chunk_data = json.loads(data_str)
                                    content = chunk_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                    if content:
                                        full_response += content
                                except json.JSONDecodeError:
                                    pass
                except Exception as e:
                    print(f"STREAM: Error: {e}", flush=True)
                
                print(f"STREAM: Got {len(full_response)} chars", flush=True)
                
                # Save response BEFORE returning to client
                if full_response:
                    try:
                        conn2 = get_chat_db_connection()
                        cursor2 = conn2.cursor()
                        cursor2.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", 
                                       (session_id, "assistant", full_response, time.time()))
                        conn2.commit()
                        conn2.close()
                        print("STREAM: Saved to DB", flush=True)
                    except Exception as e:
                        print(f"STREAM: DB error: {e}", flush=True)
                
                return json.dumps({"response": full_response})
            else:
                return json.dumps({"error": f"API Error: {resp.status_code} - {resp.text[:200]}"}), 500
        else:
            resp = requests.post(
                api_url,
                json={"model": "hermes-agent", "messages": messages, "stream": False},
                timeout=timeout
            )
            if resp.status_code == 200:
                result = resp.json()
                response = result["choices"][0]["message"]["content"]
                
                # Save display message (without file content) to database
                import re
                display_msg = re.sub(r'\[Attached file: [^\]]+\]', lambda m: m.group(0).split('```')[0].strip() + ']', message) if '[Attached file:' in message else message
                
                conn = get_chat_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "user", display_msg, time.time()))
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "assistant", response, time.time()))
                conn.commit()
                conn.close()
                
                return json.dumps({"response": response})
            else:
                return json.dumps({"error": f"API Error: {resp.status_code}"}), 500
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

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
