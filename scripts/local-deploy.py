import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs" / "local-deploy"


SERVICES = {
    "Multi-Agent": {
        "script": "ai-services/multi-agent-server/app.py",
        "port": 5013,
        "env": {"MULTI_AGENT_HOST": "0.0.0.0"},
    },
    "Agentic Loop": {
        "script": "ai-services/agentic-loop/app.py",
        "port": 5012,
        "env": {},
    },
    "MCP": {
        "script": "ai-services/mcp-server/server.py",
        "port": 8011,
        "env": {},
    },
    "RAG": {
        "script": "ai-services/rag-server/server.py",
        "port": 8012,
        "env": {},
    },
}


processes = []
log_files = []


def port_open(port, host="127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def http_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def start_process(name, command, environment=None):
    log_path = LOG_DIR / f"{name.lower().replace(' ', '-')}.log"
    log_file = open(log_path, "a", encoding="utf-8")
    log_files.append(log_file)

    env = os.environ.copy()
    env.update(environment or {})

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    processes.append((name, process))
    print(f"[STARTED] {name} (PID {process.pid})")


def start_ollama():
    if port_open(11434):
        print("[OK] Ollama already running")
        return

    executable = shutil.which("ollama")

    if not executable:
        print("[WARNING] Ollama not found in PATH")
        print("Start Ollama manually before testing AI features.")
        return

    print("[STARTING] Ollama")
    start_process("Ollama", [executable, "serve"])


def start_python_services():
    for name, config in SERVICES.items():
        port = config["port"]
        script = ROOT / config["script"]

        if port_open(port):
            print(f"[OK] {name} already listening on port {port}")
            continue

        if not script.is_file():
            print(f"[ERROR] Missing {name} script: {script}")
            continue

        print(f"[STARTING] {name}")
        start_process(
            name,
            [sys.executable, str(script)],
            config["env"],
        )


def start_docker():
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI not found")

    print("[STARTING] Docker Compose")
    subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        cwd=ROOT,
        check=True,
    )

    subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=ROOT,
        check=True,
    )

    print("[OK] Docker Compose command completed")


def show_status():
    print("\n--- Local service status ---")

    checks = [
        ("Ollama", 11434),
        ("Multi-Agent", 5013),
        ("Agentic Loop", 5012),
        ("MCP", 8011),
        ("RAG", 8012),
        ("Assessment backend", 5007),
        ("Assessment database", 5008),
        ("Authentication backend", 5011),
        ("Portal", 8000),
    ]

    for name, port in checks:
        status = "OK" if port_open(port) else "NOT LISTENING"
        print(f"{name:<24} {port:<6} {status}")

    portal = "http://localhost:8000"
    multi_agent = f"{portal}/multi-agent-api/health"

    print(f"\nPortal: {portal}")
    print(f"Multi-Agent: {portal}/multi-agent.html")

    if http_ok(multi_agent):
        print("[OK] Multi-Agent proxy health check")
    else:
        print("[WARNING] Multi-Agent proxy health check failed")

    print(f"\nService logs: {LOG_DIR}")



def stop_services():
    print("\nShutting down local deployment...")

    # Stop local Python services
    for name, process in reversed(processes):
        if process.poll() is None:
            print(f"[STOPPING] {name}")
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    # Stop Docker containers
    print("[STOPPING] Docker Compose")

    try:
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=ROOT,
            check=True,
            timeout=60,
        )
        print("[OK] Docker containers stopped")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        print(f"[WARNING] Docker shutdown failed: {error}")

    # Close log files
    for log_file in log_files:
        log_file.close()

    print("[OK] Local deployment shutdown complete")


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("ASD RELEASE 2 - LOCAL DEPLOYMENT")
    print("=" * 50)

    try:
        start_ollama()
        start_python_services()
        start_docker()

        # Give the services a short opportunity to initialise.
        time.sleep(3)
        show_status()

        print("\nPress Ctrl+C to stop launcher-managed services.")

        while True:
            for name, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{name} exited unexpectedly. "
                        f"Check logs in {LOG_DIR}"
                    )
            time.sleep(2)

    except KeyboardInterrupt:
        pass
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\n[ERROR] {error}")
    finally:
        stop_services()


if __name__ == "__main__":
    main()
