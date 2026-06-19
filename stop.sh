#!/bin/bash
cd "$(dirname "$0")"
if [ -f "bot.pid" ]; then
    kill $(cat "bot.pid") 2>/dev/null
    rm -f "bot.pid"
    echo "Бот остановлен."
else
    pkill -f "python3 bot.py" 2>/dev/null
    echo "Бот остановлен."
fi
