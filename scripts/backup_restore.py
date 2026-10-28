"""Consistent maintenance-window backups and non-destructive empty-target restores.

Run from a deployment host with Docker Compose. Never prints interpolated configuration.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from datetime import UTC, datetime

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def compose(args, *command, **kwargs):
    process = [
        "docker",
        "compose",
        "--env-file",
        str(Path(args.env_file).resolve()),
        "-f",
        str(ROOT / "docker-compose.prod.yml"),
    ]
    if getattr(args, "project_name", None):
        process.extend(["--project-name", args.project_name])
    process.extend(command)
    return subprocess.run(process, cwd=ROOT, check=True, **kwargs)


def scalar(args, sql):
    # Static SQL only. Credentials stay inside the database container.
    result = compose(
        args,
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"',
        "sh",
        sql,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def backup(args):
    target = Path(args.directory).resolve()
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    running = compose(
        args, "ps", "--status", "running", "--services", capture_output=True, text=True
    ).stdout.splitlines()
    if "backend" not in running:
        raise ValueError(
            "Backup requires a running backend so maintenance restart behavior is explicit"
        )
    if not args.maintenance_window:
        raise ValueError(
            "Pass --maintenance-window to authorize temporary API downtime"
        )
    compose(args, "stop", "backend", stdout=subprocess.DEVNULL)
    try:
        with (target / "database.dump").open("wb") as output:
            compose(
                args,
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
                stdout=output,
            )
        with (target / "media.tar.gz").open("wb") as output:
            compose(
                args,
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "tar",
                "backend",
                "-czf",
                "-",
                "-C",
                "/data/media",
                ".",
                stdout=output,
            )
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "schema": scalar(args, "SELECT version_num FROM alembic_version"),
            "files": {
                name: digest(target / name)
                for name in ("database.dump", "media.tar.gz")
            },
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(
            "Consistent database/media backup created. Encrypt and copy it off-host; this folder contains private records."
        )
    finally:
        compose(args, "start", "backend", stdout=subprocess.DEVNULL)


def restore(args):
    if not args.confirm_empty_target:
        raise ValueError(
            "Pass --confirm-empty-target only for a newly provisioned isolated destination"
        )
    source = Path(args.directory).resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    expected = {"database.dump", "media.tar.gz"}
    if set(manifest["files"]) != expected:
        raise ValueError("Unexpected manifest entries")
    for name in expected:
        if digest(source / name) != manifest["files"][name]:
            raise ValueError("Backup checksum mismatch")
    with tarfile.open(source / "media.tar.gz", "r:gz") as archive:
        for item in archive:
            normalized = item.name.replace("\\", "/")
            if (
                normalized.startswith("/")
                or ".." in normalized.split("/")
                or item.issym()
                or item.islnk()
                or item.isdev()
            ):
                raise ValueError("Unsafe media archive entry")
    running = compose(
        args, "ps", "--status", "running", "--services", capture_output=True, text=True
    ).stdout.splitlines()
    if "backend" in running:
        raise ValueError("Restore requires the destination API to be stopped")
    count = scalar(
        args,
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",
    )
    if count != "0":
        raise ValueError(
            "Destination database is not empty; refusing to overwrite data"
        )
    compose(
        args,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "--entrypoint",
        "sh",
        "backend",
        "-c",
        'test -z "$(find /data/media -mindepth 1 -maxdepth 1 -print -quit)"',
        stdout=subprocess.DEVNULL,
    )
    with (source / "database.dump").open("rb") as data:
        compose(
            args,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'exec pg_restore --exit-on-error --single-transaction --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
            stdin=data,
        )
    with (source / "media.tar.gz").open("rb") as data:
        compose(
            args,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--entrypoint",
            "tar",
            "backend",
            "-xzf",
            "-",
            "-C",
            "/data/media",
            stdin=data,
        )
    if scalar(args, "SELECT version_num FROM alembic_version") != manifest["schema"]:
        raise ValueError("Restored schema differs from backup manifest")
    print(
        "Database/media restored. API remains stopped. Run migrations, preflight and synthetic workflow before opening traffic."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--project-name", help="Optional isolated Compose project name")
    sub = parser.add_subparsers(dest="operation", required=True)
    save = sub.add_parser("backup")
    save.add_argument("directory")
    save.add_argument("--maintenance-window", action="store_true")
    load = sub.add_parser("restore")
    load.add_argument("directory")
    load.add_argument("--confirm-empty-target", action="store_true")
    args = parser.parse_args()
    try:
        (backup if args.operation == "backup" else restore)(args)
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Docker operation failed. Inspect protected deployment logs; API restart is attempted after backup."
        )
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
