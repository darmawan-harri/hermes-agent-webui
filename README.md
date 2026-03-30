# Hermes WebUI

Flask-based web UI untuk mengeksplorasi folder-folder di `/root/.hermes/` dan berinteraksi dengan Hermes Agent.

## Fitur

- **Login Authentication** - User admin dengan password aman
- **Dark Mode UI** - Tampilan modern dengan tema gelap
- **Menu Sections:**
  - Cron Jobs - Lihat jadwal cron jobs
  - File Explorer (Dropdown):
    - Browse - File explorer dengan tree view
    - Skills - Eksplorasi skills
    - Scripts - Eksplorasi scripts
    - Memories - Eksplorasi memories
    - Image Cache - Thumbnail preview gambar
    - Browser Screenshots - Preview screenshot
    - Sessions - Table view dengan View/Delete
  - Chat - Chat dengan Hermes Agent via OpenAI API
  - Configuration (Dropdown):
    - Chat Settings - Konfigurasi API URL, timeout, streaming
    - SOUL.md - Tampilkan file persona agent
    - state.db - Database viewer seperti phpMyAdmin
    - config.yaml - Konfigurasi dengan syntax highlighting
    - Change Password - Ganti password
- **Login Page** - Modern login dengan logo Hermes
- **Sidebar** - Dengan logo dan dropdown menus

## Chat Features

- **Real-time Chat** - Chat dengan Hermes Agent
- **Markdown Rendering** - Response dirender sebagai markdown
- **Code Highlighting** - Syntax highlighting untuk code blocks
- **Copy Button** - Copy code dengan satu klik
- **Chat History** - Simpan dan load riwayat chat
- **File Attachment** - Upload file untuk konteks chat
- **Multiline Input** - Shift+Enter untuk baris baru
- **Streaming Support** - Response real-time (opsional)

## JSON Viewer Features

- **Table View** - Grid seperti spreadsheet
- **Syntax Highlighting** - Warna berbeda untuk string, number, boolean, null
- **Hide/Show** - Klik ▶ untuk expand/collapse object dan array
- **JSON/JSONL** - Mendukung kedua format

## Instalasi

### 1. Clone/Setup Project

```bash
cd /opt/hermes_webui
python -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy flask-login werkzeug markdown pyyaml
```

### 2. Setup Database

```bash
# Akses http://localhost:5000/setup untuk buat user admin
# Atau reset password via:
python -c "from app import app, db, User; from werkzeug.security import generate_password_hash; app.app_context().push(); db.session.add(User(username='admin', password=generate_password_hash('admin123', method='pbkdf2:sha256'))); db.session.commit()"
```

### 3. Konfigurasi Apache SSL (Port 4436)

```bash
# Install Apache dan module
apt install -y apache2 libapache2-mod-wsgi-py3
a2enmod ssl proxy proxy_http headers rewrite

# Buat SSL certificate
mkdir -p /etc/apache2/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/apache2/ssl/apache.key \
    -out /etc/apache2/ssl/apache.crt \
    -subj "/C=ID/ST=Jakarta/L=Jakarta/O=Hermes/CN=192.168.70.31"

# Tambah port 4436 ke /etc/apache2/ports.conf
echo "Listen 4436" >> /etc/apache2/ports.conf

# Copy config
cp /opt/hermes_webui/hermes-ssl.conf /etc/apache2/sites-available/
a2ensite hermes-ssl
systemctl restart apache2
```

**Catatan:** Apache config sudah include streaming support (`proxy-sendchunked`, `proxy-nokeepalive`, `ProxyTimeout 600`).

### 4. Setup systemd Service

```bash
cp /opt/hermes_webui/hermes-webui.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hermes-webui
systemctl start hermes-webui
```

## Akses

```
https://192.168.70.31:4436
```

**Default Credentials:**
- Username: `admin`
- Password: `admin123`

## Commands

```bash
# Service
systemctl start hermes-webui
systemctl stop hermes-webui
systemctl restart hermes-webui
systemctl status hermes-webui

# Flask langsung
cd /opt/hermes_webui
source venv/bin/activate
python app.py

# Logs
tail -f /tmp/flask.log
journalctl -u hermes-webui -f
```

## Struktur Folder

```
/opt/hermes_webui/
├── app.py              # Main Flask application
├── config.py           # Configuration (folder paths)
├── users.db            # SQLite user database
├── chat.db             # SQLite chat database
├── chat_config.json    # Chat settings (API URL, timeout, streaming)
├── hermes-webui.service # Systemd service file
└── venv/               # Python virtual environment
```

## Chat Configuration

Chat settings disimpan di `/opt/hermes_webui/chat_config.json`:

```json
{
  "api_url": "http://127.0.0.1:8642/v1/chat/completions",
  "timeout": 600,
  "streaming": true
}
```

Atau ubah melalui **Chat Settings** di menu.

## Konfigurasi Folder

Edit `/opt/hermes_webui/config.py`:

```python
ROOT_HERMES_FOLDER = "/root/.hermes/"
SCRIPTS_FOLDER = "/root/.hermes/scripts"
MEMORIES_FOLDER = "/root/.hermes/memories"
IMAGE_CACHE_FOLDER = "/root/.hermes/image_cache"
BROWSER_SCREENSHOTS_FOLDER = "/root/.hermes/browser_screenshots"
SESSIONS_FOLDER = "/root/.hermes/sessions"

# Chat settings (Hermes Agent API)
HERMES_API_URL = "http://127.0.0.1:8642/v1/chat/completions"
HERMES_API_TIMEOUT = 600  # 10 minutes
HERMES_STREAMING = True
```

## Prerequisites

- **Hermes Agent** berjalan dengan API Server enabled:
  ```bash
  API_SERVER_ENABLED=true API_SERVER_PORT=8642 hermes-gateway
  ```

## Teknologi

- **Backend:** Flask, SQLAlchemy, Flask-Login
- **Frontend:** HTML, CSS (Dark Mode), JavaScript, Marked.js (markdown)
- **Server:** Apache2 with SSL (mod_proxy, streaming support)
- **Database:** SQLite (users.db, chat.db)
