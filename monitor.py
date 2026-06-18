import os
import sys
import time
import json
import sqlite3
import subprocess
import psutil
import requests
import threading

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

# Configuration Lock for thread safety
config_lock = threading.Lock()

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def send_telegram_msg(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def handle_telegram_command(token, chat_id, text):
    parts = text.split()
    if not parts:
        return
    cmd = parts[0].lower()
    
    if cmd in ["/start", "/help"]:
        help_text = (
            "📡 *IT System Monitor Bot* 🤖\n\n"
            "Danh sách lệnh hỗ trợ:\n"
            "• `/status` - Kiểm tra hiệu năng tài nguyên (CPU/RAM/Disk).\n"
            "• `/ping` - Kiểm tra trạng thái các máy chủ đang giám sát.\n"
            "• `/addhost <tên> <ip>` - Thêm máy chủ mới cần ping.\n"
            "• `/removehost <ip>` - Xóa máy chủ khỏi danh sách.\n"
            "• `/setthreshold <cpu|ram|disk> <giá_trị>` - Điều chỉnh ngưỡng cảnh báo (ví dụ: `/setthreshold cpu 95`)."
        )
        send_telegram_msg(token, chat_id, help_text)
        
    elif cmd == "/status":
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('C:\\' if sys.platform.lower().startswith("win") else '/').percent
        
        with config_lock:
            config = load_config()
            
        status_msg = (
            "🖥️ *Trạng thái Hệ thống hiện tại:*\n"
            f"• **CPU Usage:** `{cpu}%` (Ngưỡng: {config['cpu_alert_threshold']}%)\n"
            f"• **RAM Usage:** `{ram}%` (Ngưỡng: {config['ram_alert_threshold']}%)\n"
            f"• **Disk Usage:** `{disk}%` (Ngưỡng: {config['disk_alert_threshold']}%)\n\n"
            "📊 Trạng thái: " + ("🟢 Khỏe mạnh" if (cpu <= config['cpu_alert_threshold'] and ram <= config['ram_alert_threshold']) else "🔴 Tải cao / Đáng báo động!")
        )
        send_telegram_msg(token, chat_id, status_msg)
        
    elif cmd == "/ping":
        with config_lock:
            config = load_config()
        send_telegram_msg(token, chat_id, "⏳ Đang ping kiểm tra các máy chủ, vui lòng đợi...")
        results = []
        for host in config.get("hosts_to_ping", []):
            is_online = ping_host(host["ip"])
            status_str = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
            results.append(f"• **{host['name']}** ({host['ip']}): {status_str}")
        send_telegram_msg(token, chat_id, "📡 *Trạng thái kết nối mạng:*\n" + "\n".join(results))
        
    elif cmd == "/addhost":
        if len(parts) < 3:
            send_telegram_msg(token, chat_id, "⚠️ Cú pháp: `/addhost <tên> <ip>`\nVí dụ: `/addhost Router 192.168.1.1`")
            return
        name = parts[1]
        ip = parts[2]
        with config_lock:
            config = load_config()
            config["hosts_to_ping"].append({"name": name, "ip": ip})
            save_config(config)
        send_telegram_msg(token, chat_id, f"✅ Đã thêm máy chủ **{name}** ({ip}) vào danh sách giám sát.")
        
    elif cmd == "/removehost":
        if len(parts) < 2:
            send_telegram_msg(token, chat_id, "⚠️ Cú pháp: `/removehost <ip>`\nVí dụ: `/removehost 192.168.1.1`")
            return
        ip = parts[1]
        removed = False
        with config_lock:
            config = load_config()
            new_hosts = []
            for host in config.get("hosts_to_ping", []):
                if host["ip"] == ip:
                    removed = True
                else:
                    new_hosts.append(host)
            config["hosts_to_ping"] = new_hosts
            save_config(config)
        if removed:
            send_telegram_msg(token, chat_id, f"✅ Đã xóa máy chủ có IP **{ip}**.")
        else:
            send_telegram_msg(token, chat_id, f"❌ Không tìm thấy máy chủ nào có IP **{ip}**.")
            
    elif cmd == "/setthreshold":
        if len(parts) < 3:
            send_telegram_msg(token, chat_id, "⚠️ Cú pháp: `/setthreshold <cpu|ram|disk> <giá_trị>`\nVí dụ: `/setthreshold cpu 85`")
            return
        metric = parts[1].lower()
        try:
            val = float(parts[2])
        except ValueError:
            send_telegram_msg(token, chat_id, "❌ Giá trị ngưỡng không hợp lệ (phải là số).")
            return
            
        with config_lock:
            config = load_config()
            if metric == "cpu":
                config["cpu_alert_threshold"] = val
            elif metric == "ram":
                config["ram_alert_threshold"] = val
            elif metric == "disk":
                config["disk_alert_threshold"] = val
            else:
                send_telegram_msg(token, chat_id, "❌ Loại tài nguyên không hợp lệ. Chọn: cpu, ram hoặc disk.")
                return
            save_config(config)
        send_telegram_msg(token, chat_id, f"✅ Đã cập nhật ngưỡng cảnh báo của **{metric.upper()}** thành `{val}%`.")
    else:
        send_telegram_msg(token, chat_id, "❓ Lệnh không hợp lệ. Gõ `/help` để xem danh sách lệnh.")

def telegram_bot_listener():
    offset = None
    print("🤖 [Telegram Bot] Outgoing Command Listener thread running...")
    
    while True:
        with config_lock:
            config = load_config()
        token = config.get("telegram_bot_token")
        allowed_chat_id = config.get("telegram_chat_id")
        
        if not token:
            time.sleep(5)
            continue
            
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset
            
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "")
                        
                        if not text or not chat_id:
                            continue
                        
                        # Authorize the sender if chat ID is configured
                        if allowed_chat_id and str(chat_id) != str(allowed_chat_id):
                            print(f"Ignored unauthorized message from Chat ID {chat_id}")
                            send_telegram_msg(token, chat_id, "❌ Bạn không có quyền truy cập hệ thống giám sát này.")
                            continue
                            
                        handle_telegram_command(token, chat_id, text)
        except Exception as e:
            pass
            
        time.sleep(1)

def main():
    with config_lock:
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
    
    # Start background Telegram interactive listener thread
    t = threading.Thread(target=telegram_bot_listener, daemon=True)
    t.start()
    
    print(f"Press Ctrl + C to exit the monitor loop.\n")
    
    try:
        while True:
            with config_lock:
                config = load_config()
            run_checks(config)
            time.sleep(config["check_interval_seconds"])
    except KeyboardInterrupt:
        print("\nStopping IT System Monitor. Goodbye!")

if __name__ == "__main__":
    main()
