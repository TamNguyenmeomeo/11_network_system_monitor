import os
import sys
import time
import json
import sqlite3
import subprocess
import psutil
import requests

# Set stdout/stderr encoding to UTF-8 to prevent Windows terminal encoding issues with emojis
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Default Configuration
DEFAULT_CONFIG = {
    "db_name": "monitor_logs.db",
    "check_interval_seconds": 10,
    "cpu_alert_threshold": 90.0,
    "ram_alert_threshold": 90.0,
    "disk_alert_threshold": 90.0,
    "webhook_url": "",  # Discord webhook URL or general endpoint
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "hosts_to_ping": [
        {"name": "Local Loopback", "ip": "127.0.0.1"},
        {"name": "Google DNS", "ip": "8.8.8.8"},
        {"name": "Cloudflare DNS", "ip": "1.1.1.1"}
    ]
}

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# Initialize Database
def init_db(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cpu_usage REAL,
            ram_usage REAL,
            disk_usage REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS host_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            host_name TEXT,
            ip_address TEXT,
            is_online INTEGER
        )
    """)
    conn.commit()
    conn.close()

# Ping utility compatible with Windows and Unix
def ping_host(ip):
    # Determine OS parameters
    param = "-n" if sys.platform.lower().startswith("win") else "-c"
    command = ["ping", param, "1", "-w", "1000", ip]
    try:
        # Hide standard outputs
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False

# Log metrics to DB
def log_system_metrics(db_name, cpu, ram, disk):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_metrics (cpu_usage, ram_usage, disk_usage) VALUES (?, ?, ?)",
        (cpu, ram, disk)
    )
    conn.commit()
    conn.close()

def log_host_status(db_name, name, ip, is_online):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO host_status (host_name, ip_address, is_online) VALUES (?, ?, ?)",
        (name, ip, int(is_online))
    )
    conn.commit()
    conn.close()

# Notification Dispatcher
def send_alert(config, message):
    print(f"\n⚠️  [ALERT TRIGGERED]: {message}")
    
    # Send to Discord Webhook
    if config["webhook_url"]:
        try:
            requests.post(config["webhook_url"], json={"content": f"🚨 **IT Monitor Alert:** {message}"})
        except Exception as e:
            print(f"Failed to dispatch Discord alert: {e}")
            
    # Send to Telegram
    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/sendMessage"
        try:
            requests.post(url, json={"chat_id": config["telegram_chat_id"], "text": f"🚨 IT Monitor Alert:\n{message}"})
        except Exception as e:
            print(f"Failed to dispatch Telegram alert: {e}")

# Core evaluation
def run_checks(config, simulate_spikes=False):
    # Fetch parameters
    cpu = 95.0 if simulate_spikes else psutil.cpu_percent(interval=1)
    ram = 92.5 if simulate_spikes else psutil.virtual_memory().percent
    disk = psutil.disk_usage('C:\\' if sys.platform.lower().startswith("win") else '/').percent
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] system checking... CPU: {cpu}% | RAM: {ram}% | Disk: {disk}%")
    log_system_metrics(config["db_name"], cpu, ram, disk)
    
    # Check system thresholds
    if cpu > config["cpu_alert_threshold"]:
        send_alert(config, f"High CPU usage detected: {cpu}% (Threshold: {config['cpu_alert_threshold']}%)")
    if ram > config["ram_alert_threshold"]:
        send_alert(config, f"High RAM usage detected: {ram}% (Threshold: {config['ram_alert_threshold']}%)")
    if disk > config["disk_alert_threshold"]:
        send_alert(config, f"High Disk usage detected: {disk}% (Threshold: {config['disk_alert_threshold']}%)")
        
    # Check Hosts ping status
    for host in config["hosts_to_ping"]:
        is_online = ping_host(host["ip"])
        status_str = "ONLINE" if is_online else "OFFLINE"
        print(f" -> Host {host['name']} ({host['ip']}): {status_str}")
        log_host_status(config["db_name"], host["name"], host["ip"], is_online)
        
        if not is_online:
            send_alert(config, f"Host {host['name']} ({host['ip']}) is OFFLINE!")

def main():
    config = load_config()
    init_db(config["db_name"])
    
    # Parse arguments
    simulate = "--simulate" in sys.argv
    if simulate:
        print("🔧 Running in Alert Simulation Mode (spiking resource parameters)...")
        run_checks(config, simulate_spikes=True)
        print("Simulation complete.")
        return
        
    print(f"📡 Automated IT System Monitor started. Logging to {config['db_name']}")
    print(f"Press Ctrl + C to exit the monitor loop.\n")
    
    try:
        while True:
            config = load_config()
            run_checks(config)
            time.sleep(config["check_interval_seconds"])
    except KeyboardInterrupt:
        print("\nStopping IT System Monitor. Goodbye!")

if __name__ == "__main__":
    main()
