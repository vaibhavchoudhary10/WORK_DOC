import time
import paramiko

# Remote Kali SSH Configuration
REMOTE_HOST = "192.168.26.192"  # Your Kali VM IP address
REMOTE_PORT = 22
REMOTE_USER = "root"             
REMOTE_PASS = "Andr0med@"    # Replace with your root password

# Paths on the remote Kali system
REMOTE_TXT_PATH = "/root/Downloads/NAV_TEST.txt"
REMOTE_DB_PATH = "/root/Downloads/nav.db"  # Path to nav.db on remote Kali

def get_remote_anu(ssh_client, unique_id, name):
    """Queries the remote SQLite database and returns the 'anu' column if found."""
    try:
        safe_id = unique_id.replace("'", "''")
        safe_name = name.replace("'", "''")
        
        # Query to fetch the 'anu' primary key instead of just '1'
        query = f"sqlite3 {REMOTE_DB_PATH} \"SELECT anu FROM NAV_ADV_EVENT WHERE event_reference = '{safe_id}' AND name = '{safe_name}';\""
        
        stdin, stdout, stderr = ssh_client.exec_command(query)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            print(f"Remote DB Error: {error}")
            return None
            
        return output if output else None
    except Exception as e:
        print(f"SSH execution error: {e}")
        return None

def fetch_remote_file(sftp_client):
    """Reads the contents of the remote text file via SFTP."""
    try:
        with sftp_client.open(REMOTE_TXT_PATH, 'r') as f:
            lines = f.readlines()
        return [line.strip() for line in lines]
    except Exception as e:
        print(f"SFTP read error: {e}")
        return None

def run_comparison_cycle(ssh, sftp):
    """Fetches the file, grabs the last 4 data rows, fetches 'anu', and prints the table."""
    lines = fetch_remote_file(sftp)
    if not lines:
        print("Could not retrieve remote file contents.")
        return

    # Filter out header/comment lines (starting with #) and empty lines
    data_lines = [line for line in lines if line and not line.startswith("#")]
    
    # Get only the last 4 rows
    last_4_rows = data_lines[-4:] if len(data_lines) >= 4 else data_lines

    print("\n" + "=" * 65)
    print(f"Comparison Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 65)
    print(f"{'Anu (DB ID)':<15} | {'Name':<15} | {'Status':<15}")
    print("-" * 65)

    for line in last_4_rows:
        parts = line.split()
        if len(parts) >= 2:
            unique_id = parts[0].strip()
            name = parts[1].strip()
            
            # Query the remote database for the corresponding 'anu' value
            anu_value = get_remote_anu(ssh, unique_id, name)
            
            if anu_value:
                status = "Found"
                display_anu = anu_value
            else:
                status = "Not Found"
                display_anu = "N/A"
            
            print(f"{display_anu:<15} | {name:<15} | {status:<15}")
        else:
            print(f"Skipping malformed row: {line}")
    print("=" * 65)

def main():
    print(f"Connecting to remote Kali system at {REMOTE_HOST}...")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=REMOTE_USER, password=REMOTE_PASS)
        sftp = ssh.open_sftp()
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    print(f"Successfully connected! Checking the last 4 rows every 5 minutes...")

    try:
        while True:
            # Run comparison immediately, then repeat every 5 minutes (300 seconds)
            run_comparison_cycle(ssh, sftp)
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()