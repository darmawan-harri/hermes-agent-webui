import os
import json
import secrets
from flask import Blueprint, render_template_string, request, send_file
from flask_login import login_required
import config

files_bp = Blueprint('files', __name__)

STATE_DB_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "state.db")
CONFIG_YAML_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "config.yaml")
SOUL_MD_PATH = os.path.join(config.ROOT_HERMES_FOLDER, "SOUL.md")

STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; flex-shrink: 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; transition: 0.2s; font-size: 15px; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.menu-logout { margin-top: auto; border-top: 1px solid #334155; padding-top: 10px; }
.main { flex: 1; padding: 24px; overflow: auto; }
h1 { color: #f1f5f9; margin-bottom: 20px; font-size: 28px; }
.file-explorer { background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 20px; border: 1px solid #334155; }
.breadcrumb { color: #64748b; margin-bottom: 16px; font-size: 14px; }
.breadcrumb a { color: #60a5fa; text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.file-list { list-style: none; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.file-item { padding: 10px 12px; border-radius: 4px; }
.file-item:hover { background: #334155; }
.file-item a { color: #e2e8f0; text-decoration: none; display: block; }
.file-item.folder a { color: #fb923c; }
.file-viewer { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
.file-viewer-header { display: flex; justify-content: space-between; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #334155; }
.file-viewer-title { font-size: 18px; font-weight: 600; color: #f1f5f9; }
.file-content { background: #0f172a; padding: 16px; border-radius: 4px; overflow-x: auto; }
.file-content pre { margin: 0; white-space: pre-wrap; font-family: 'Consolas', monospace; font-size: 14px; color: #e2e8f0; }
.view-toggle { background: #334155; color: #e2e8f0; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.view-toggle.active { background: #3b82f6; }
.table-view { overflow-x: auto; }
.table-view table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table-view th, .table-view td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }
.table-view th { background: #334155; color: #f1f5f9; }
.json-grid { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; border: 1px solid #334155; border-radius: 8px; overflow: hidden; }
.json-grid th { background: #1e3a5f; color: #60a5fa; padding: 12px; text-align: left; }
.json-grid td { padding: 10px; border-bottom: 1px solid #1e293b; }
.json-grid tr:hover td { background: #1e293b; }
.json-key { color: #ffcb6b; }
.json-string { color: #c3e88d; }
.json-number { color: #f78c6c; }
.json-boolean { color: #c792ea; }
.json-null { color: #546e7a; }
.json-toggle { cursor: pointer; color: #60a5fa; margin-right: 4px; }
.json-object, .json-array { color: #60a5fa; }
"""

def get_file_list(path, base_path):
    items = []
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            rel_path = os.path.relpath(item_path, base_path)
            is_dir = os.path.isdir(item_path)
            if is_dir:
                items.append({'name': item, 'path': rel_path, 'is_dir': True, 'size': '-', 'date': '-'})
            else:
                stat = os.stat(item_path)
                size = stat.st_size
                if size < 1024: size_str = f"{size} B"
                elif size < 1024 * 1024: size_str = f"{size / 1024:.1f} KB"
                else: size_str = f"{size / (1024 * 1024):.1f} MB"
                import datetime
                date_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                items.append({'name': item, 'path': rel_path, 'is_dir': False, 'size': size_str, 'date': date_str})
    except: pass
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
                            try: lines.append(json.loads(line))
                            except: lines.append(line)
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

def json_to_table(data, expanded=False):
    from html import escape
    def get_type(v):
        if isinstance(v, bool): return 'boolean'
        if isinstance(v, int) or isinstance(v, float): return 'number'
        if v is None: return 'null'
        if isinstance(v, str): return 'string'
        if isinstance(v, dict): return 'object'
        if isinstance(v, list): return 'array'
        return 'string'
    
    def format_value(v):
        t = get_type(v)
        if t == 'object':
            count = len(v) if isinstance(v, dict) else 0
            uid = f"obj_{secrets.token_hex(8)}"
            return f"<span class='json-toggle' onclick=\"toggleJson('{uid}')\">▶</span> <span class='json-object'>Object [{count} keys]</span><div id='{uid}' class='json-collapsed' style='display:{"none" if not expanded else "block"};margin-left:20px;'>{json_to_table(v, expanded)}</div>"
        elif t == 'array':
            count = len(v) if isinstance(v, list) else 0
            uid = f"arr_{secrets.token_hex(8)}"
            return f"<span class='json-toggle' onclick=\"toggleJson('{uid}')\">▶</span> <span class='json-array'>Array [{count} items]</span><div id='{uid}' class='json-collapsed' style='display:{"none" if not expanded else "block"};margin-left:20px;'>{json_to_table(v, expanded)}</div>"
        elif t == 'string': return f"<span class='json-string'>\"{escape(str(v))}\"</span>"
        elif t == 'number': return f"<span class='json-number'>{v}</span>"
        elif t == 'boolean': return f"<span class='json-boolean'>{str(v).lower()}</span>"
        elif t == 'null': return f"<span class='json-null'>null</span>"
        return escape(str(v))
    
    if isinstance(data, dict):
        rows = [f"<tr><td class='json-key'>{escape(str(k))}</td><td>{format_value(v)}</td></tr>" for k, v in data.items()]
        return "<table class='json-grid'><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    elif isinstance(data, list):
        if not data: return "<div style='color:#64748b;'>Empty array</div>"
        if isinstance(data[0], dict):
            keys = list(data[0].keys())
            header = "<tr><th>#</th>" + "".join(f"<th>{escape(str(k))}</th>" for k in keys) + "</tr>"
            rows = [f"<tr><td>{i}</td>" + "".join(f"<td>{format_value(row.get(k))}</td>" for k in keys) + "</tr>" for i, row in enumerate(data)]
            return "<table class='json-grid'><thead>" + header + "</thead><tbody>" + "".join(rows) + "</tbody></table>"
        else:
            rows = [f"<tr><td>{i}</td><td>{format_value(item)}</td></tr>" for i, item in enumerate(data)]
            return "<table class='json-grid'><thead><tr><th>#</th><th>Value</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    return escape(str(data))

SIDEBAR = """
<div class="sidebar">
    <div class="sidebar-logo"><h2>Hermes</h2></div>
    <a href="/" class="menu-item">Cron Jobs</a>
    <a href="/skills" class="menu-item">List Skill</a>
    <a href="/scripts" class="menu-item">Scripts</a>
    <a href="/memories" class="menu-item">Memories</a>
    <a href="/sessions" class="menu-item">Sessions</a>
    <a href="/chat" class="menu-item">Chat</a>
    <a href="/chat/settings" class="menu-item">Chat Settings</a>
    <a href="/change_password" class="menu-item">Change Password</a>
    <a href="/logout" class="menu-item menu-logout">Logout</a>
</div>
"""

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hermes</title>
<style>""" + STYLE + """
.json-collapsed { border-left: 2px solid #334155; padding-left: 8px; }
</style>
</head>
<body>
""" + SIDEBAR + """
<div class="main">
    <h1>""" + """{{ title }}""" + """ Explorer</h1>
    <div class="file-explorer">
        <div class="breadcrumb"><a href="{{ base_url }}">{{ folder_name }}</a>{% if current_path %}/{% for p in current_path.split('/') %}<a href="{{ base_url }}/{{ current_path.split('/')[:loop.index]|join('/') }}">{{ p }}</a>{% if not loop.last %}/{% endif %}{% endfor %}{% endif %}</div>
        <ul class="file-list">
            {% if parent_path %}<li class="file-item folder"><a href="{{ base_url }}/{{ parent_path }}">..</a></li>{% endif %}
            {% for item in items %}
            <li class="file-item {{ 'folder' if item.is_dir else 'file' }}">
                <a href="{{ base_url }}/{{ item.path if item.is_dir else 'view/' + item.path }}">{{ item.name }}{% if item.is_dir %}/{% endif %}</a>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% if file_content %}
    <div class="file-viewer">
        <div class="file-viewer-header">
            <div class="file-viewer-title">{{ file_name }}</div>
            <div>{% if is_json %}<button class="view-toggle" onclick="toggleView()">View as Table</button>{% endif %}</div>
        </div>
        <div id="code-view" class="file-content{% if is_markdown %} markdown-content{% endif %}">{% if is_markdown %}{{ file_content|safe }}{% else %}<pre>{{ file_content }}</pre>{% endif %}</div>
        {% if is_json and json_table %}<div id="table-view" class="file-content table-view" style="display:none;">{{ json_table|safe }}</div>{% endif %}
    </div>
    {% endif %}
</div>
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
        if (toggle) toggle.textContent = '▼';
    } else {
        el.style.display = 'none';
        if (toggle) toggle.textContent = '▶';
    }
}
</script>
</body>
</html>
"""

@files_bp.route("/skills")
@files_bp.route("/skills/<path:path>")
@login_required
def skills(path=""):
    return explorer(path, config.SKILLS_FOLDER, '/skills', 'skills', 'List Skill')

@files_bp.route("/scripts")
@files_bp.route("/scripts/<path:path>")
@login_required
def scripts(path=""):
    return explorer(path, config.SCRIPTS_FOLDER, '/scripts', 'scripts', 'Scripts')

@files_bp.route("/memories")
@files_bp.route("/memories/<path:path>")
@login_required
def memories(path=""):
    return explorer(path, config.MEMORIES_FOLDER, '/memories', 'memories', 'Memories')

def explorer(path, folder, base_url, active, title):
    full_path = os.path.join(folder, path)
    if not os.path.exists(full_path):
        return "Path not found", 404
    
    if os.path.isfile(full_path):
        return file_viewer(path, folder, base_url, title)
    
    items = get_file_list(full_path, folder)
    parent_path = '/'.join(path.split('/')[:-1]) if path else ""
    
    return render_template_string(EXPLORER_HTML,
        items=items, current_path=path, parent_path=parent_path,
        file_content=None, base_url=base_url, folder_name=title, title=title)

def file_viewer(path, folder, base_url, title):
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
            else:
                json_data = []
                with open(full_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try: json_data.append(json.loads(line))
                            except: pass
            json_table = json_to_table(json_data)
        except:
            is_json = False
    
    current_path = os.path.dirname(path)
    parent_path = '/'.join(current_path.split('/')[:-1]) if current_path else ""
    items = get_file_list(os.path.join(folder, current_path), folder) if current_path else []
    
    return render_template_string(EXPLORER_HTML,
        items=items, current_path=current_path, parent_path=parent_path,
        file_content=content, file_name=os.path.basename(path),
        is_json=is_json, is_markdown=is_markdown, json_table=json_table,
        base_url=base_url, folder_name=title, title=title)

@files_bp.route("/view/<path:path>")
@login_required
def view_file(path):
    for folder, base_url, title in [
        (config.SCRIPTS_FOLDER, '/scripts', 'Scripts'),
        (config.MEMORIES_FOLDER, '/memories', 'Memories'),
        (config.SKILLS_FOLDER, '/skills', 'Skills'),
    ]:
        full_path = os.path.join(folder, path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return file_viewer(path, folder, base_url, title)
    return "File not found", 404
