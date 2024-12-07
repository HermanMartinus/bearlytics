#!/bin/bash
set -e

export USER=bear
UID=${UID:-1000}
GID=${GID:-1000}
groupmod -o -g "$GID" $USER
usermod -o -u "$UID" $USER
chown -R $USER:$USER /app

exec su $USER -c "$@"

