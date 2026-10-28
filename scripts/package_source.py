"""Create a distributable source archive without local credentials or runtime data.

Usage (from repository root): python scripts/package_source.py
"""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / 'FindIt-Next-2.0-clean-source.zip'
EXCLUDED_DIRECTORIES = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'coverage', '.pytest_cache',
                        '__pycache__', '.ruff_cache', 'media', 'storage', 'test-results',
                        'playwright-report', 'htmlcov', '.idea', '.vscode', 'work'}
EXCLUDED_FILES = {'.env', '.coverage', '.DS_Store', 'Thumbs.db'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.sqlite', '.sqlite3', '.log', '.tsbuildinfo', '.pem', '.key', '.eml', '.dump'}


def is_safe(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (not any(part in EXCLUDED_DIRECTORIES for part in relative.parts)
            and (path.name in {'.env.example', '.env.production.example'} or not any(part.startswith('.env.') for part in relative.parts))
            and path.name not in EXCLUDED_FILES
            and path.suffix.lower() not in EXCLUDED_SUFFIXES
            and not path.is_symlink())


def main() -> None:
    count = 0
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file() and is_safe(path):
                archive.write(path, f'FindIT/{path.relative_to(ROOT).as_posix()}')
                count += 1
    print(f'Source archive: {OUTPUT.name} ({count} files, {OUTPUT.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
