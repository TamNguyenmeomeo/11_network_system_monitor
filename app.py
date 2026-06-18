import os
import sys
import json
import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import subprocess

# Config file path relative to this script
CONFIG_FILE = "config.json"
DEFAULT_DB = "monitor_logs.db"

# Language translation mappings
UI_LANG = {
    "EN": {
        "title": "📡 IT Network & System Monitor",
        "subtitle": "Real-time system health and network pinger dashboard",
        "sidebar_config": "⚙️ Configuration Settings",
        "lang_select": "🌐 Language / Ngôn ngữ",
        "theme_select": "🌓 Interface Theme",
        "light": "Light Mode",
        "dark": "Dark Mode",
        "metrics_section": "📊 Live System Resources",
        "cpu_usage": "CPU Usage",
        "cpu_help": "Current processor activity. Lower is better for system speed and temperature.",
        "ram_usage": "RAM Usage",
        "ram_help": "Temporary system memory currently in use. High RAM usage can slow down applications.",
        "disk_usage": "Disk Usage",
        "disk_help": "Total storage space utilized. Keep some free space for system stability.",
        "network_section": "🔌 Network Host Pinger Status",
        "host_name": "Host Name",
        "ip_address": "IP Address",
        "status": "Status",
        "last_checked": "Last Checked",
        "online": "ONLINE",
        "offline": "OFFLINE",
        "history_section": "📈 Resource Utilization History (Last 50 Checks)",
        "settings_section": "🔧 Alert Thresholds & Webhooks",
        "cpu_threshold": "CPU Alert Threshold (%)",
        "ram_threshold": "RAM Alert Threshold (%)",
        "disk_threshold": "Disk Alert Threshold (%)",
        "check_interval": "Check Interval (Seconds)",
        "webhook_url": "Discord Webhook URL",
        "telegram_token": "Telegram Bot Token",
        "telegram_chat_id": "Telegram Chat ID",
        "save_config": "Save Configurations",
        "save_success": "Configurations saved successfully!",
        "add_host": "➕ Add Target Host",
        "new_host_name": "New Host Name",
        "new_host_ip": "New Host IP Address",
        "add_host_btn": "Add Host",
        "add_host_success": "Host added successfully!",
        "delete_host": "🗑️ Remove Target Host",
        "delete_host_btn": "Remove Selected Host",
        "delete_host_success": "Host removed successfully!",
        "simulation": "🛠️ Alert System Simulation",
        "simulate_btn": "Simulate Alert Spikes",
        "sim_success": "Simulation executed successfully!",
        "no_logs": "No logs recorded yet. Start monitor.py to log metrics.",
    },
    "VI": {
        "title": "📡 Bộ giám sát Mạng & Hệ thống IT",
        "subtitle": "Bảng điều khiển hiệu năng và kiểm tra trạng thái kết nối mạng",
        "sidebar_config": "⚙️ Cài đặt & Cấu hình",
        "lang_select": "🌐 Ngôn ngữ / Language",
        "theme_select": "🌓 Giao diện",
        "light": "Sáng (Light)",
        "dark": "Tối (Dark)",
        "metrics_section": "📊 Tài nguyên Hệ thống Hiện tại",
        "cpu_usage": "Tỉ lệ CPU",
        "cpu_help": "Tỷ lệ hoạt động hiện tại của bộ vi xử lý (CPU). Càng thấp máy chạy càng mát và nhanh.",
        "ram_usage": "Dung lượng RAM",
        "ram_help": "Bộ nhớ tạm thời (RAM) đang sử dụng. Cấu hình quá cao có thể gây giật lag ứng dụng.",
        "disk_usage": "Ổ cứng",
        "disk_help": "Dung lượng bộ nhớ lưu trữ đã dùng. Nên giữ trống một phần dung lượng để hệ thống ổn định.",
        "network_section": "🔌 Trạng thái kết nối Máy chủ (Ping)",
        "host_name": "Tên máy chủ",
        "ip_address": "Địa chỉ IP",
        "status": "Trạng thái",
        "last_checked": "Kiểm tra cuối",
        "online": "ONLINE (Hoạt động)",
        "offline": "OFFLINE (Mất kết nối)",
        "history_section": "📈 Biểu đồ lịch sử tài nguyên (50 lần gần nhất)",
        "settings_section": "🔧 Ngưỡng cảnh báo & Webhook",
        "cpu_threshold": "Ngưỡng cảnh báo CPU (%)",
        "ram_threshold": "Ngưỡng cảnh báo RAM (%)",
        "disk_threshold": "Ngưỡng cảnh báo Ổ cứng (%)",
        "check_interval": "Chu kỳ kiểm tra (Giây)",
        "webhook_url": "Đường dẫn Discord Webhook",
        "telegram_token": "Telegram Bot Token",
        "telegram_chat_id": "Telegram Chat ID",
        "save_config": "Lưu cấu hình",
        "save_success": "Cấu hình đã được lưu thành công!",
        "add_host": "➕ Thêm máy chủ giám sát",
        "new_host_name": "Tên máy chủ mới",
        "new_host_ip": "Địa chỉ IP máy chủ",
        "add_host_btn": "Thêm máy chủ",
        "add_host_success": "Đã thêm máy chủ thành công!",
        "delete_host": "🗑️ Xóa máy chủ giám sát",
        "delete_host_btn": "Xóa máy chủ đã chọn",
        "delete_host_success": "Đã xóa máy chủ thành công!",
        "simulation": "🛠️ Giả lập cảnh báo hệ thống",
        "simulate_btn": "Chạy giả lập quá tải (Spikes)",
        "sim_success": "Giả lập đã được gửi thành công!",
        "no_logs": "Chưa có nhật ký nào được ghi nhận. Hãy chạy monitor.py để bắt đầu ghi log.",
    }
}

# Load configuration safely
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {
            "db_name": DEFAULT_DB,
            "check_interval_seconds": 10,
            "cpu_alert_threshold": 90.0,
            "ram_alert_threshold": 90.0,
            "disk_alert_threshold": 90.0,
            "webhook_url": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "hosts_to_ping": [
                {"name": "Local Loopback", "ip": "127.0.0.1"},
                {"name": "Google DNS", "ip": "8.8.8.8"},
                {"name": "Cloudflare DNS", "ip": "1.1.1.1"}
            ]
        }
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# Save configuration back to config.json
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Database querying helpers
def get_metrics_history(db_name, limit=50):
    if not os.path.exists(db_name):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_name)
        df = pd.read_sql_query(
            "SELECT timestamp, cpu_usage, ram_usage, disk_usage FROM system_metrics ORDER BY timestamp DESC LIMIT ?", 
            conn, 
            params=(limit,)
        )
        conn.close()
        return df.iloc[::-1]  # Reverse to keep chronological order
    except Exception:
        return pd.DataFrame()

def get_latest_host_status(db_name):
    if not os.path.exists(db_name):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_name)
        query = """
            SELECT host_name, ip_address, is_online, MAX(timestamp) as last_checked
            FROM host_status
            GROUP BY host_name, ip_address
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def main():
    st.set_page_config(page_title="Network & System Monitor", page_icon="📡", layout="wide")
    
    # Load configuration
    config = load_config()
    db_name = config.get("db_name", DEFAULT_DB)

    # 1. Sidebar Configuration Controls
    st.sidebar.markdown(f"## ⚙️ Configuration")
    
    # Language Selector
    lang_opt = st.sidebar.selectbox("🌐 Language / Ngôn ngữ", ["English", "Tiếng Việt"])
    lang = "EN" if lang_opt == "English" else "VI"
    t = UI_LANG[lang]

    # Theme Selector
    theme_opt = st.sidebar.selectbox(t["theme_select"], [t["light"], t["dark"]])
    theme = "Light" if theme_opt == t["light"] else "Dark"

    # Inject dynamic CSS stylesheet
    if theme == "Dark":
        css = """
        <style>
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
            color: #f8fafc !important;
        }
        section[data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.95) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
        }
        section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p {
            color: #cbd5e1 !important;
        }
        .glass-card {
            background: rgba(30, 41, 59, 0.7) !important;
            border-radius: 16px !important;
            padding: 20px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
            margin-bottom: 20px !important;
        }
        .online-badge {
            background-color: rgba(34, 197, 94, 0.2) !important;
            color: #4ade80 !important;
            border: 1px solid rgba(34, 197, 94, 0.4) !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-weight: bold !important;
            display: inline-block !important;
        }
        .offline-badge {
            background-color: rgba(239, 68, 68, 0.2) !important;
            color: #f87171 !important;
            border: 1px solid rgba(239, 68, 68, 0.4) !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-weight: bold !important;
            display: inline-block !important;
        }
        h1, h2, h3 {
            color: #ffffff !important;
        }
        </style>
        """
    else:
        css = """
        <style>
        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%) !important;
            color: #1e293b !important;
        }
        section[data-testid="stSidebar"] {
            background-color: rgba(241, 245, 249, 0.95) !important;
            border-right: 1px solid rgba(0, 0, 0, 0.05) !important;
        }
        section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p {
            color: #334155 !important;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.7) !important;
            border-radius: 16px !important;
            padding: 20px !important;
            border: 1px solid rgba(0, 0, 0, 0.06) !important;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.05) !important;
            margin-bottom: 20px !important;
        }
        .online-badge {
            background-color: rgba(34, 197, 94, 0.1) !important;
            color: #15803d !important;
            border: 1px solid rgba(34, 197, 94, 0.3) !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-weight: bold !important;
            display: inline-block !important;
        }
        .offline-badge {
            background-color: rgba(239, 68, 68, 0.1) !important;
            color: #b91c1c !important;
            border: 1px solid rgba(239, 68, 68, 0.3) !important;
            border-radius: 6px !important;
            padding: 4px 10px !important;
            font-weight: bold !important;
            display: inline-block !important;
        }
        h1, h2, h3 {
            color: #0f172a !important;
        }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)

    # 2. Main Title Layout
    st.title(t["title"])
    st.markdown(f"*{t['subtitle']}*")
    st.markdown("---")

    # 3. Read Database Logs
    df_metrics = get_metrics_history(db_name)
    df_hosts = get_latest_host_status(db_name)

    # Display error warning if no logs exist
    if df_metrics.empty:
        st.warning(t["no_logs"])
        
        # Still show configuration section so they can set up webhooks
        st.markdown(f"### {t['settings_section']}")
        with st.form("settings_form"):
            cpu_val = st.number_input(t["cpu_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("cpu_alert_threshold", 90.0)))
            ram_val = st.number_input(t["ram_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("ram_alert_threshold", 90.0)))
            disk_val = st.number_input(t["disk_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("disk_alert_threshold", 90.0)))
            interval_val = st.number_input(t["check_interval"], min_value=2, max_value=3600, value=int(config.get("check_interval_seconds", 10)))
            webhook_val = st.text_input(t["webhook_url"], value=config.get("webhook_url", ""))
            tel_token = st.text_input(t["telegram_token"], value=config.get("telegram_bot_token", ""))
            tel_chat = st.text_input(t["telegram_chat_id"], value=config.get("telegram_chat_id", ""))
            
            if st.form_submit_button(t["save_config"]):
                config["cpu_alert_threshold"] = cpu_val
                config["ram_alert_threshold"] = ram_val
                config["disk_alert_threshold"] = disk_val
                config["check_interval_seconds"] = interval_val
                config["webhook_url"] = webhook_val
                config["telegram_bot_token"] = tel_token
                config["telegram_chat_id"] = tel_chat
                save_config(config)
                st.success(t["save_success"])
        return

    # 4. Live Metrics Panel
    st.header(t["metrics_section"])
    latest = df_metrics.iloc[-1]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="glass-card" title="{t['cpu_help']}">
            <h4 style='margin:0; opacity:0.8;'>{t["cpu_usage"]} ℹ️</h4>
            <h1 style='margin:10px 0;'>{latest["cpu_usage"]:.1f}%</h1>
            <p style='margin:0; font-size:0.9em; opacity:0.6;'>Limit: {config["cpu_alert_threshold"]}%</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="glass-card" title="{t['ram_help']}">
            <h4 style='margin:0; opacity:0.8;'>{t["ram_usage"]} ℹ️</h4>
            <h1 style='margin:10px 0;'>{latest["ram_usage"]:.1f}%</h1>
            <p style='margin:0; font-size:0.9em; opacity:0.6;'>Limit: {config["ram_alert_threshold"]}%</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="glass-card" title="{t['disk_help']}">
            <h4 style='margin:0; opacity:0.8;'>{t["disk_usage"]} ℹ️</h4>
            <h1 style='margin:10px 0;'>{latest["disk_usage"]:.1f}%</h1>
            <p style='margin:0; font-size:0.9em; opacity:0.6;'>Limit: {config["disk_alert_threshold"]}%</p>
        </div>
        """, unsafe_allow_html=True)

    # 5. Resource Utilization History Chart
    st.subheader(t["history_section"])
    if not df_metrics.empty:
        chart_data = df_metrics.copy()
        chart_data['Time'] = pd.to_datetime(chart_data['timestamp'])
        
        # Rename columns for prettier legend
        chart_data = chart_data.rename(columns={
            "cpu_usage": "CPU (%)",
            "ram_usage": "RAM (%)",
            "disk_usage": "Disk (%)"
        })
        
        # Melt to long format for Altair
        df_melted = chart_data.melt(
            id_vars=['Time'], 
            value_vars=['CPU (%)', 'RAM (%)', 'Disk (%)'], 
            var_name='Metric', 
            value_name='Usage (%)'
        )
        
        # Build premium Altair chart (without calling .interactive() to prevent dragging/zooming)
        chart = alt.Chart(df_melted).mark_line(
            strokeWidth=2,
            interpolate='monotone'
        ).encode(
            x=alt.X('Time:T', title=None, axis=alt.Axis(
                format='%H:%M:%S',
                labelOverlap='greedy',
                grid=True
            )),
            y=alt.Y('Usage (%):Q', title='Usage (%)', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('Metric:N', scale=alt.Scale(
                domain=['CPU (%)', 'RAM (%)', 'Disk (%)'],
                range=['#3b82f6', '#8b5cf6', '#f59e0b']
            ), legend=alt.Legend(
                orient='bottom',
                title=None,
                labelFontSize=12
            ))
        ).properties(
            height=300
        )
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No metrics history to display.")

    # 6. Network Host Pinger Grid
    st.header(t["network_section"])
    if not df_hosts.empty:
        h_cols = st.columns(min(len(df_hosts), 4))
        for idx, row in df_hosts.iterrows():
            col_target = h_cols[idx % len(h_cols)]
            is_online = bool(row["is_online"])
            badge = f'<div class="online-badge">{t["online"]}</div>' if is_online else f'<div class="offline-badge">{t["offline"]}</div>'
            with col_target:
                st.markdown(f"""
                <div class="glass-card">
                    <h3 style='margin:0 0 5px 0;'>{row["host_name"]}</h3>
                    <code style='font-size:1.1em;'>{row["ip_address"]}</code>
                    <div style='margin-top:15px;'>{badge}</div>
                    <p style='margin:10px 0 0 0; font-size:0.8em; opacity:0.6;'>{t["last_checked"]}: {row["last_checked"]}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No hosts logged yet. Pinger loop might be initializing.")

    # 7. Sidebar Configurations Forms (Collapsible via Expanders)
    st.sidebar.markdown("---")
    
    with st.sidebar.expander(t["settings_section"]):
        with st.form("settings_form_sb"):
            cpu_val = st.number_input(t["cpu_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("cpu_alert_threshold", 90.0)))
            ram_val = st.number_input(t["ram_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("ram_alert_threshold", 90.0)))
            disk_val = st.number_input(t["disk_threshold"], min_value=10.0, max_value=100.0, value=float(config.get("disk_alert_threshold", 90.0)))
            interval_val = st.number_input(t["check_interval"], min_value=2, max_value=3600, value=int(config.get("check_interval_seconds", 10)))
            webhook_val = st.text_input(t["webhook_url"], value=config.get("webhook_url", ""))
            tel_token = st.text_input(t["telegram_token"], value=config.get("telegram_bot_token", ""))
            tel_chat = st.text_input(t["telegram_chat_id"], value=config.get("telegram_chat_id", ""))
            
            if st.form_submit_button(t["save_config"]):
                config["cpu_alert_threshold"] = cpu_val
                config["ram_alert_threshold"] = ram_val
                config["disk_alert_threshold"] = disk_val
                config["check_interval_seconds"] = interval_val
                config["webhook_url"] = webhook_val
                config["telegram_bot_token"] = tel_token
                config["telegram_chat_id"] = tel_chat
                save_config(config)
                st.success(t["save_success"])

    with st.sidebar.expander(t["add_host"]):
        with st.form("add_host_form"):
            h_name = st.text_input(t["new_host_name"])
            h_ip = st.text_input(t["new_host_ip"])
            if st.form_submit_button(t["add_host_btn"]):
                if h_name and h_ip:
                    config["hosts_to_ping"].append({"name": h_name, "ip": h_ip})
                    save_config(config)
                    st.success(t["add_host_success"])
                    st.rerun()

    if config["hosts_to_ping"]:
        with st.sidebar.expander(t["delete_host"]):
            with st.form("delete_host_form"):
                host_options = [f"{h['name']} ({h['ip']})" for h in config["hosts_to_ping"]]
                selected_host_str = st.selectbox(t["delete_host"], options=host_options)
                if st.form_submit_button(t["delete_host_btn"]):
                    idx_to_remove = host_options.index(selected_host_str)
                    config["hosts_to_ping"].pop(idx_to_remove)
                    save_config(config)
                    st.success(t["delete_host_success"])
                    st.rerun()

    with st.sidebar.expander(t["simulation"]):
        if st.button(t["simulate_btn"]):
            # Run monitor.py in --simulate mode in background
            subprocess.Popen([sys.executable, "monitor.py", "--simulate"])
            st.success(t["sim_success"])

if __name__ == "__main__":
    main()
