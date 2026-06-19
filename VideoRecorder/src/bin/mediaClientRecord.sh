#!/bin/bash
# Record a DVB-C channel using Sundtek mediaclient + tspidfilter.
# Parameters passed by MediaClientCommand.getArguments():
#   $1  durance     recording duration in seconds
#   $2  freq        frequency in Hz
#   $3  qam         modulation, e.g. Q256
#   $4  symbolrate  symbol rate in Hz
#   $5  service_id  DVB service_id (program number from channels.conf)
#   $6  target      output file path

durance=$1
freq=$2
qam=$3
symbolrate=$4
service_id=$5
target=$6

BINDIR="$(dirname "$0")"

# Named pipe so we can track the PID of mediaclient --cat independently.
# With a regular shell pipe, mediaclient --cat ignores SIGPIPE and keeps
# running when tspidfilter exits; we need to kill it explicitly.
FIFO=$(mktemp -u /tmp/dvb_XXXXXX)
mkfifo "$FIFO"

echo "Recording service_id:$service_id to \"$target\" for ${durance}s"

/opt/bin/mediaclient -d /dev/dvb/adapter0/frontend0 -m DVBC -D DVBC \
    -f "$freq" -M "$qam" -S "$symbolrate" > /dev/null &
mc=$!

sleep 1
if ! kill -0 "$mc" 2>/dev/null; then
    rm -f "$FIFO"
    echo "tuning failed" >&2
    exit 1
fi

/opt/bin/mediaclient --cat /dev/dvb/adapter0/dvr0 > "$FIFO" &
cat_pid=$!

"$BINDIR/tspidfilter" -t "$durance" "$service_id" < "$FIFO" > "$target" &
filter_pid=$!

cleanup() {
    kill "$mc" "$cat_pid" "$filter_pid" 2>/dev/null || true
    rm -f "$FIFO"
}
trap cleanup INT TERM EXIT

# wait is interruptible by SIGTERM: the daemon can kill this script and
# the trap will clean up all three child processes.
wait "$filter_pid"
echo "Recording done"
