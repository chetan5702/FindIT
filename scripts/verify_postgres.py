"""Verify a complete application against an EMPTY disposable PostgreSQL database.

Set FINDIT_TEST_DATABASE_URL in the environment. Never use a campus database.
Creates test records, isolated schemas and private test mail, and starts local servers.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def ready(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("A local verification service did not become ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-disposable-database", action="store_true")
    parser.add_argument(
        "--chrome-channel",
        default=None,
        help="Optional installed browser, e.g. chrome; default uses Playwright Chromium",
    )
    args = parser.parse_args()
    url = os.environ.get("FINDIT_TEST_DATABASE_URL", "")
    if not args.confirm_disposable_database or not url.startswith(
        "postgresql+psycopg://"
    ):
        raise SystemExit(
            "Set FINDIT_TEST_DATABASE_URL and explicitly confirm an empty disposable PostgreSQL database"
        )
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        if inspect(connection).get_table_names(schema="public"):
            raise SystemExit(
                "Refusing a nonempty public schema; create a fresh disposable database"
            )
    engine.dispose()
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js 22+ must be installed")
    run = ROOT / "work" / ("verification-" + uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    api_port, frontend_port = free_port(), free_port()
    env = os.environ.copy()
    env.update(
        FINDIT_DATABASE_URL=url,
        FINDIT_TEST_DATABASE_URL=url,
        FINDIT_ENVIRONMENT="test",
        FINDIT_SECRET_KEY=secrets.token_urlsafe(48),
        FINDIT_COOKIE_SECURE="false",
        FINDIT_MEDIA_ROOT=str(run / "media"),
        FINDIT_REQUIRE_EMAIL_VERIFICATION="true",
        FINDIT_ALLOWED_EMAIL_DOMAINS='["suh.edu.in"]',
        FINDIT_MAIL_BACKEND="file",
        FINDIT_MAIL_DIRECTORY=str(run / "mail"),
        FINDIT_E2E_STAFF_EMAIL="staff@suh.edu.in",
        FINDIT_E2E_STAFF_PASSWORD=secrets.token_urlsafe(32) + "A1",
        FINDIT_PUBLIC_BASE_URL=f"http://127.0.0.1:{frontend_port}",
        VITE_PORT=str(frontend_port),
        VITE_PROXY_TARGET=f"http://127.0.0.1:{api_port}",
        PLAYWRIGHT_BASE_URL=f"http://127.0.0.1:{frontend_port}",
    )
    if args.chrome_channel:
        env["PLAYWRIGHT_CHANNEL"] = args.chrome_channel
    processes, handles, results = [], [], {}

    def command(name, command, cwd):
        with (run / (name + ".log")).open("w") as output:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
        results[name] = result.returncode
        print(f"{name}: " + ("PASS" if result.returncode == 0 else "FAIL"), flush=True)
        if result.returncode:
            raise RuntimeError(
                "Verification failed; inspect the private " + name + ".log"
            )

    def start(name, command, cwd):
        handle = (run / (name + ".log")).open("w")
        handles.append(handle)
        processes.append(
            subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=handle,
                stderr=handle,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        )

    try:
        command(
            "migrations",
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            ROOT / "backend",
        )
        command(
            "schema-check", [sys.executable, "-m", "alembic", "check"], ROOT / "backend"
        )
        command(
            "api",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--basetemp",
                str(run / "pytest"),
                "--tb=short",
            ],
            ROOT / "backend",
        )
        command(
            "frontend-build",
            [node, "node_modules/typescript/bin/tsc", "-b"],
            ROOT / "frontend",
        )
        command(
            "frontend-bundle",
            [node, "node_modules/vite/bin/vite.js", "build"],
            ROOT / "frontend",
        )
        command(
            "frontend-tests",
            [node, "node_modules/vitest/vitest.mjs", "run"],
            ROOT / "frontend",
        )
        command(
            "browser-fixture",
            [sys.executable, "-m", "app.e2e_fixture"],
            ROOT / "backend",
        )
        start(
            "api-server",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            ROOT / "backend",
        )
        ready(f"http://127.0.0.1:{api_port}/api/v1/health")
        start(
            "frontend-server",
            [node, "node_modules/vite/bin/vite.js", "--host", "127.0.0.1"],
            ROOT / "frontend",
        )
        ready(env["PLAYWRIGHT_BASE_URL"])
        command(
            "browsers",
            [
                node,
                "node_modules/@playwright/test/cli.js",
                "test",
                "--workers=1",
                "--reporter=line",
            ],
            ROOT / "frontend",
        )
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        for handle in handles:
            handle.close()
        (run / "results.json").write_text(json.dumps(results, indent=2))
        print("Private logs and result codes: " + str(run))
    print(
        "PostgreSQL migrations, complete API suite, build, unit tests and verified-identity browser workflows passed."
    )


if __name__ == "__main__":
    main()
