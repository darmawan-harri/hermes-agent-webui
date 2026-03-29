import os
import json
from flask import Blueprint, render_template_string, request, flash, redirect, url_for
from flask_login import login_required

chat_settings_bp = Blueprint('chat_settings', __name__)

STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; flex-shrink: 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.main { flex: 1; padding: 24px; }
h1 { color: #f1f5f9; margin-bottom: 20px; }
.settings-box { background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; max-width: 600px; }
.settings-box h2 { color: #f1f5f9; margin-bottom: 24px; }
.form-group { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; color: #94a3b8; font-weight: 500; }
.form-group input { width: 100%; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; }
.form-group input:focus { outline: none; border-color: #3b82f6; }
.hint { font-size: 12px; color: #64748b; margin-top: 4px; }
.btn { padding: 12px 24px; border-radius: 6px; border: none; background: #3b82f6; color: white; cursor: pointer; }
.btn:hover { background: #2563eb; }
.flash { padding: 12px; border-radius: 6px; margin-bottom: 20px; }
.flash-success { background: #14532d; color: #4ade80; }
"""

CHAT_SETTINGS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat Settings - Hermes</title>
<style>""" + STYLE + """
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo"><h2>Hermes</h2></div>
    <a href="/" class="menu-item">Cron Jobs</a>
    <a href="/chat" class="menu-item active">Chat</a>
    <a href="/chat/settings" class="menu-item">Chat Settings</a>
    <a href="/change_password" class="menu-item">Change Password</a>
    <a href="/logout" class="menu-item menu-logout">Logout</a>
</div>
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
                <input type="text" name="api_url" value="""" + """{{ settings.api_url }}""" + """" required>
                <div class="hint">OpenAI-compatible API endpoint</div>
            </div>
            <div class="form-group">
                <label>Timeout (seconds)</label>
                <input type="number" name="timeout" value="""" + """{{ settings.timeout }}""" + """" min="60" max="3600">
                <div class="hint">Max wait time for response</div>
            </div>
            <div class="form-group">
                <label><input type="checkbox" name="streaming" """ + """{% if settings.streaming %}checked{% endif %}""" + """ id="streaming"> Enable Streaming</label>
                <div class="hint">Show response as it generates</div>
            </div>
            <button type="submit" class="btn">Save Settings</button>
        </form>
    </div>
</div>
</body>
</html>
"""

@chat_settings_bp.route("/chat/settings", methods=["GET", "POST"])
@login_required
def chat_settings():
    config_path = "/opt/hermes_webui/chat_config.json"
    defaults = {"api_url": "http://127.0.0.1:8642/v1/chat/completions", "timeout": 600, "streaming": True}
    
    if request.method == "POST":
        data = {
            "api_url": request.form.get("api_url", ""),
            "timeout": int(request.form.get("timeout", 600)),
            "streaming": request.form.get("streaming") == "on"
        }
        with open(config_path, "w") as f:
            json.dump(data, f)
        flash("Settings saved!", "success")
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            settings = {**defaults, **json.load(f)}
    else:
        settings = defaults
    
    return render_template_string(CHAT_SETTINGS_HTML, settings=settings)
