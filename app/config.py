"""Settings from the environment / .env. OPENSCRAPPER_* wins; legacy SCOUT_* still works."""

import os
from pathlib import Path
from typing import Optional

PREFIX = 'OPENSCRAPPER_'
LEGACY_PREFIX = 'SCOUT_'


def env(name: str, default: str = '') -> str:
    """env('PROXY') reads OPENSCRAPPER_PROXY, then SCOUT_PROXY. Empty counts as unset."""
    for prefix in (PREFIX, LEGACY_PREFIX):
        value = os.environ.get(prefix + name)
        if value not in (None, ''):
            return value
    return default


def flag(name: str) -> bool:
    return env(name).strip().lower() in ('1', 'true', 'yes', 'on')


def number(name: str, default: float) -> float:
    try:
        return float(env(name, str(default)))
    except ValueError:
        return default


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding variables that are already set."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())


def update_env_file(path: Path, name: str, value: str) -> None:
    """Persist a setting under its OPENSCRAPPER_ name and retire the legacy SCOUT_ line."""
    path = Path(path)
    key, legacy = PREFIX + name, LEGACY_PREFIX + name
    lines, found = [], False
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines(keepends=True):
            stripped = line.strip()
            if stripped.startswith(legacy + '='):
                continue
            if stripped.startswith(key + '='):
                lines.append(f'{key}={value}\n')
                found = True
            else:
                lines.append(line if line.endswith('\n') else line + '\n')
    if not found:
        lines.append(f'{key}={value}\n')
    path.write_text(''.join(lines), encoding='utf-8')
    os.environ[key] = value
    os.environ.pop(legacy, None)


def home() -> Path:
    p = Path(os.environ.get('OPENSCRAPPER_HOME') or Path.home() / '.openscrapper')
    p.mkdir(parents=True, exist_ok=True)
    return p


def llm_name() -> Optional[str]:
    return env('LLM').strip() or None
