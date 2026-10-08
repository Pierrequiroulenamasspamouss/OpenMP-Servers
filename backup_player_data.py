import os
import stat
from pathlib import Path
from dotenv import load_dotenv
import paramiko

def backup_remote_player_data():
    server_dir = Path(__file__).parent.resolve()
    env_path = server_dir / ".env"
    load_dotenv(env_path)

    ssh_host = os.getenv("SSH_HOST", "192.168.1.7")
    ssh_user = os.getenv("SSH_USER", "pierre")
    ssh_password = os.getenv("SSH_PASSWORD", "hacking4fun")
    remote_dir = "/opt/minions/player_data"

    local_backup_dir = server_dir / "prod-backup"
    local_backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to {ssh_user}@{ssh_host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ssh_host, username=ssh_user, password=ssh_password)

    sftp = ssh.open_sftp()
    
    try:
        files = sftp.listdir(remote_dir)
        for file in files:
            remote_filepath = f"{remote_dir}/{file}"
            local_filepath = local_backup_dir / file
            
            # Check if directory or file
            mode = sftp.stat(remote_filepath).st_mode
            if not stat.S_ISDIR(mode):
                print(f"Downloading {file} to {local_filepath}...")
                sftp.get(remote_filepath, str(local_filepath))
    finally:
        sftp.close()
        ssh.close()

    print("Backup completed successfully.")

if __name__ == "__main__":
    backup_remote_player_data()
