import os, json, sqlite3 
from flask import Flask, request, render_template, flash, redirect, url_for
import logging 
import requests 
from flask_httpauth import HTTPBasicAuth
from pydactyl import PterodactylClient
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from uuid import UUID


load_dotenv()
# Initialize Flask app and logging
app = Flask(__name__)
log_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
log_file = "app.log" # Set log file
handler = logging.FileHandler(log_file)
handler.setFormatter(log_format)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.secret_key = os.getenv("FLASK_SECRET")


# Admin HTTP Basic Auth
auth = HTTPBasicAuth()
ADMIN_CREDENTIALS = json.loads(os.getenv("ADMIN_CREDS"))
@auth.verify_password
def verify(username, password):
    return ADMIN_CREDENTIALS.get(username) == password


# Initialize SQLite database
conn = sqlite3.connect("whitelist.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mc_username TEXT NOT NULL,
    mc_uuid TEXT NOT NULL,
    discord_username TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    ip_address TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS ptero_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    server_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0
)
""")
conn.commit()


# Add IP address if not exists
c.execute("PRAGMA table_info(whitelist)")
cols = [row[1] for row in c.fetchall()]
if "ip_address" not in cols:
    c.execute("ALTER TABLE whitelist ADD COLUMN ip_address TEXT")
    conn.commit()


# Initialize Pterodactyl API client
PTERO_URL = os.getenv("PTERO_API_URL")
PTERO_KEY = os.getenv("PTERO_API_KEY")
api = PterodactylClient(PTERO_URL, PTERO_KEY)


# Sync whitelists with Pterodactyl servers
def sync_whitelists():
    c.execute("SELECT mc_username, mc_uuid FROM whitelist WHERE approved=1")
    entries = c.fetchall()
    whitelist_data = []

    for name, raw_uuid in entries:
        try:
            formatted = str(UUID(raw_uuid))
        except ValueError:
            formatted = raw_uuid
        whitelist_data.append({"uuid": formatted, "name": name})   
    
    payload = json.dumps(whitelist_data, indent=2)  
    c.execute("SELECT server_id FROM ptero_servers WHERE enabled=1")
    servers = [row[0] for row in c.fetchall()]  # Fetch enabled server IDs
    for sid in servers:
        try:
            api.client.servers.files.write_file(sid, "/whitelist.json", payload)  
            api.client.servers.send_console_command(sid, "whitelist reload")  
        except Exception as e:
            app.logger.error(f"Ptero sync failed for {sid}: {e}")

# Schedule periodic sync
Interval = int(os.getenv("SYNC_INTERVAL", 60))
scheduler = BackgroundScheduler()
scheduler.add_job(func=sync_whitelists, trigger="interval", minutes=Interval)
scheduler.start()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        mc_username = request.form["mc_username"].strip()
        discord_username = request.form["discord_username"].strip()
        if not mc_username or not discord_username:
            flash("Both fields are required.", "error")
            return redirect(url_for("index"))

        resp = requests.get(
            f"https://api.minecraftservices.com/minecraft/profile/lookup/name/{mc_username}"
        )
        if resp.status_code != 200:
            flash(f"Minecraft user '{mc_username}' not found.", "error")
            return redirect(url_for("index"))
        raw = resp.json()['id']
        mc_uuid = str(UUID(raw))  # Format UUID properly
        
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        c.execute(
            "INSERT INTO whitelist (mc_username, mc_uuid, discord_username, ip_address) VALUES (?, ?, ?, ?)",
            (mc_username, mc_uuid, discord_username, ip_address)
        )
        conn.commit()
        app.logger.info(f"New request: {mc_username} ({mc_uuid}) from {ip_address}")
        NTFY_URL = os.getenv("NTFY_TOPIC")
        if NTFY_URL:
            requests.post(f"https://ntfy.sh/{NTFY_URL}",
                          data=f"New Request: {mc_username}".encode(encoding='utf-8'))
        else:
            app.logger.info("NTFY_TOPIC not set, skipping notification.")
            
        flash("Your request has been submitted for approval.", "success")
        return redirect(url_for("index"))

    return render_template("index.html")



@app.route("/admin")
@auth.login_required
def admin():
    try:
        raw = api.client.servers.list_servers(params={'per_page': 100})
    except Exception as e:
        app.logger.error(f"OOH YOU FUCKED UP: {e}")
        raw = {}
    servers_list = raw.get('data', raw)  

    for srv in servers_list:
        att = srv.get('attributes', {})
        sid  = att.get('identifier')
        name = att.get('name')
        if sid and name:
            c.execute(
                "SELECT 1 FROM ptero_servers WHERE server_id = ?",
                (sid,)
            )
            if not c.fetchone():
                c.execute(
                    "INSERT INTO ptero_servers (name, server_id) VALUES (?, ?)",
                    (name, sid)
                )
    conn.commit()

    cleanup_ptero_servers()  # Clean up servers not present in API

    c.execute("SELECT id, name, server_id, enabled FROM ptero_servers")
    servers = c.fetchall()

    c.execute("""
      SELECT id, mc_username, mc_uuid, discord_username, ip_address, approved, created_at
        FROM whitelist
        ORDER BY created_at DESC
    """)
    entries = c.fetchall()

    return render_template("admin.html", servers=servers, entries=entries)



# Manage whitelist requests
@app.route("/admin/toggle/<int:req_id>", methods=["POST"])
@auth.login_required
def toggle(req_id):
    c.execute("UPDATE whitelist SET approved = 1 - approved WHERE id = ?", (req_id,)) # Flip approved state
    conn.commit()
    sync_whitelists() 
    return redirect(url_for("admin"))

# Delete user from whitelist list
@app.route("/admin/delete/<int:req_id>", methods=["POST"])
@auth.login_required
def delete(req_id):
    c.execute("DELETE FROM whitelist WHERE id = ?", (req_id,))
    conn.commit()
    flash(f"Request #{req_id} deleted.", "success")
    sync_whitelists()
    return redirect(url_for("admin"))

# Pterodactyl server management
@app.route("/admin/servers", methods=["POST"])
@auth.login_required
def add_server():
    name = request.form["name"].strip()
    sid  = request.form["server_id"].strip()
    if name and sid:
        c.execute(
            "INSERT INTO ptero_servers (name, server_id) VALUES (?, ?)",
            (name, sid)
        )
        conn.commit()
        flash(f"Added server '{name}'.", "success")
    return redirect(url_for("admin"))

# Remove servers from database if not present in Pterodactyl API
def cleanup_ptero_servers():
    app.logger.info("Cleaning up Pterodactyl servers not present in API...")
    try:
        raw = api.client.servers.list_servers(params={'per_page': 100})
    except Exception as e:
        app.logger.error(f"Failed to fetch servers for cleanup: {e}")
        return
    servers_list = raw.get('data', raw)
    current_server_ids = set()
    for srv in servers_list:
        att = srv.get('attributes', {})
        sid = att.get('identifier')
        if sid:
            current_server_ids.add(sid)
    
    # Delete servers not present in API
    c.execute("SELECT server_id FROM ptero_servers")
    db_server_ids = set(row[0] for row in c.fetchall())
    missing = db_server_ids - current_server_ids
    for sid in missing:
        c.execute("DELETE FROM ptero_servers WHERE server_id = ?", (sid,))
        app.logger.info(f"Deleted server {sid} from database (no longer present in Pterodactyl API)")
    if missing:
        conn.commit()
        
    # Reorder IDs to be sequential
    c.execute("SELECT name, server_id, enabled FROM ptero_servers ORDER BY id ASC")
    servers = c.fetchall()
    c.execute("DELETE FROM ptero_servers")
    for idx, (name, server_id, enabled) in enumerate(servers, start=1):
        c.execute(
            "INSERT INTO ptero_servers (id, name, server_id, enabled) VALUES (?, ?, ?, ?)",
            (idx, name, server_id, enabled)
        )
    conn.commit()
# Pterodactyl server toggle
@app.route("/admin/servers/toggle/<int:srv_id>", methods=["POST"])
@auth.login_required
def toggle_server(srv_id):
    c.execute("UPDATE ptero_servers SET enabled = 1 - enabled WHERE id = ?", (srv_id,)) # Flip enabled state
    conn.commit()
    sync_whitelists()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
