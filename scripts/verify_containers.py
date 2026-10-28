"""Build and verify the production Compose stack with synthetic identity/mail and HTTPS.

Requires Linux Docker Compose >=2.24.4, OpenSSL, Node 22+, npm ci and Playwright Chromium.
Creates unique Compose projects and removes only their disposable containers/volumes.
No public email is sent; no real campus settings or data are used.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-containers", action="store_true")
    args = parser.parse_args()
    if os.name == "nt":
        raise SystemExit(
            "Run production-container verification on a Linux Docker host (or the supplied CI job)"
        )
    folder = ROOT / "work/container-verification"
    folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    mail = folder / "mail"
    mail.mkdir(mode=0o700)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    project = "findit-verify-" + uuid.uuid4().hex[:12]
    restore_project = project + "-restore"
    secret = secrets.token_urlsafe(36)
    database_password = secrets.token_urlsafe(36)
    origin = f"https://localhost:{port}"
    values = {
        "POSTGRES_DB": "findit_verification",
        "POSTGRES_USER": "findit_verification",
        "POSTGRES_PASSWORD": database_password,
        "FINDIT_DATABASE_URL": f"postgresql+psycopg://findit_verification:{database_password}@db:5432/findit_verification",
        "FINDIT_SECRET_KEY": secret,
        "FINDIT_DOMAIN": "localhost",
        "FINDIT_PUBLIC_BASE_URL": origin,
        "FINDIT_ALLOWED_ORIGINS": json.dumps([origin]),
        "FINDIT_TRUSTED_HOSTS": '["localhost"]',
        "FINDIT_ALLOWED_EMAIL_DOMAINS": '["suh.edu.in"]',
        "FINDIT_REQUIRE_EMAIL_VERIFICATION": "true",
        "FINDIT_MAIL_FROM": "FindIt <noreply@suh.edu.in>",
        "FINDIT_SMTP_HOST": "test-smtp",
        "FINDIT_SMTP_PORT": "1025",
        "FINDIT_SMTP_SECURITY": "starttls",
        "FINDIT_E2E_STAFF_EMAIL": "staff@suh.edu.in",
        "FINDIT_E2E_STAFF_PASSWORD": secrets.token_urlsafe(24) + "A1",
        "FINDIT_TEST_HTTPS_PORT": str(port),
        "FINDIT_TEST_UID": str(os.getuid()),
        "FINDIT_TEST_GID": str(os.getgid()),
    }
    env_file = folder / "stack.env"
    env_file.write_text(
        "\n".join(f"{key}='{value}'" for key, value in values.items()) + "\n"
    )
    env_file.chmod(0o600)
    env = os.environ.copy()
    env.update(values)
    env.update(
        PLAYWRIGHT_BASE_URL=origin,
        PLAYWRIGHT_IGNORE_HTTPS_ERRORS="true",
        FINDIT_MAIL_DIRECTORY=str(mail),
    )
    cert = folder / "test-cert.crt"
    key = folder / "test-key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,DNS:test-smtp",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cert.chmod(0o644)
    key.chmod(0o600)
    caddy = (
        (ROOT / "deploy/Caddyfile")
        .read_text()
        .replace(
            "    encode zstd gzip",
            "    tls /test-cert.crt /test-key.pem\n    encode zstd gzip",
        )
    )
    (folder / "Caddyfile").write_text(
        "{\n admin off\n auto_https disable_redirects\n}\n" + caddy
    )

    def compose(project_name, *command, overlay=True, **kwargs):
        base = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-p",
            project_name,
            "-f",
            str(ROOT / "docker-compose.prod.yml"),
        ]
        if overlay:
            base += ["-f", str(ROOT / "docker-compose.verify.yml")]
        return subprocess.run(
            [*base, *command], cwd=ROOT, env=env, check=True, **kwargs
        )

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=str(cert))
        ),
    )
    results = {}
    try:
        compose(project, "config", "--quiet")
        compose(project, "up", "-d", "--build")
        for _ in range(120):
            try:
                with opener.open(origin + "/api/v1/health", timeout=3) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError("Production topology did not become ready")
        compose(
            project,
            "exec",
            "-T",
            "backend",
            "python",
            "-m",
            "app.cli",
            "check-deployment",
        )
        compose(
            project,
            "exec",
            "-T",
            "-e",
            "FINDIT_ENVIRONMENT=test",
            "backend",
            "python",
            "-m",
            "app.e2e_fixture",
        )
        with opener.open(origin + "/api/v1/auth/csrf") as response:
            assert "Secure" in response.headers.get("Set-Cookie", "")
            assert response.headers.get("Strict-Transport-Security")
        with opener.open(origin + "/") as response:
            assert "default-src" in response.headers.get("Content-Security-Policy", "")
        node = shutil.which("node")
        subprocess.run(
            [node, "node_modules/@playwright/test/cli.js", "test", "--workers=1"],
            cwd=ROOT / "frontend",
            env=env,
            check=True,
        )
        results["production-topology-https-smtp-browser-workflows"] = "passed"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/backup_restore.py"),
                "--env-file",
                str(env_file),
                "--project-name",
                project,
                "backup",
                str(folder / "backup"),
                "--maintenance-window",
            ],
            check=True,
        )
        compose(restore_project, "up", "-d", "db", overlay=False)
        for _ in range(30):
            try:
                compose(
                    restore_project,
                    "exec",
                    "-T",
                    "db",
                    "pg_isready",
                    "-U",
                    values["POSTGRES_USER"],
                    "-d",
                    values["POSTGRES_DB"],
                    overlay=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                break
            except subprocess.CalledProcessError:
                time.sleep(2)
        compose(restore_project, "build", "backend", overlay=False)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/backup_restore.py"),
                "--env-file",
                str(env_file),
                "--project-name",
                restore_project,
                "restore",
                str(folder / "backup"),
                "--confirm-empty-target",
            ],
            check=True,
        )
        results["consistent-docker-backup-and-empty-target-restore"] = "passed"
    finally:
        (folder / "results.json").write_text(json.dumps(results, indent=2))
        if not args.keep_containers:
            # Names are generated here; this cannot target a user's production project.
            assert project.startswith("findit-verify-") and restore_project.startswith(
                project
            )
            for name in (restore_project, project):
                try:
                    compose(
                        name,
                        "down",
                        "--volumes",
                        "--remove-orphans",
                        overlay=(name == project),
                    )
                except subprocess.CalledProcessError:
                    pass
    print(
        "Production container verification passed. Synthetic logs and backup remain private under work/container-verification."
    )


if __name__ == "__main__":
    main()
