#!/bin/sh
echo "$(date '+%Y-%m-%d %H:%M:%S'): Starting backup of $1 to $2"
if rsync -av "$1" "$2"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S'): Successfully backed up $1"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S'): FAILED to backup $1 (exit code $?)"
fi
