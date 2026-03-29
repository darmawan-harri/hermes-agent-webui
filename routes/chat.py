import os
import json
import time
import uuid
import requests
from flask import Blueprint, render_template_string, request, jsonify, Response
from flask_login import login_required, current_user
import config

chat_bp = Blueprint('chat', __name__)

CHAT_DB_PATH = "/opt/hermes_webui/chat.db"

def get_chat_db_connection():
    import sqlite3
    conn = sqlite3.connect(CHAT_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
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

CHAT_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; }
.sidebar { width: 240px; background: #1e293b; padding: 20px 0; flex-shrink: 0; }
.sidebar-logo { padding: 0 20px 20px; border-bottom: 1px solid #334155; margin-bottom: 10px; }
.sidebar-logo h2 { font-size: 22px; }
.menu-item { padding: 14px 20px; color: #94a3b8; text-decoration: none; display: block; }
.menu-item:hover { background: #334155; color: white; }
.menu-item.active { background: #3b82f6; color: white; }
.menu-logout { margin-top: auto; border-top: 1px solid #334155; padding-top: 10px; }
.main { flex: 1; padding: 24px; overflow: auto; }
h1 { color: #f1f5f9; margin-bottom: 20px; font-size: 28px; }
.chat-container { display: flex; height: calc(100vh - 120px); gap: 20px; }
.chat-sidebar { width: 250px; background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; overflow-y: auto; }
.chat-sidebar h3 { color: #f1f5f9; font-size: 16px; margin-bottom: 16px; }
.session-item { padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; }
.session-item:hover { background: #334155; }
.session-item a { color: #e2e8f0; text-decoration: none; display: block; }
.chat-main { flex: 1; background: #1e293b; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column; }
.chat-header { padding: 16px; border-bottom: 1px solid #334155; }
.chat-header input { background: none; border: none; color: #f1f5f9; font-size: 18px; font-weight: 600; flex: 1; }
.chat-header input:focus { outline: 1px solid #3b82f6; padding: 4px 8px; border-radius: 4px; }
.chat-header button { background: #dc2626; border: none; color: white; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.message { margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; max-width: 80%; }
.message.user { background: #3b82f6; margin-left: auto; border-bottom-right-radius: 4px; }
.message.assistant { background: #334155; border-bottom-left-radius: 4px; }
.message .role { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
.message .content { color: #e2e8f0; line-height: 1.5; white-space: pre-wrap; }
.chat-input { padding: 16px; border-top: 1px solid #334155; display: flex; gap: 12px; align-items: flex-end; }
.chat-input .input-wrapper { flex: 1; }
.chat-input textarea { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 15px; resize: none; min-height: 48px; max-height: 200px; }
.chat-input textarea:focus { outline: none; border-color: #3b82f6; }
.chat-input button { padding: 12px 24px; border-radius: 8px; border: none; background: #3b82f6; color: white; cursor: pointer; }
.chat-input button:disabled { background: #475569; cursor: not-allowed; }
.new-chat-btn { display: block; width: 100%; padding: 12px; border-radius: 6px; border: 1px dashed #334155; background: none; color: #60a5fa; cursor: pointer; margin-bottom: 16px; text-align: center; }
.new-chat-btn:hover { background: #334155; }
.empty-state { display: flex; align-items: center; justify-content: center; height: 100%; color: #64748b; }
.thinking { color: #64748b; font-style: italic; }
.markdown-body { line-height: 1.5; }
.markdown-body h1, .markdown-body h2, .markdown-body h3 { color: #f1f5f9; margin: 12px 0 6px 0; }
.markdown-body p { margin: 6px 0; }
.markdown-body code { background: #0f172a; padding: 2px 5px; border-radius: 3px; font-family: monospace; color: #fb923c; }
.markdown-body pre { background: #0f172a; padding: 10px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }
.markdown-body pre code { background: none; padding: 0; color: #e2e8f0; }
.markdown-body blockquote { border-left: 3px solid #3b82f6; padding-left: 10px; color: #94a3b8; }
.markdown-body table { border-collapse: collapse; width: 100%; margin: 8px 0; }
.markdown-body th, .markdown-body td { border: 1px solid #475569; padding: 6px 10px; text-align: left; }
.markdown-body th { background: #1e3a5f; color: #60a5fa; }
"""

CHAT_LIST_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat - Hermes</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>""" + CHAT_STYLE + """
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo"><h2>Hermes</h2></div>
    <a href="/" class="menu-item">Cron Jobs</a>
    <a href="/skills" class="menu-item">List Skill</a>
    <a href="/scripts" class="menu-item">Scripts</a>
    <a href="/memories" class="menu-item">Memories</a>
    <a href="/sessions" class="menu-item">Sessions</a>
    <a href="/chat" class="menu-item active">Chat</a>
    <a href="/chat/settings" class="menu-item">Chat Settings</a>
    <a href="/change_password" class="menu-item">Change Password</a>
    <a href="/logout" class="menu-item menu-logout">Logout</a>
</div>
<div class="main">
    <h1>Chat</h1>
    <div class="chat-container">
        <div class="chat-sidebar">
            <button class="new-chat-btn" onclick="newChat()">+ New Chat</button>
            <h3>Sessions</h3>
            {% for s in sessions %}
            <div class="session-item">
                <a href="/chat/{{ s.id }}">{{ s.title[:20] }}</a>
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
"""

CHAT_SESSION_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Chat - Hermes</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>""" + CHAT_STYLE + """
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo"><h2>Hermes</h2></div>
    <a href="/" class="menu-item">Cron Jobs</a>
    <a href="/skills" class="menu-item">List Skill</a>
    <a href="/scripts" class="menu-item">Scripts</a>
    <a href="/memories" class="menu-item">Memories</a>
    <a href="/sessions" class="menu-item">Sessions</a>
    <a href="/chat" class="menu-item active">Chat</a>
    <a href="/chat/settings" class="menu-item">Chat Settings</a>
    <a href="/change_password" class="menu-item">Change Password</a>
    <a href="/logout" class="menu-item menu-logout">Logout</a>
</div>
<div class="main">
    <h1>Chat</h1>
    <div class="chat-container">
        <div class="chat-sidebar">
            <button class="new-chat-btn" onclick="newChat()">+ New Chat</button>
            <h3>Sessions</h3>
            <div class="session-item"><a href="/chat">← Back</a></div>
        </div>
        <div class="chat-main">
            <div class="chat-header">
                <input type="text" value=""" + json.dumps('{{ session_title }}') + """ onchange="renameChat('{{ session_id }}', this.value)">
                <button onclick="deleteChat('{{ session_id }}')">Delete</button>
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
                <div class="input-wrapper"><textarea id="userInput" placeholder="Type... (Shift+Enter for new line)"></textarea></div>
                <button id="sendBtn" onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
</div>
<script>
var sessionId = '{{ session_id }}';
var messages = """ + json.dumps([]) + """;

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
    document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
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
        div.innerHTML = '<div class="role">' + role + '</div><div class="content markdown-body markdown-render">' + marked.parse(content) + '</div>';
    } else {
        div.innerHTML = '<div class="role">' + role + '</div><div class="content">' + escapeHtml(content) + '</div>';
    }
    container.appendChild(div);
    scrollToBottom();
}

async function sendMessage() {
    var input = document.getElementById('userInput');
    var btn = document.getElementById('sendBtn');
    var message = input.value.trim();
    if (!message || btn.disabled) return;
    
    btn.disabled = true;
    input.disabled = true;
    input.value = '';
    
    renderMessage('user', message);
    
    var thinking = document.createElement('div');
    thinking.className = 'message assistant';
    thinking.id = 'thinking';
    thinking.innerHTML = '<div class="role">assistant</div><div class="content thinking">Thinking...</div>';
    document.getElementById('messages').appendChild(thinking);
    scrollToBottom();
    
    try {
        var response = await fetch('/chat/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId, message: message})
        });
        
        if (response.headers.get('content-type') === 'text/event-stream') {
            document.getElementById('thinking').remove();
            var assistantDiv = document.createElement('div');
            assistantDiv.className = 'message assistant';
            assistantDiv.innerHTML = '<div class="role">assistant</div><div class="content markdown-body markdown-render" id="assistant-content"></div>';
            document.getElementById('messages').appendChild(assistantDiv);
            var contentDiv = document.getElementById('assistant-content');
            contentDiv.textContent = '';
            scrollToBottom();
            
            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            while (true) {
                var {done, value} = await reader.read();
                if (done) break;
                var text = decoder.decode(value);
                var lines = text.split('\\n');
                for (var line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            var data = JSON.parse(line.slice(6));
                            if (data.content) {
                                contentDiv.textContent += data.content;
                                if (typeof marked !== 'undefined') {
                                    contentDiv.innerHTML = marked.parse(contentDiv.textContent);
                                }
                                scrollToBottom();
                            }
                        } catch (e) {}
                    }
                }
            }
        } else {
            var data = await response.json();
            document.getElementById('thinking').remove();
            if (data.error) renderMessage('assistant', 'Error: ' + data.error);
            else renderMessage('assistant', data.response);
        }
    } catch (e) {
        console.error(e);
        document.getElementById('thinking').remove();
        renderMessage('assistant', 'Error: ' + e.message);
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
            .then(d => { window.location.href = '/chat'; });
    }
}

function newChat() {
    fetch('/chat/new', { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            if (d.session_id) window.location.href = '/chat/' + d.session_id;
        });
}

scrollToBottom();
</script>
</body>
</html>
"""

@chat_bp.route("/chat")
@login_required
def chat_index():
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, COALESCE(title, id) as title FROM chat_sessions ORDER BY created_at DESC LIMIT 10")
    sessions = [{"id": row[0], "title": row[1]} for row in cursor.fetchall()]
    conn.close()
    return render_template_string(CHAT_LIST_HTML, sessions=sessions)

@chat_bp.route("/chat/<session_id>")
@login_required
def chat_session(session_id):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(title, id) FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    session_title = row[0] if row else "New Chat"
    
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY timestamp", (session_id,))
    messages = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    conn.close()
    
    return render_template_string(CHAT_SESSION_HTML, session_id=session_id, session_title=session_title, messages=messages)

@chat_bp.route("/chat/new", methods=["POST"])
@login_required
def chat_new():
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO chat_sessions (id, title, created_at) VALUES (?, ?, ?)", (session_id, f"New Chat", time.time()))
    conn.commit()
    conn.close()
    return jsonify({"session_id": session_id})

@chat_bp.route("/chat/delete/<session_id>", methods=["POST"])
@login_required
def chat_delete(session_id):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@chat_bp.route("/chat/rename/<session_id>", methods=["POST"])
@login_required
def chat_rename(session_id):
    data = request.get_json()
    title = data.get("title", "Untitled")
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@chat_bp.route("/chat/send", methods=["POST"])
@login_required
def chat_send():
    config_path = "/opt/hermes_webui/chat_config.json"
    defaults = {"api_url": config.HERMES_API_URL, "timeout": config.HERMES_API_TIMEOUT, "streaming": config.HERMES_STREAMING}
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
    cursor.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO chat_sessions (id, title, created_at) VALUES (?, ?, ?)", (session_id, f"Chat", time.time()))
        conn.commit()
    
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY timestamp", (session_id,))
    history = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    conn.close()
    
    messages = history + [{"role": "user", "content": message}]
    api_url = settings.get("api_url", config.HERMES_API_URL)
    timeout = settings.get("timeout", config.HERMES_API_TIMEOUT)
    streaming = settings.get("streaming", config.HERMES_STREAMING)
    
    try:
        if streaming:
            resp = requests.post(api_url, json={"model": "hermes-agent", "messages": messages, "stream": True}, stream=True, timeout=timeout)
            
            if resp.status_code == 200:
                conn = get_chat_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "user", message, time.time()))
                conn.commit()
                conn.close()
                
                def generate():
                    full_response = ""
                    try:
                        for chunk in resp.iter_lines():
                            if chunk:
                                line = chunk.decode('utf-8')
                                if line.startswith('data: '):
                                    data_str = line[6:]
                                    if data_str.strip() == '[DONE]': break
                                    try:
                                        chunk_data = json.loads(data_str)
                                        content = chunk_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                        if content:
                                            full_response += content
                                            yield f"data: {json.dumps({'content': content})}\n\n"
                                    except: pass
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    
                    if full_response:
                        try:
                            conn = get_chat_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "assistant", full_response, time.time()))
                            conn.commit()
                            conn.close()
                        except: pass
                
                return Response(generate(), mimetype='text/event-stream')
            else:
                return jsonify({"error": f"API Error: {resp.status_code}"}), 500
        else:
            resp = requests.post(api_url, json={"model": "hermes-agent", "messages": messages, "stream": False}, timeout=timeout)
            if resp.status_code == 200:
                result = resp.json()
                response = result["choices"][0]["message"]["content"]
                
                conn = get_chat_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "user", message, time.time()))
                cursor.execute("INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)", (session_id, "assistant", response, time.time()))
                conn.commit()
                conn.close()
                
                return jsonify({"response": response})
            else:
                return jsonify({"error": f"API Error: {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
