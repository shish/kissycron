#!/usr/bin/env python3
import argparse
import logging
import os
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Backup files/directories using rsync")
    parser.add_argument(
        "sources",
        nargs="+",
        help="Source file(s) or directory(ies) to backup",
    )
    parser.add_argument(
        "destination",
        help="Destination directory",
    )
    parser.add_argument(
        "--mkdir",
        action="store_true",
        help="Create destination directory if it doesn't exist",
    )

    args = parser.parse_args()

    destination = args.destination

    if args.mkdir and not os.path.exists(destination):
        try:
            os.makedirs(destination, exist_ok=True)
            logger.info(f"Created destination directory: {destination}")
        except Exception as e:
            logger.error(f"Failed to create destination directory {destination}: {e}")
            sys.exit(1)

    logger.info(f"Starting backup of {len(args.sources)} source(s) to {destination}")

    rsync_cmd = ["rsync", "-av"]

    backup_uid = os.environ.get("BACKUP_UID")
    backup_gid = os.environ.get("BACKUP_GID")

    if backup_uid and backup_gid:
        rsync_cmd.append(f"--chown={backup_uid}:{backup_gid}")

    rsync_cmd.extend(args.sources)
    rsync_cmd.append(destination)

    try:
        subprocess.run(rsync_cmd, check=True)
        logger.info("All backups completed successfully")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed (exit code {e.returncode})")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backup failed (error: {e})")
        sys.exit(1)


if __name__ == "__main__":
    main()
