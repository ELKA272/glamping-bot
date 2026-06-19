#!/bin/bash
cd "$(dirname "$0")"
PID_FILE="bot.pid"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Бот уже запущен (PID: $OLD_PID)"
        exit 0
    fi
fi

nohup python3 bot.py > bot.log 2>&1 &
echo $! > "$PID_FILE"
echo "Бот запущен! PID: $(cat $PID_FILE)"
