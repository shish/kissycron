#!/bin/sh
echo "$(date '+%Y-%m-%d %H:%M:%S'): Starting backup of $1 to $2"

CHOWN_FLAG=""
if [ -n "$BACKUP_UID" ] && [ -n "$BACKUP_GID" ]; then
    CHOWN_FLAG="--chown=$BACKUP_UID:$BACKUP_GID"
fi

if rsync -av $CHOWN_FLAG "$1" "$2"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S'): Successfully backed up $1"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S'): FAILED to backup $1 (exit code $?)"
fi
