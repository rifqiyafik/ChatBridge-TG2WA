import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
BAILEYS_ROOT = WORKSPACE_ROOT / "whatsapp-api"

TELEGRAM_PATTERNS = [
    "*.session",
    "*.session-journal",
]
WHATSAPP_SESSION_DIR = BAILEYS_ROOT / "auth_info"


def ensure_inside_workspace(path):
    resolved = path.resolve()
    if WORKSPACE_ROOT.resolve() not in (resolved, *resolved.parents):
        raise ValueError(f"Refusing to touch path outside workspace: {resolved}")
    return resolved


def collect_telegram_sessions():
    files = []
    for pattern in TELEGRAM_PATTERNS:
        files.extend(PROJECT_ROOT.glob(pattern))
    return sorted(set(files))


def collect_whatsapp_sessions():
    if WHATSAPP_SESSION_DIR.exists():
        return [WHATSAPP_SESSION_DIR]
    return []


def delete_path(path, dry_run):
    resolved = ensure_inside_workspace(path)
    if dry_run:
        print(f"DRY-RUN delete: {resolved}")
        return

    if resolved.is_dir():
        shutil.rmtree(resolved)
        print(f"Deleted directory: {resolved}")
        return

    resolved.unlink()
    print(f"Deleted file: {resolved}")


def reset(paths, dry_run):
    if not paths:
        print("No session files found.")
        return

    for path in paths:
        delete_path(path, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="Reset Telegram and/or WhatsApp session files for TG2WA."
    )
    parser.add_argument("--telegram", action="store_true", help="Reset Telegram .session files.")
    parser.add_argument("--whatsapp", action="store_true", help="Reset WhatsApp Baileys auth_info session.")
    parser.add_argument("--all", action="store_true", help="Reset Telegram and WhatsApp sessions.")
    parser.add_argument("--force", action="store_true", help="Actually delete files. Without this, only dry-run is shown.")
    args = parser.parse_args()

    reset_telegram = args.telegram or args.all
    reset_whatsapp = args.whatsapp or args.all

    if not reset_telegram and not reset_whatsapp:
        parser.error("Choose --telegram, --whatsapp, or --all.")

    dry_run = not args.force
    if dry_run:
        print("Dry-run mode. Add --force to delete the listed session files.")

    if reset_telegram:
        print("\nTelegram session reset target:")
        reset(collect_telegram_sessions(), dry_run)

    if reset_whatsapp:
        print("\nWhatsApp session reset target:")
        reset(collect_whatsapp_sessions(), dry_run)

    if not dry_run:
        print("\nReset complete. Start the apps again and login/scan QR with the new account.")


if __name__ == "__main__":
    main()
