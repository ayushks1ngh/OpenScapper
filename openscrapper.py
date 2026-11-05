#!/usr/bin/env python3

import sys
import csv
import time
import os
import logging
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

from app import __version__

_verbose = '--verbose' in sys.argv or '-V' in sys.argv

_args = [a for a in sys.argv[1:] if a not in ('--verbose', '-V')]
if _args:
    arg = _args[0].lower()
    if arg in ('--version', '-v', 'version'):
        print(f"OpenScrapper v{__version__}")
        sys.exit(0)
    elif arg in ('--help', '-h', 'help'):
        print(f"OpenScrapper v{__version__} - Social media lead generation tool")
        print()
        print("Usage: python openscrapper.py [options]")
        print("       python openscrapper.py lead <url>   Print a lead (JSON) for any profile or page")
        print('       python openscrapper.py find "<query>" [--limit N]   Describe the leads you want')
        print()
        print("Options:")
        print("  --version, -v    Show version")
        print("  --help, -h       Show this help")
        print("  --verbose, -V    Enable debug logging (console and log file)")
        print()
        print("Run without arguments to start the interactive menu.")
        sys.exit(0)

from app import config  # noqa: E402

config.load_dotenv(Path(__file__).parent / '.env')

from app.logsetup import setup_logging  # noqa: E402

LOG_FILE = setup_logging(verbose=_verbose)

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn
from rich import box
from rich.layout import Layout
from rich.text import Text
from rich.theme import Theme
from rich.rule import Rule

from app.scrapers.instagram import scrape_profile_no_login
from app.scrapers.stealth import random_delay, proxy_status

ACCENT = "#a70947"
ACCENT_DIM = "#6b0530"
ACCENT_LIGHT = "#d64d7a"
ACCENT_MUTED = "#4a0727"

_GRAD_START = (255, 107, 157)
_GRAD_END = (167, 9, 71)

_LOGO_LINES = [
    "███████  ██████  ██████  ██  ██ ████████",
    "██      ██      ██    ██ ██  ██    ██   ",
    "███████ ██      ██    ██ ██  ██    ██   ",
    "     ██ ██      ██    ██ ██  ██    ██   ",
    "███████  ██████  ██████   ████     ██   ",
]

_session_stats = {"scraped": 0}
_update_cache = {"checked": False, "latest": None}


def _check_for_updates():
    """Check GitHub releases API for a newer version. Non-blocking, fails silently."""
    if _update_cache["checked"]:
        return _update_cache["latest"]

    _update_cache["checked"] = True

    try:
        import requests as _req
        resp = _req.get(
            "https://api.github.com/repos/ayushks1ngh/OpenScapper/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=3,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        tag = data.get("tag_name", "")
        latest = tag.lstrip("v").strip()
        if not latest:
            return None

        def _ver(s):
            try:
                return tuple(int(x) for x in s.split("."))
            except (ValueError, AttributeError):
                return (0,)

        if _ver(latest) > _ver(__version__):
            _update_cache["latest"] = latest
            return latest

    except Exception:
        pass

    return None


def _start_update_check():
    """Fire off the update check in a background thread so it doesn't block startup."""
    import threading
    t = threading.Thread(target=_check_for_updates, daemon=True)
    t.start()
    return t


custom_theme = Theme({
    "prompt.choices": ACCENT,
    "prompt.default": "dim",
})
console = Console(theme=custom_theme)
Prompt.prompt_suffix = " "
Confirm.prompt_suffix = " "


def _update_env(name, value):
    config.update_env_file(Path(__file__).parent / '.env', name, value)


def enrich_profiles(profiles):
    if not profiles:
        return profiles

    if not Confirm.ask("\n[white][+] Enrich leads with contact info?[/white]", default=True):
        return profiles

    from app.scrapers.enrichment import LeadEnricher
    hunter_key = os.environ.get('HUNTER_API_KEY', '').strip() or None
    enricher = LeadEnricher(hunter_api_key=hunter_key)

    console.print()
    emails_found = 0
    phones_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[white]Enriching leads...", total=len(profiles))

        enriched = []
        for p in profiles:
            had_email = bool(p.get('email'))
            had_phone = bool(p.get('phone'))

            result = enricher.enrich_lead(p)
            enriched.append(result)

            if result.get('email') and not had_email:
                emails_found += 1
            if result.get('phone') and not had_phone:
                phones_found += 1

            progress.advance(task)

    console.print()

    summary_parts = []
    if emails_found:
        summary_parts.append(f"[green]{emails_found} emails found[/green]")
    if phones_found:
        summary_parts.append(f"[green]{phones_found} phones found[/green]")
    if not summary_parts:
        summary_parts.append("[yellow]No new contact info found[/yellow]")

    scores = [e.get('lead_score', 0) for e in enriched]
    avg_score = sum(scores) // len(scores) if scores else 0
    summary_parts.append(f"[white]Avg lead score: {avg_score}/100[/white]")

    console.print(Rule("[bold white]Enrichment[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    for part in summary_parts:
        console.print(f"  {part}")
    console.print()

    email_leads = [e for e in enriched if e.get('email')]
    if email_leads:
        t = Table(show_header=True, box=box.MINIMAL_HEAVY_HEAD, border_style="dim", padding=(0, 1))
        t.add_column("Lead", style="white")
        t.add_column("Email", style="white")
        t.add_column("Confidence", style="green")
        t.add_column("Source", style="dim")
        t.add_column("Verified", style="yellow")

        for e in email_leads:
            name = e.get('full_name') or e.get('username', '?')
            email_score = e.get('email_score', 0)
            score_color = 'green' if email_score >= 70 else 'yellow' if email_score >= 40 else 'red'
            verified = 'Yes' if e.get('email_verified') else 'No'
            t.add_row(
                name[:25],
                e['email'],
                f"[{score_color}]{email_score}%[/{score_color}]",
                e.get('email_source', '?'),
                verified
            )

        console.print(t)

    return enriched


def _platform_header(name: str, subtitle: str = "No login required"):
    """Print a consistent platform header."""
    console.print()
    console.print(Rule(
        f"[bold white]{name}[/bold white]  [dim]{subtitle}[/dim]",
        style=ACCENT_DIM,
        align="left"
    ))
    console.print()


def _profile_card(profile: dict):
    """Display a scraped profile as a compact card."""
    _session_stats["scraped"] += 1
    lines = []

    if profile.get('full_name'):
        lines.append(f"[bold white]{profile['full_name'][:50]}[/bold white]")

    stats = []
    if profile.get('follower_count'):
        stats.append(f"[white]{profile['follower_count']:,}[/white] [dim]followers[/dim]")
    if profile.get('following_count'):
        stats.append(f"[white]{profile['following_count']:,}[/white] [dim]following[/dim]")
    if stats:
        lines.append("  ·  ".join(stats))

    email = profile.get('email', '')
    if profile.get('bio'):
        bio = profile['bio'].replace('\n', ' ')
        if email:
            bio = bio.replace(email, '').strip(' |·-,')
        bio = bio[:80] + '...' if len(bio) > 80 else bio
        if bio:
            lines.append(f"[dim]{bio}[/dim]")

    if email:
        lines.append(f"[bold {ACCENT}]{email}[/bold {ACCENT}]")

    if profile.get('website'):
        lines.append(f"[dim]{profile['website']}[/dim]")

    if profile.get('phone'):
        lines.append(f"[dim]{profile['phone']}[/dim]")

    username = profile.get('username', '?')
    console.print(Panel(
        "\n".join(lines) if lines else "[dim]No data[/dim]",
        title=f"[bold white]@{username}[/bold white]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        padding=(0, 2),
        width=64
    ))


def _success_summary(successful: int, total: int, item_type: str = "profiles"):
    """Print a compact success summary line."""
    console.print()
    if successful == total:
        console.print(f"  [green]OK[/green] [white]{successful}/{total} {item_type} scraped[/white]")
    elif successful > 0:
        console.print(f"  [yellow]DONE[/yellow] [white]{successful}/{total} {item_type} scraped[/white]")
    else:
        console.print(f"  [red]FAIL[/red] [white]0/{total} {item_type} scraped[/white]")
    console.print()


def _export_result(filename: str, count: int, item_type: str = "profiles"):
    """Print a compact export confirmation line."""
    console.print(f"  [green]Saved[/green] [white]{filename}[/white] [dim]({count} {item_type})[/dim]")
    console.print()


def _no_results():
    """Print no-results feedback."""
    console.print()
    console.print("  [yellow]No profiles were scraped successfully[/yellow]")
    console.print()


def _pause():
    """Pause before returning to menu so the user can review output."""
    console.print()
    console.print(Rule(style=ACCENT_MUTED))
    Prompt.ask("[dim]Press Enter to continue[/dim]", default="")


def _gradient_line(text: str, row: int, total_rows: int) -> Text:
    """Apply a per-character color gradient across a line of text.
    Row position shifts the gradient vertically (top rows lighter, bottom darker)."""
    t = Text()
    length = len(text.rstrip())
    row_shift = row / max(total_rows - 1, 1)

    for j, char in enumerate(text):
        if j < length and char != ' ':
            h_progress = j / max(length - 1, 1)
            progress = h_progress * 0.6 + row_shift * 0.4
            progress = max(0.0, min(1.0, progress))

            r = int(_GRAD_START[0] + (_GRAD_END[0] - _GRAD_START[0]) * progress)
            g = int(_GRAD_START[1] + (_GRAD_END[1] - _GRAD_START[1]) * progress)
            b = int(_GRAD_START[2] + (_GRAD_END[2] - _GRAD_START[2]) * progress)
            t.append(char, style=f"bold #{r:02x}{g:02x}{b:02x}")
        else:
            t.append(char)
    return t


def _gradient_bar() -> Text:
    """Create a thin gradient bar spanning the terminal width."""
    width = min(console.width, 80)
    t = Text()
    for j in range(width):
        progress = j / max(width - 1, 1)
        r = int(_GRAD_START[0] + (_GRAD_END[0] - _GRAD_START[0]) * progress)
        g = int(_GRAD_START[1] + (_GRAD_END[1] - _GRAD_START[1]) * progress)
        b = int(_GRAD_START[2] + (_GRAD_END[2] - _GRAD_START[2]) * progress)
        t.append("▀", style=f"#{r:02x}{g:02x}{b:02x}")
    return t


def show_header():
    console.print()
    console.print(_gradient_bar(), justify="center")
    console.print()

    total = len(_LOGO_LINES)
    for i, line in enumerate(_LOGO_LINES):
        t = _gradient_line(line, i, total)
        console.print(t, justify="center")

    console.print()
    console.print(f"[dim]v{__version__}[/dim]  [white]Lead Generation Tool[/white]", justify="center")

    console.print()
    console.print(_gradient_bar(), justify="center")

    ps = proxy_status()
    if ps == 'custom':
        proxy_str = "[green]● custom[/green]"
    elif ps == 'file':
        proxy_str = "[green]● rotating[/green]"
    elif ps == 'free':
        proxy_str = "[yellow]● free[/yellow]"
    else:
        proxy_str = "[dim]○ off[/dim]"

    status = f"[dim]github.com/ayushks1ngh/OpenScapper[/dim]  ·  [dim]Proxy:[/dim] {proxy_str}"
    if _session_stats["scraped"] > 0:
        status += f"  ·  [dim]Scraped:[/dim] [white]{_session_stats['scraped']}[/white]"
    console.print(status, justify="center")
    console.print()


def show_menu():
    console.print(Rule("[bold white]Platforms[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()

    platforms_left = [
        ("1", "Instagram", "profiles"),
        ("2", "TikTok", "profiles"),
        ("3", "LinkedIn", "cookie"),
        ("4", "GitHub", "profiles"),
        ("5", "YouTube", "channels"),
    ]
    platforms_right = [
        ("6", "Twitch", "streamers"),
        ("7", "Linktree", "link-in-bio"),
        ("8", "Pinterest", "profiles"),
    ]

    table = Table(show_header=False, box=None, padding=(0, 0), pad_edge=False, expand=False)
    table.add_column("", width=35)
    table.add_column("", width=35)

    max_rows = max(len(platforms_left), len(platforms_right))
    for i in range(max_rows):
        left = ""
        right = ""
        if i < len(platforms_left):
            n, name, desc = platforms_left[i]
            left = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        if i < len(platforms_right):
            n, name, desc = platforms_right[i]
            right = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        table.add_row(left, right)

    console.print(table)
    console.print()

    console.print(Rule("[bold white]Tools[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()

    tools_left = [
        ("9", "Bulk Scrape", "from file"),
        ("10", "Exports", "view files"),
        ("12", "Smart Scrape", "any URL (AI)"),
        ("13", "Scraper Health", "self-healing"),
        ("14", "Lead from URL", "any page"),
        ("15", "Find Leads", "describe them"),
    ]
    tools_right = [
        ("11", "Settings", "config"),
        ("0", "Exit", ""),
    ]

    tools = Table(show_header=False, box=None, padding=(0, 0), pad_edge=False, expand=False)
    tools.add_column("", width=35)
    tools.add_column("", width=35)

    for i in range(max(len(tools_left), len(tools_right))):
        left = ""
        right = ""
        if i < len(tools_left):
            n, name, desc = tools_left[i]
            left = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        if i < len(tools_right):
            n, name, desc = tools_right[i]
            right = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        tools.add_row(left, right)

    console.print(tools)
    console.print()


def _get_delay_range(fallback=(1.0, 2.5)):
    """Get configured delay range from env vars, with fallback."""
    try:
        d_min = config.number('DELAY_MIN', fallback[0])
        d_max = config.number('DELAY_MAX', fallback[1])
        return (d_min, d_max) if d_max >= d_min >= 0 else fallback
    except ValueError:
        return fallback


def _standard_scrape_loop(scraper_func, items, label_prefix="@", delay_range=None):
    """Shared scrape loop: spinner per item, then profile card. Clean output."""
    if delay_range is None:
        delay_range = _get_delay_range()
    profiles = []

    for i, item in enumerate(items, 1):
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            task = progress.add_task(f"[white]Scraping {label_prefix}{item}  [dim]({i}/{len(items)})[/dim]", total=None)
            try:
                prev_level = logging.getLogger().level
                if not _verbose:
                    logging.getLogger().setLevel(logging.CRITICAL)
                profile = scraper_func(item)
                if not _verbose:
                    logging.getLogger().setLevel(prev_level)

                if profile:
                    profiles.append(profile)
                    progress.stop()
                    _profile_card(profile)
                else:
                    progress.stop()
                    console.print(f"  [red]✗[/red] [dim]{label_prefix}{item} — not found[/dim]")
            except RuntimeError as e:
                if not _verbose:
                    logging.getLogger().setLevel(prev_level)
                progress.stop()
                console.print(f"  [bold red]✗ {label_prefix}{item} — rate limited[/bold red]")
                break
            except Exception as e:
                if not _verbose:
                    logging.getLogger().setLevel(prev_level)
                progress.stop()
                console.print(f"  [red]✗[/red] [dim]{label_prefix}{item} — {str(e)[:80]}[/dim]")

        if i < len(items):
            random_delay(*delay_range)

    return profiles


def _standard_export(profiles, total, platform_name, item_type="profiles"):
    """Shared post-scrape: summary, enrichment, CSV export."""
    if profiles:
        _success_summary(len(profiles), total, item_type)
        profiles = enrich_profiles(profiles)
        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{platform_name}_export_{timestamp}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)
            _export_result(filename, len(profiles), item_type)
    else:
        _no_results()


def _collect_usernames(platform_name, prompt_label="Username", strip_at=False):
    """Shared username input loop. Returns list of usernames."""
    console.print(f"[white]Enter {platform_name} usernames (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    items = []
    while True:
        entry = Prompt.ask(prompt_label, default="")
        if not entry:
            break
        if strip_at:
            entry = entry.replace('@', '')
        entry = entry.strip()
        if entry:
            items.append(entry)
            prefix = "@" if strip_at else ""
            console.print(f"[green]✓[/green] Added {prefix}{entry}")

    if not items:
        console.print("[yellow]No usernames entered[/yellow]")
    return items


def scrape_instagram_interactive():
    _platform_header("Instagram")
    usernames = _collect_usernames("Instagram", strip_at=True)
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile_no_login, usernames, label_prefix="@", delay_range=(1.5, 4.0))
    _standard_export(profiles, len(usernames), "instagram")


def scrape_tiktok_interactive():
    from app.scrapers.tiktok import scrape_tiktok_profile
    _platform_header("TikTok")
    usernames = _collect_usernames("TikTok", strip_at=True)
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_tiktok_profile, usernames, label_prefix="@", delay_range=(2.0, 5.0))
    _standard_export(profiles, len(usernames), "tiktok")


def scrape_linkedin_interactive():
    from app.scrapers.linkedin import scrape_linkedin_profile

    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        console.print()
        console.print(Rule("[bold yellow]LinkedIn Cookie Required[/bold yellow]", style="yellow", align="left"))
        console.print()
        console.print("  [white]1.[/white] Open Chrome > linkedin.com (logged in)")
        console.print("  [white]2.[/white] F12 > Application > Cookies > linkedin.com")
        console.print("  [white]3.[/white] Copy the value of [bold]li_at[/bold]")
        console.print("  [white]4.[/white] Add to .env: [bold]LINKEDIN_COOKIE=your_value[/bold]")
        console.print("  [white]5.[/white] Restart OpenScrapper")
        console.print()
        return

    _platform_header("LinkedIn", "Using session cookie")

    console.print("[white]Enter LinkedIn usernames or profile URLs (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    usernames = []
    while True:
        entry = Prompt.ask("Username/URL", default="")
        if not entry:
            break
        entry = entry.strip().rstrip('/')
        if '/in/' in entry:
            entry = entry.split('/in/')[-1]
        entry = entry.lstrip('@').strip()
        if entry:
            usernames.append(entry)
            console.print(f"[green]✓[/green] Added {entry}")

    if not usernames:
        console.print("[yellow]No usernames entered[/yellow]")
        return

    console.print()
    profiles = _standard_scrape_loop(scrape_linkedin_profile, usernames, label_prefix="", delay_range=(3.0, 6.0))
    _standard_export(profiles, len(usernames), "linkedin")


def scrape_github_interactive():
    from app.scrapers.github import scrape_profile
    _platform_header("GitHub")
    usernames = _collect_usernames("GitHub")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(0.5, 1.5))
    _standard_export(profiles, len(usernames), "github")


def scrape_youtube_interactive():
    from app.scrapers.youtube import scrape_channel
    _platform_header("YouTube")

    console.print("[white]Enter YouTube channel handles (e.g. @MrBeast) or channel IDs[/white]")
    console.print("[dim]Press Enter on empty line when done[/dim]")
    console.print()

    channels = []
    while True:
        channel = Prompt.ask("Channel", default="")
        if not channel:
            break
        channel = channel.strip()
        if channel:
            channels.append(channel)
            console.print(f"[green]✓[/green] Added {channel}")

    if not channels:
        console.print("[yellow]No channels entered[/yellow]")
        return

    console.print()
    profiles = _standard_scrape_loop(scrape_channel, channels, label_prefix="", delay_range=(1.0, 2.5))
    _standard_export(profiles, len(channels), "youtube", "channels")


def scrape_twitch_interactive():
    from app.scrapers.twitch import scrape_profile
    _platform_header("Twitch")
    usernames = _collect_usernames("Twitch")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(0.5, 1.5))
    _standard_export(profiles, len(usernames), "twitch")


def scrape_linktree_interactive():
    from app.scrapers.linktree import scrape_linktree, scrape_all
    _platform_header("Link-in-Bio", "Linktree, Stan & more")

    console.print("[1] Linktree (linktr.ee)")
    console.print("[2] Auto-detect (try all)")
    console.print()
    platform_choice = Prompt.ask("[>] Platform", choices=["1", "2"], default="1")

    scraper_map = {"1": (scrape_linktree, "linktree"), "2": (scrape_all, "linkbio")}
    scraper_func, platform_name = scraper_map[platform_choice]

    console.print()
    usernames = _collect_usernames("link-in-bio")
    if not usernames:
        return

    console.print()
    profiles = _standard_scrape_loop(scraper_func, usernames, label_prefix="", delay_range=(0.5, 1.5))

    if profiles:
        _success_summary(len(profiles), len(usernames))
        profiles = enrich_profiles(profiles)
        if Confirm.ask("[+] Export to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{platform_name}_export_{timestamp}.csv"

            export_profiles = []
            for p in profiles:
                flat = {k: v for k, v in p.items() if k not in ['links', 'socials']}
                if p.get('socials'):
                    for platform, handle in p['socials'].items():
                        flat[f'social_{platform}'] = handle
                export_profiles.append(flat)

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if export_profiles:
                    all_keys = set()
                    for p in export_profiles:
                        all_keys.update(p.keys())
                    writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                    writer.writeheader()
                    writer.writerows(export_profiles)
            _export_result(filename, len(profiles))
    else:
        _no_results()


def scrape_pinterest_interactive():
    from app.scrapers.pinterest import scrape_profile
    _platform_header("Pinterest")
    usernames = _collect_usernames("Pinterest")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(1.0, 2.5))
    _standard_export(profiles, len(usernames), "pinterest")


def scrape_from_file():
    _platform_header("Bulk Scrape", "From username list file")
    console.print()

    filename = Prompt.ask("[>] Enter filename", default="usernames.txt")

    try:
        usernames = []
        if filename.lower().endswith('.csv'):
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    username = row.get('username', '') or row.get('Username', '') or row.get('handle', '') or row.get('Handle', '')
                    if not username:
                        first_col = list(row.values())[0] if row else ''
                        username = first_col
                    username = username.strip().replace('@', '')
                    if username:
                        usernames.append(username)
        else:
            with open(filename, 'r', encoding='utf-8') as f:
                usernames = [line.strip().replace('@', '') for line in f if line.strip()]

        if not usernames:
            console.print(f"\n[red]✗ No usernames found in {filename}[/red]")
            return

        console.print(f"\n[white]Found {len(usernames)} usernames in {filename}[/white]")

        console.print()
        console.print(f"[bold {ACCENT}]Select platform:[/bold {ACCENT}]")
        console.print("[1] Instagram")
        console.print("[2] TikTok")
        console.print("[3] LinkedIn")
        console.print("[4] YouTube")
        console.print("[5] GitHub")
        console.print("[6] Twitch")
        console.print("[7] Linktree")
        console.print("[8] Pinterest")
        console.print()

        platform_choice = Prompt.ask("[>] Platform", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="1")

        platform_map = {
            "1": ("instagram", "Instagram"),
            "2": ("tiktok", "TikTok"),
            "3": ("linkedin", "LinkedIn"),
            "4": ("youtube", "YouTube"),
            "5": ("github", "GitHub"),
            "6": ("twitch", "Twitch"),
            "7": ("linktree", "Linktree"),
            "8": ("pinterest", "Pinterest"),
        }
        platform_key, platform_name = platform_map[platform_choice]

        if platform_key == "instagram":
            from app.scrapers.instagram import scrape_profile_no_login as scraper_func
        elif platform_key == "tiktok":
            from app.scrapers.tiktok import scrape_tiktok_profile as scraper_func
        elif platform_key == "linkedin":
            cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
            if not cookie:
                console.print("[red]✗ LINKEDIN_COOKIE not set in .env. Cannot bulk scrape LinkedIn.[/red]")
                return
            from app.scrapers.linkedin import scrape_linkedin_profile as scraper_func
        elif platform_key == "youtube":
            from app.scrapers.youtube import scrape_channel as scraper_func
        elif platform_key == "github":
            from app.scrapers.github import scrape_profile as scraper_func
        elif platform_key == "twitch":
            from app.scrapers.twitch import scrape_profile as scraper_func
        elif platform_key == "linktree":
            from app.scrapers.linktree import scrape_linktree as scraper_func
        elif platform_key == "pinterest":
            from app.scrapers.pinterest import scrape_profile as scraper_func

        console.print()
        console.print(f"[white]Scraping {len(usernames)} {platform_name} profiles...[/white]")

        if not Confirm.ask("Continue?", default=True):
            return

        console.print()

        profiles = []
        successful = 0

        for i, username in enumerate(usernames, 1):
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                task = progress.add_task(f"[white]@{username}  [dim]({i}/{len(usernames)})[/dim]", total=None)

                try:
                    prev_level = logging.getLogger().level
                    if not _verbose:
                        logging.getLogger().setLevel(logging.CRITICAL)
                    profile = scraper_func(username)
                    if not _verbose:
                        logging.getLogger().setLevel(prev_level)

                    if profile:
                        profiles.append(profile)
                        successful += 1
                        follower_count = profile.get('follower_count', 0) or profile.get('subscribers', 0) or 0
                        progress.stop()
                        console.print(f"  [green]✓[/green] @{username}  [dim]{follower_count:,} followers[/dim]")
                    else:
                        progress.stop()
                        console.print(f"  [red]✗[/red] [dim]@{username}[/dim]")

                except Exception as e:
                    if not _verbose:
                        logging.getLogger().setLevel(prev_level)
                    progress.stop()
                    console.print(f"  [red]✗[/red] [dim]@{username}[/dim]")

            if i < len(usernames):
                random_delay(*_get_delay_range((1.5, 4.0)))

        console.print()

        if profiles:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_filename = f"{platform_key}_export_{timestamp}.csv"

            with open(export_filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)

            _success_summary(successful, len(usernames))
            _export_result(export_filename, successful)
        else:
            _no_results()

    except FileNotFoundError:
        console.print(f"\n[red]✗ Error: File '{filename}' not found![/red]")
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")


def settings_menu():
    _platform_header("Settings", "Configure OpenScrapper")

    ps = proxy_status()
    current_proxy = config.env('PROXY')
    free_enabled = config.flag('FREE_PROXY')
    proxy_file = config.env('PROXY_FILE')
    delay_min = config.env('DELAY_MIN', '1.0')
    delay_max = config.env('DELAY_MAX', '2.5')
    li_cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()

    proxy_str = f"[green]{ps}[/green]" if ps != 'none' else "[red]off[/red]"
    if current_proxy:
        proxy_str += f"  [dim]{current_proxy[:40]}[/dim]"
    elif proxy_file:
        proxy_str += f"  [dim]{proxy_file[:40]}[/dim]"

    console.print(f"  [dim]Proxy:[/dim]     {proxy_str}")
    console.print(f"  [dim]Free proxy:[/dim] [green]on[/green]" if free_enabled else f"  [dim]Free proxy:[/dim] [dim]off[/dim]")
    console.print(f"  [dim]Delay:[/dim]     [white]{delay_min}s - {delay_max}s[/white]")
    console.print(f"  [dim]LinkedIn:[/dim]  [green]cookie set[/green]" if li_cookie else f"  [dim]LinkedIn:[/dim]  [dim]not configured[/dim]")
    console.print(f"  [dim]Scraped:[/dim]   [white]{_session_stats['scraped']}[/white] [dim]this session[/dim]")
    console.print()

    console.print(Rule("[bold white]Proxy[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    console.print(f"  [{ACCENT}][1][/{ACCENT}]  Set proxy URL")
    console.print(f"  [{ACCENT}][2][/{ACCENT}]  Set proxy file")
    console.print(f"  [{ACCENT}][3][/{ACCENT}]  Toggle free proxy")
    console.print(f"  [{ACCENT}][4][/{ACCENT}]  Test connection")
    console.print(f"  [{ACCENT}][5][/{ACCENT}]  Remove proxy")
    console.print()

    console.print(Rule("[bold white]Scraping[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    console.print(f"  [{ACCENT}][6][/{ACCENT}]  Set scrape delay")
    console.print(f"  [{ACCENT}][7][/{ACCENT}]  Set LinkedIn cookie")
    console.print()

    console.print(Rule("[bold white]Data[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    console.print(f"  [{ACCENT}][8][/{ACCENT}]  Clear all exports")
    console.print(f"  [{ACCENT}][0][/{ACCENT}]  Back to menu")
    console.print()

    choice = Prompt.ask(f"[{ACCENT}]>[/{ACCENT}]", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="0")

    import httpx as _httpx

    if choice == '1':
        url = Prompt.ask("[>] Proxy URL (e.g. http://user:pass@host:port)")
        if url.strip():
            _update_env('PROXY', url.strip())
            console.print(f"[green]✓ Proxy set[/green]")

    elif choice == '2':
        filepath = Prompt.ask("[>] Path to proxy list file")
        if filepath.strip():
            if os.path.exists(filepath.strip()):
                _update_env('PROXY_FILE', filepath.strip())
                console.print(f"[green]✓ Proxy file set[/green]")
            else:
                console.print(f"[red]✗ File not found: {filepath.strip()}[/red]")

    elif choice == '3':
        if free_enabled:
            _update_env('FREE_PROXY', 'false')
            console.print("[yellow]✓ Free proxy disabled[/yellow]")
        else:
            _update_env('FREE_PROXY', 'true')
            console.print("[green]✓ Free proxy enabled[/green]")

    elif choice == '4':
        console.print("[white]Testing connection...[/white]")
        from app.scrapers.stealth import get_proxy
        px = get_proxy()
        if not px:
            console.print("[dim]No proxy configured, testing direct...[/dim]")
            try:
                resp = _httpx.get('https://httpbin.org/ip', timeout=10)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Direct connection works. IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Connection failed: {str(e)[:80]}[/red]")
        else:
            console.print(f"[dim]Trying: {px[:60]}[/dim]")
            proxy_url = px if px.startswith('http') else f'http://{px}'
            try:
                resp = _httpx.get('https://httpbin.org/ip', proxy=proxy_url, timeout=10, verify=False)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Proxy works! IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Proxy failed: {str(e)[:80]}[/red]")
                if free_enabled:
                    console.print("[yellow]Free proxies are unreliable. Trying others...[/yellow]")
                    from app.scrapers.stealth import _fetch_free_proxies
                    proxies = _fetch_free_proxies()
                    for p in proxies[:3]:
                        p_url = p if p.startswith('http') else f'http://{p}'
                        console.print(f"[dim]Trying: {p_url[:60]}[/dim]")
                        try:
                            resp = _httpx.get('https://httpbin.org/ip', proxy=p_url, timeout=8, verify=False)
                            ip = resp.json().get('origin', '?')
                            console.print(f"[green]✓ Found working proxy! IP: {ip}[/green]")
                            break
                        except Exception:
                            console.print(f"[red]✗ Dead[/red]")
                    else:
                        console.print("[red]All free proxies failed. Use a paid proxy.[/red]")

    elif choice == '5':
        _update_env('PROXY', '')
        _update_env('FREE_PROXY', 'false')
        _update_env('PROXY_FILE', '')
        console.print("[yellow]✓ Proxy removed[/yellow]")

    elif choice == '6':
        console.print(f"[dim]Current: {delay_min}s - {delay_max}s between requests[/dim]")
        new_min = Prompt.ask("[>] Min delay (seconds)", default=delay_min)
        new_max = Prompt.ask("[>] Max delay (seconds)", default=delay_max)
        try:
            fmin, fmax = float(new_min), float(new_max)
            if fmin < 0 or fmax < fmin:
                console.print("[red]✗ Invalid range[/red]")
            else:
                _update_env('DELAY_MIN', str(fmin))
                _update_env('DELAY_MAX', str(fmax))
                console.print(f"[green]✓ Delay set to {fmin}s - {fmax}s[/green]")
        except ValueError:
            console.print("[red]✗ Must be numbers[/red]")

    elif choice == '7':
        console.print("[white]Paste your LinkedIn li_at cookie value:[/white]")
        console.print("[dim]Chrome > F12 > Application > Cookies > linkedin.com > li_at[/dim]")
        cookie = Prompt.ask("[>] li_at", default="")
        if cookie.strip():
            _update_env('LINKEDIN_COOKIE', cookie.strip())
            console.print("[green]✓ LinkedIn cookie saved[/green]")

    elif choice == '8':
        csv_files = list(Path('.').glob('*_export_*.csv'))
        if not csv_files:
            console.print("[yellow]No exports to clear[/yellow]")
        else:
            console.print(f"[yellow]This will delete {len(csv_files)} export file(s)[/yellow]")
            if Confirm.ask("[>] Continue?", default=False):
                for f in csv_files:
                    f.unlink()
                console.print(f"[green]✓ Deleted {len(csv_files)} exports[/green]")



def view_exports():
    _platform_header("Exports", "Your scraped data")

    csv_files = list(Path('.').glob('*_export_*.csv'))

    if not csv_files:
        console.print("  [yellow]No exports found yet[/yellow]")
        console.print("  [dim]Run a scrape to create your first export[/dim]")
        return

    csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    table = Table(box=box.MINIMAL_HEAVY_HEAD, border_style="dim", padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Filename", style="white")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Date", style="dim")

    for i, file in enumerate(csv_files[:10], 1):
        size = file.stat().st_size / 1024
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(file.stat().st_mtime))
        table.add_row(str(i), file.name, f"{size:.1f} KB", mtime)

    console.print(table)
    console.print(f"  [dim]{len(csv_files)} exports total[/dim]")
    console.print()


def smart_scrape_interactive():
    """Scrape any URL: Scrapling fetches it, the configured LLM extracts the data."""
    from app.scrapers.ai import ai_enabled, ai_extract, llm_name, CONTACT_PROMPT
    from app.scrapers.fetch import fetch, engine_mode

    _platform_header("Smart Scrape", f"engine: {engine_mode()}  |  LLM: {llm_name() or 'off'}")
    if not ai_enabled():
        console.print("[yellow]No LLM configured.[/yellow] Set [bold]OPENSCRAPPER_LLM[/bold] in .env, e.g.")
        console.print("  [dim]OPENSCRAPPER_LLM=ollama/llama3.2[/dim]  (local, free)")
        console.print("  [dim]OPENSCRAPPER_LLM=openai/gpt-4o-mini[/dim] + [dim]OPENSCRAPPER_LLM_KEY=...[/dim]")
        return

    url = Prompt.ask(f"[{ACCENT}]URL[/{ACCENT}]").strip()
    if not url:
        return
    prompt = Prompt.ask(f"[{ACCENT}]What to extract[/{ACCENT}]", default="contact details")
    prompt = CONTACT_PROMPT if prompt == "contact details" else prompt

    with console.status("Fetching and extracting..."):
        result = ai_extract(url, prompt)
    if not result:
        console.print("[red]✗ Nothing extracted (blocked page, LLM unreachable, or empty result).[/red]")
        return
    import json
    console.print(json.dumps(result, indent=2, ensure_ascii=False))


def _lead_json(url: str):
    import json
    from app.lead.any_url import lead_from_url
    res = lead_from_url(url)
    if not res.lead:
        return None, res
    return json.dumps(res.lead, indent=2, ensure_ascii=False), res


def _show_plan(plan):
    rng = ""
    if plan.min_followers is not None or plan.max_followers is not None:
        lo = f"{plan.min_followers:,}" if plan.min_followers is not None else "0"
        hi = f"{plan.max_followers:,}" if plan.max_followers is not None else "any"
        rng = f"{lo} to {hi}"
    console.print(f"  [dim]looking for[/dim]  {plan.terms or '(anything)'}")
    console.print(f"  [dim]location   [/dim]  {plan.location or 'any'}")
    console.print(f"  [dim]platforms  [/dim]  {', '.join(plan.platforms)}")
    console.print(f"  [dim]followers  [/dim]  {rng or 'any'}")
    console.print()


def _run_find(query: str, limit: int, confirm: bool = True):
    from app.prospect.pipeline import export_csv, run
    from app.prospect.query import parse_query

    plan = parse_query(query)
    if not plan.terms and not plan.location:
        console.print("[red]✗ Describe who you want, e.g. \"yoga studio owners in Austin with 5k+ followers\".[/red]")
        return None
    _show_plan(plan)
    if confirm and not Confirm.ask(f"[{ACCENT}]Search with this plan?[/{ACCENT}]", default=True):
        return None

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), MofNCompleteColumn(),
                  console=console, transient=True) as prog:
        task = prog.add_task("Finding profiles...", total=None)

        def on_progress(stage, i, n):
            prog.update(task, description="Scraping and enriching..." if stage == 'scraping' else
                        "Found candidates", total=n, completed=i)

        out = run(plan, per_platform=limit, on_progress=on_progress)

    leads, st = out['leads'], out['stats']
    console.print(f"[dim]{st['discovered']} found · {st['scraped']} scraped · {st['filtered_out']} outside "
                  f"follower range · {st['merged']} duplicates merged · {st['failed']} failed[/dim]")
    if not leads:
        console.print("[yellow]No leads. The search engine may be blocking requests; try again later "
                      "or loosen the query.[/yellow]")
        return None
    table = Table(box=None, padding=(0, 2), pad_edge=False)
    for col in ("Score", "Platforms", "Name", "Followers", "Email"):
        table.add_column(col)
    for l in leads[:15]:
        table.add_row(str(l.get('quality_score', l.get('lead_score', 0))),
                      ', '.join(l.get('platforms') or [l.get('platform', '')]),
                      (l.get('full_name') or l.get('username') or '')[:28],
                      f"{l.get('total_reach', l.get('follower_count', 0)):,}" + ("?" if l.get('followers_unknown') else ""),
                      l.get('email', '') or "-")
    console.print(table)
    console.print("[dim]Score reasons are in the score_explain column of the CSV.[/dim]")
    path = export_csv(leads)
    console.print(f"\n[{ACCENT}]✓[/{ACCENT}] {len(leads)} leads saved to [bold]{path}[/bold]")
    return path


def find_leads_interactive():
    """Describe the leads you want in plain English."""
    _platform_header("Find Leads", "e.g. yoga studio owners in Austin with 5k+ followers on instagram")
    query = Prompt.ask(f"[{ACCENT}]Who are you looking for?[/{ACCENT}]").strip()
    if query:
        _run_find(query, limit=10)


def lead_from_url_interactive():
    """Paste any profile or page URL and get a normalized lead."""
    _platform_header("Lead from URL", "profile links use the platform scraper, other pages use generic extraction")
    url = Prompt.ask(f"[{ACCENT}]URL[/{ACCENT}]").strip()
    if not url:
        return
    with console.status("Fetching..."):
        out, res = _lead_json(url)
    if not out:
        console.print("[red]✗ No lead found (blocked page, nothing person-like on it, or not found).[/red]")
        return
    console.print(f"[dim]source: {res.source}  |  tier: {res.tier}[/dim]")
    console.print(out)


def scraper_health_interactive():
    """Which extraction tier served each platform recently, and what has been learned."""
    from app.healing.engine import get_cache
    from app.healing.report import summarize

    _platform_header("Scraper Health", "last 7 days")
    cache = get_cache()
    rows = summarize(cache.stats())
    if not rows:
        console.print("[dim]No runs recorded yet. Scrape something first.[/dim]")
        return

    colors = {'healthy': 'green', 'healing': 'yellow', 'broken': 'red', 'idle': 'dim'}
    table = Table(box=None, padding=(0, 2), pad_edge=False)
    for col in ("Platform", "Status", "Runs", "Own parser", "Healed", "Failed", "Learned selectors"):
        table.add_column(col)
    for r in rows:
        learned = len(cache.selectors(r['platform']))
        table.add_row(r['platform'], f"[{colors[r['status']]}]{r['status']}[/{colors[r['status']]}]",
                      str(r['total']), f"{r['primary_rate']}%", str(r['healed']), str(r['failed']), str(learned))
    console.print(table)
    console.print()
    console.print("[dim]healing = own parser failing, backup tiers serving leads. "
                  "broken = nothing worked. Set OPENSCRAPPER_LLM to let the LLM tier repair broken platforms.[/dim]")


def main():
    _update_thread = _start_update_check()
    console.clear()
    _update_thread.join(timeout=3.0)
    show_header()

    latest = _update_cache.get("latest")
    if latest:
        console.print()
        console.print(Panel(
            f"[bold white]OpenScrapper v{latest} is available.[/bold white]\n"
            f"[dim]You are running v{__version__}. Please update before continuing.[/dim]\n\n"
            f"[{ACCENT}]git pull origin main[/{ACCENT}]  [dim]or visit[/dim]  [{ACCENT}]github.com/ayushks1ngh/OpenScapper[/{ACCENT}]",
            border_style=ACCENT,
            title="[bold white]Update Required[/bold white]",
            padding=(1, 3),
        ))
        console.print()
        sys.exit(1)

    while True:
        show_menu()

        try:
            choice = Prompt.ask(
                f"[{ACCENT}]>[/{ACCENT}]",
                choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"],
                default="1",
                show_choices=False
            )

            if choice == '0':
                console.clear()
                console.print()
                console.print(Rule(style=ACCENT_DIM))
                console.print(
                    f"  [bold {ACCENT}]Thanks for using OpenScrapper[/bold {ACCENT}]  "
                    "[dim]★ github.com/ayushks1ngh/OpenScapper[/dim]"
                )
                console.print()
                break

            console.clear()

            if choice == '1':
                scrape_instagram_interactive()
            elif choice == '2':
                scrape_tiktok_interactive()
            elif choice == '3':
                scrape_linkedin_interactive()
            elif choice == '4':
                scrape_github_interactive()
            elif choice == '5':
                scrape_youtube_interactive()
            elif choice == '6':
                scrape_twitch_interactive()
            elif choice == '7':
                scrape_linktree_interactive()
            elif choice == '8':
                scrape_pinterest_interactive()
            elif choice == '9':
                scrape_from_file()
            elif choice == '10':
                view_exports()
            elif choice == '11':
                settings_menu()
            elif choice == '12':
                smart_scrape_interactive()
            elif choice == '13':
                scraper_health_interactive()
            elif choice == '14':
                lead_from_url_interactive()
            elif choice == '15':
                find_leads_interactive()

            _pause()
            console.clear()
            show_header()

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Exiting...[/yellow]")
            break
        except EOFError:
            console.print("\n[yellow]No more input, exiting.[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")


if __name__ == '__main__':
    if _args and _args[0].lower() == 'lead':
        if len(_args) < 2:
            print("Usage: python openscrapper.py lead <url>")
            sys.exit(2)
        _out, _res = _lead_json(_args[1])
        if not _out:
            print("No lead found.", file=sys.stderr)
            sys.exit(1)
        print(_out)
        sys.exit(0)
    if _args and _args[0].lower() == 'find':
        _rest = _args[1:]
        _limit = 10
        if '--limit' in _rest:
            _i = _rest.index('--limit')
            try:
                _limit = max(1, int(_rest[_i + 1]))
            except (IndexError, ValueError):
                print("--limit needs a number")
                sys.exit(2)
            del _rest[_i:_i + 2]
        if not _rest:
            print('Usage: python openscrapper.py find "<query>" [--limit N]')
            sys.exit(2)
        sys.exit(0 if _run_find(' '.join(_rest), _limit, confirm=False) else 1)
    main()
