import time
import logging
from logging.handlers import RotatingFileHandler
import paramiko

# Remote Kali SSH Configuration
REMOTE_HOST = "192.168.26.192"
REMOTE_PORT = 22
REMOTE_USER = "root"             
REMOTE_PASS = "your_password"

# Paths on the remote Kali system
REMOTE_TXT_PATH = "/root/Downloads/NAV_TEST.txt"
REMOTE_DB_PATH = "/root/Downloads/nav.db"

# --- LOGGING SETUP ---
# Configure logger to write to 'monitor.log'
# maxBytes=5*1024*1024 (5 MB per file), backupCount=3 (keeps last 3 old log files)
log_handler = RotatingFileHandler("monitor.log", maxBytes=5*1024*1024, backupCount=3)
log_formatter = logging.Formatter('%(message)s')
log_handler.setFormatter(log_formatter)

logger = logging.getLogger("MonitorLogger")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

def log_and_print(message=""):
    """Helper function to print to terminal AND write to the rolling log file simultaneously."""
    print(message)
    logger.info(message)

def get_remote_records(ssh_client, unique_id, name):
    """Queries the remote SQLite database and returns all matching rows as a list of tuples."""
    try:
        safe_id = unique_id.replace("'", "''")
        safe_name = name.replace("'", "''")
        
        query = f"sqlite3 -separator '|' {REMOTE_DB_PATH} \"SELECT anu, name, event_reference, StartDate, created_at FROM NAV_ADV_EVENT WHERE event_reference = '{safe_id}' AND name = '{safe_name}';\""
        
        stdin, stdout, stderr = ssh_client.exec_command(query)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            return []
            
        if not output:
            return []
            
        rows = output.split('\n')
        parsed_rows = []
        for row in rows:
            parts = row.split('|')
            if len(parts) == 5:
                parsed_rows.append(parts)
        return parsed_rows
    except Exception as e:
        return []

def fetch_remote_file(sftp_client):
    """Reads the contents of the remote text file via SFTP."""
    try:
        with sftp_client.open(REMOTE_TXT_PATH, 'r') as f:
            lines = f.readlines()
        return [line.strip() for line in lines]
    except Exception as e:
        return None

def run_comparison_cycle(ssh, sftp):
    """Fetches the file, grabs the last 10 data rows, compares them, and logs/prints the output."""
    lines = fetch_remote_file(sftp)
    if not lines:
        log_and_print("Could not retrieve remote file contents.")
        return

    data_lines = [line for line in lines if line and not line.startswith("#")]
    last_10_rows = data_lines[-10:] if len(data_lines) >= 10 else data_lines

    # Build output block
    output_block = []
    output_block.append("\n" + "=" * 95)
    output_block.append(f"Comparison Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    output_block.append("-" * 95)
    output_block.append(f"{'Anu':<6} | {'Name':<10} | {'Event Ref (ID)':<15} | {'Start Date':<12} | {'Created At':<20} | {'Status':<10}")
    output_block.append("-" * 95)

    for line in last_10_rows:
        parts = line.split()
        if len(parts) >= 2:
            unique_id = parts[0].strip()
            name = parts[1].strip()
            
            matched_records = get_remote_records(ssh, unique_id, name)
            
            if matched_records:
                for record in matched_records:
                    anu, db_name, ref, start_date, created_at = record
                    output_block.append(f"{anu:<6} | {db_name:<10} | {ref:<15} | {start_date:<12} | {created_at:<20} | {'Found':<10}")
            else:
                output_block.append(f"{'N/A':<6} | {name:<10} | {unique_id:<15} | {'N/A':<12} | {'N/A':<20} | {'Not Found':<10}")
        else:
            output_block.append(f"Skipping malformed row: {line}")
            
    output_block.append("=" * 95)
    
    # Print all lines simultaneously to terminal and log file
    for block_line in output_block:
        log_and_print(block_line)

def main():
    log_and_print(f"Connecting to remote Kali system at {REMOTE_HOST}...")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=REMOTE_USER, password=REMOTE_PASS)
        sftp = ssh.open_sftp()
    except Exception as e:
        log_and_print(f"Connection failed: {e}")
        return

    log_and_print(f"Successfully connected! Checking the last 10 rows every 5 minutes...")

    try:
        while True:
            run_comparison_cycle(ssh, sftp)
            time.sleep(300)  # Wait 5 minutes
            
    except KeyboardInterrupt:
        log_and_print("\nMonitoring stopped by user.")
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()