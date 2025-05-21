#!/bin/bash

BOT_DIR="$HOME/Documents/overwatch-bot"
PID_FILE="$BOT_DIR/bot.pid"
VENV_DIR="$BOT_DIR/venv"
BOT_SCRIPT="$BOT_DIR/bot.py"

start_bot() {
    echo "Starting bot..."
    source "$VENV_DIR/bin/activate"
    nohup python3 "$BOT_SCRIPT" > "$BOT_DIR/bot.log" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Bot started with PID $(cat $PID_FILE)"
}

stop_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "Stopping bot with PID $PID..."
        kill "$PID" && rm "$PID_FILE"
        echo "Bot stopped."
    else
        echo "Bot is not running (no PID file found)."
    fi
}

status_bot() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "Bot is running (PID: $PID)"
        else
            echo "PID file exists but bot is not running."
        fi
    else
        echo "Bot is not running."
    fi
}

case "$1" in
    start) start_bot ;;
    stop) stop_bot ;;
    status) status_bot ;;
    restart)
        stop_bot
        sleep 1
        start_bot
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        ;;
esac
