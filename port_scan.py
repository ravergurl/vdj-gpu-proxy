import asyncio
import socket

TARGET = "192.168.1.104"
PORT_RANGE = range(1, 65535)
TIMEOUT = 0.5


async def check_port(ip, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
        return port
    except:
        return None


async def scan():
    print(f"Scanning {TARGET} ports 1-65535...")
    tasks = []
    semaphore = asyncio.Semaphore(500)

    async def sem_scan(port):
        async with semaphore:
            result = await check_port(TARGET, port)
            if result:
                print(f"[+] PORT {result} OPEN")
                return result
            return None

    for port in PORT_RANGE:
        tasks.append(sem_scan(port))

    results = await asyncio.gather(*tasks)
    open_ports = [p for p in results if p]

    print(f"\nScan complete. Open ports: {open_ports}")
    return open_ports


if __name__ == "__main__":
    asyncio.run(scan())
