import psutil
import os
import time
import subprocess
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CPU_THRESHOLD = 80
MEMORY_THRESHOLD = 7 * 1024 * 1024  # 7 MB
LOG_FILE = "system_monitor.log"
WINDOWS_DIRS_TO_SCAN = [
    '/mnt/c/Users/pc/Downloads/demo',  # Demo folder
]

# Email config
SENDER_EMAIL = "devansh7895@gmail.com"
SENDER_PASSWORD = "your_app_specific_password"  # REPLACE with app password
RECEIVER_EMAIL = "beforelyf07@gmail.com"

event_log = []  # For collecting important actions

def log(message):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a") as f:
        f.write(full_message + "\n")

def log_event(message):
    event_log.append(message)
    log(message)

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def check_storage_linux():
    usage = psutil.disk_usage('/')
    used = usage.used / (1024 ** 3)
    free = usage.free / (1024 ** 3)
    total = usage.total / (1024 ** 3)
    log(f"Linux Disk: {used:.2f} GB / {total:.2f} GB Free: {free:.2f} GB")

def get_windows_storage_info():
    try:
        cmd = [
            "powershell.exe",
            "-Command",
            "Get-PSDrive C | Select-Object Used,Free,DisplayRoot"
        ]
        result = subprocess.check_output(cmd, shell=False).decode("utf-8", errors="ignore").strip()
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        if len(lines) >= 3:
            values = lines[2].split()
            used_gb = int(values[0]) / (1024 ** 3)
            free_gb = int(values[1]) / (1024 ** 3)
            log(f"Windows C: Used: {used_gb:.2f} GB | Free: {free_gb:.2f} GB")
        else:
            log("Could not parse Windows storage info.")
    except Exception as e:
        log(f"Windows disk check failed: {e}")

def check_large_files():
    for path in WINDOWS_DIRS_TO_SCAN:
        log(f"Scanning: {path}")
        found = False
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    if os.path.islink(file_path): continue
                    size = os.path.getsize(file_path)
                    if size > MEMORY_THRESHOLD:
                        last_used = time.ctime(os.path.getatime(file_path))
                        size_mb = size / (1024 ** 2)
                        log_event(f"Large File: {file_path} | {size_mb:.2f} MB | Last Accessed: {last_used}")
                        os.remove(file_path)
                        log_event(f"File {file} has been removed.")
                        found = True
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        if not found:
            log("No large files over 7 MB.")

def check_memory():
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    log(f"RAM Usage: {used_gb:.2f} GB / {total_gb:.2f} GB")

def check_high_cpu():
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            if proc.info['cpu_percent'] > CPU_THRESHOLD:
                log_event(f"High CPU: {proc.info['name']} (PID {proc.info['pid']}) - {proc.info['cpu_percent']}%")
                proc.terminate()
                log_event("Terminated high CPU process.")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def list_processes():
    log("\nProcess List:")
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            cpu = proc.info['cpu_percent']
            log(f"{proc.info['name']} (PID {proc.info['pid']}) - {cpu}% CPU")
        except:
            continue

def get_active_window():
    try:
        ps_script = r"""
        Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public class Win32 {
            [DllImport("user32.dll")]
            public static extern IntPtr GetForegroundWindow();
            [DllImport("user32.dll")]
            public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);
        }
"@;
        $hwnd = [Win32]::GetForegroundWindow()
        [int]$id = 0
        [Win32]::GetWindowThreadProcessId($hwnd, [ref]$id) | Out-Null
        $proc = Get-Process -Id $id
        "Active App: $($proc.ProcessName) | Title: $($proc.MainWindowTitle)"
        """
        result = subprocess.check_output(["powershell.exe", "-Command", ps_script], shell=False)
        log(result.decode("utf-8", errors="ignore").strip())
    except Exception as e:
        log(f"Active app detection failed: {e}")

def monitor():
    log("Launching Self-Heal Kernel Monitor (WSL2)...")
    while True:
        global event_log
        event_log = []

        log("\nSystem Check:")
        check_storage_linux()
        get_windows_storage_info()
        check_large_files()
        check_memory()
        get_active_window()
        check_high_cpu()
        list_processes()
        log("\nEnd of Check\n")

        if event_log:
            body = "\n".join(event_log)
            send_email("System Activity Alert", body)
        else:
            send_email("System OK", "No abnormal activity detected. System is running normally.")

        time.sleep(3600)  # Repeat every hour

if __name__ == "__main__":
    monitor()