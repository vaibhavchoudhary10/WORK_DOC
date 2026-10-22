import time
import paramiko

# Remote Kali SSH Configuration
REMOTE_HOST = "192.168.26.192"  # Your Kali VM IP address
REMOTE_PORT = 22
REMOTE_USER = "root"             
REMOTE_PASS = "your_password"    # Replace with your root password

# Paths on the remote Kali system
REMOTE_TXT_PATH = "/root/Downloads/NAV_TEST.txt"
REMOTE_DB_PATH = "/root/Downloads/nav.db"

def get_remote_records(ssh_client, unique_id, name):
    """Queries the remote SQLite database and returns all matching rows as a list of tuples."""
    try:
        safe_id = unique_id.replace("'", "''")
        safe_name = name.replace("'", "''")
        
        # Query to fetch multiple columns; outputs pipe-delimited rows if multiple matches exist
        query = f"sqlite3 -separator '|' {REMOTE_DB_PATH} \"SELECT anu, name, event_reference, StartDate, created_at FROM NAV_ADV_EVENT WHERE event_reference = '{safe_id}' AND name = '{safe_name}';\""
        
        stdin, stdout, stderr = ssh_client.exec_command(query)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        if error:
            print(f"Remote DB Error: {error}")
            return []
            
        if not output:
            return []
            
        # Split multiple lines if more than one row matches
        rows = output.split('\n')
        parsed_rows = []
        for row in rows:
            parts = row.split('|')
            if len(parts) == 5:
                parsed_rows.append(parts)
        return parsed_rows
    except Exception as e:
        print(f"SSH execution error: {e}")
        return []

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
    """Fetches the file, grabs the last 10 data rows, fetches all matching DB records, and prints them."""
    lines = fetch_remote_file(sftp)
    if not lines:
        print("Could not retrieve remote file contents.")
        return

    # Filter out header/comment lines (starting with #) and empty lines
    data_lines = [line for line in lines if line and not line.startswith("#")]
    
    # Get only the last 10 rows (changed from 4 to 10)
    last_10_rows = data_lines[-10:] if len(data_lines) >= 10 else data_lines

    print("\n" + "=" * 95)
    print(f"Comparison Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 95)
    print(f"{'Anu':<6} | {'Name':<10} | {'Event Ref (ID)':<15} | {'Start Date':<12} | {'Created At':<20} | {'Status':<10}")
    print("-" * 95)

    for line in last_10_rows:
        parts = line.split()
        if len(parts) >= 2:
            unique_id = parts[0].strip()
            name = parts[1].strip()
            
            # Query remote DB for all matching records
            matched_records = get_remote_records(ssh, unique_id, name)
            
            if matched_records:
                # If multiple records (different anus) match, print every single one
                for record in matched_records:
                    anu, db_name, ref, start_date, created_at = record
                    print(f"{anu:<6} | {db_name:<10} | {ref:<15} | {start_date:<12} | {created_at:<20} | {'Found':<10}")
            else:
                # If no match found, output N/A placeholders with 'Not Found' status
                print(f"{'N/A':<6} | {name:<10} | {unique_id:<15} | {'N/A':<12} | {'N/A':<20} | {'Not Found':<10}")
        else:
            print(f"Skipping malformed row: {line}")
    print("=" * 95)

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

    print(f"Successfully connected! Checking the last 10 rows every 5 minutes...")

    try:
        while True:
            run_comparison_cycle(ssh, sftp)
            time.sleep(300)  # Wait 5 minutes
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()