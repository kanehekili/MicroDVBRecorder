# DVB-C Recording / EPG — Architecture Notes

Context for continuing work on the Raspberry Pi 4 DVB-C recording system.
These notes capture findings from debugging sessions and explain *why*
the architecture changed, so the reasoning isn't lost.

## Hardware / environment

- Raspberry Pi 4, Arch Linux ARM (armv7h), kernel `6.12.56-1-rpi`
  (6.18 is installed but does not boot — pinned to 6.12 for now).
- Tuner: **Sundtek MediaTV Pro III (EU)**, USB id `2659:1210`.
- Sundtek is a **proprietary userspace stack**, not a kernel DVB driver:
  - daemon `mediasrv` (started via `sundtek.service`)
  - client `/opt/bin/mediaclient`
  - `LD_PRELOAD=/opt/lib/libmediaclient.so` intercepts DVB API calls and
    redirects them to the daemon. This **must be exported** by the parent
    process; recording subprocesses inherit it. Without it, opening
    `/dev/dvb/adapter0/frontend0` fails with ENXIO (`No such device or
    address`), because calls hit the bare kernel node instead of Sundtek.
- DVB-C provider: Vodafone (Germany). Text encoding is Latin-1 / ISO 6937.

## What broke and why

The system ran ~15 years (Cubieboard1 → Pi 4) using:
  - `czap -r -p "<channel>"` to tune and set up dvr0 recording
  - `cat /dev/dvb/adapter0/dvr0 > file` to capture
  - `czap -x -n "<channel>"` + `tv_grab_dvb` to harvest EPG

After a Sundtek reinstall (2025-11-02) recording produced only a TS header
and no data. Root causes established by testing:

1. **`czap -r -p` is dead on this Sundtek version.** czap discovers the PMT
   via a demux *section* filter read, which now returns EAGAIN
   (`read_sections: read error: Resource temporarily unavailable` →
   `couldn't find pmt-pid`). Even `czap -r` without `-p` reads **nothing**
   from dvr0 (8 KiB header only). czap can no longer get data off dvr0.

2. **The device auto-sleeps.** `mediaclient -e` shows `STATUS: STANDBY`.
   The frontend only wakes when a `mediaclient` tune command addresses it.
   A tune command that exits lets it fall back to STANDBY. So a reader needs
   a **separate tune process kept alive** to hold the device ACTIVE.

3. **`--tsprogram` is throttled.** Sundtek's own per-program filter delivers
   only ~258 KiB/s (~2 Mb/s) vs ~45 MiB/s for the raw multiplex on the same
   stream, causing bitstream-sync loss and blocking artefacts. This is a
   **driver bug**; reported to Sundtek (they have the raw file). Do not rely
   on `--tsprogram` until they confirm a fix.

Signal is perfect (99%, BER 0, CNR ~36.5 dB) — none of this is RF related.

## The working architecture (current)

**Two processes, always.** One tunes and stays alive (holds device ACTIVE),
a separate process reads the full multiplex via `--cat`:

```
mediaclient -d /dev/dvb/adapter0/frontend0 -m DVBC -D DVBC \
    -f <freq_hz> -M Q<mod> -S <symrate> &     # process 1: TUNER, background
mediaclient --cat /dev/dvb/adapter0/dvr0 \    # process 2: READER (+ filter)
    | <filter> > out.ts
```

- The `-D DVBC` (set DTV mode) and explicit `-d frontend0` matter; without
  them throughput/behaviour is wrong. This matches Sundtek's documented
  two-command pattern.
- `--cat` delivers the **entire transponder** at full bitrate, clean.
- Filtering down to one program is done by our own tools (below).
- **`mediaclient --cat` ignores SIGPIPE.** When the downstream filter exits,
  `--cat` does not die. A plain shell pipeline (`--cat | filter`) therefore
  hangs bash waiting for `--cat` to exit. Fix: use a named FIFO so `--cat`
  runs as a tracked background process and can be killed explicitly.
- On teardown, kill ALL three pids (tuner, `--cat`, filter). The Sundtek
  daemon often tears down the tuner automatically when the reader closes,
  so `kill $mc` may report "no such process" — that is normal and harmless.

## Custom tools (replace czap path and tv_grab_dvb)

### `tspidfilter` (C, zero deps) — program filtering + PAT/PMT rewriting

Replaces `czap -r -p` (dead) and `--tsprogram` (throttled). Reads TS on
stdin, writes a clean **single-program** TS to stdout.

**Two calling conventions** (auto-detected by value range, PIDs ≤ 8191):

```bash
# Service-id mode (value > 8191): discovers PMT and all ES PIDs automatically
mediaclient --cat /dev/dvb/adapter0/dvr0 | tspidfilter 53002 > tele5.m2t

# ES-PID mode (values ≤ 8191): scans PMTs until one containing a wanted PID is found
mediaclient --cat /dev/dvb/adapter0/dvr0 | tspidfilter 411 412 > tele5.m2t
```

In both modes the tool:
- Reads the PAT (PID 0) to discover all (service_id, PMT_PID) pairs.
- Identifies the PMT that owns the requested program.
- Rewrites every PAT packet to list **only** the matched program (valid
  single-program TS; mediainfo, ffprobe, and strict players see streams).
- Passes the matched PMT through unchanged.
- Passes wanted ES PIDs through.

**Duration flag `-t <seconds>`**: tspidfilter exits after the given number
of seconds of *actual output*. The timer starts on the **first output
packet** (i.e. after PMT discovery / tuner lock), not at process start.
When tspidfilter exits the named FIFO closes, the caller kills `--cat`
explicitly (see `mediaClientRecord.sh`).

**Error handling**: if the service_id is not found in the PAT, tspidfilter
prints an error to stderr and exits with code 1 immediately, ignoring `-t`.
This prevents the recording daemon from hanging indefinitely on a bad
service_id.

```bash
# stderr on error:
tspidfilter: service_id 53627 not found in PAT
```

**Build on the Pi:**
```bash
gcc -O2 -o tspidfilter tspidfilter.c
```
No dependencies. Fine under GCC 16.

**Note on service_ids in channels.conf**: service_ids can go stale when
providers reorganise their multiplexes. 

Until channels.conf is rescanned, use ES-PID mode for affected channels.

### `EPGRead.py` (Python 3, stdlib only) — replaces tv_grab_dvb

Reads TS on stdin, extracts EIT (PID 0x12), reassembles SI sections, parses
the schedule, emits XMLTV. Implements the EN 300 468 subset needed for EPG:
EIT schedule (0x50–0x5F) + optional present/following (0x4E, `--pf`),
short_event_descriptor (0x4D), extended_event_descriptor (0x4E, multi-part),
MJD+BCD time, DVB text decoding incl. charset-selector byte.

```bash
mediaclient -d /dev/dvb/adapter0/frontend0 -m DVBC -D DVBC \
    -f 546000000 -M Q256 -S 6900000 &
mc=$!
timeout 60 mediaclient --cat /dev/dvb/adapter0/dvr0 \
    | ./EPGRead.py --channels channels.map > epg.xml
kill $mc; killall mediaclient
```

`channels.map`: one `service_id<space>Name` per line, used for XMLTV channel
ids/names.

Known limits / things real-stream testing may surface:
- Parses **actual-TS** EIT only (the tuned transponder). For full EPG, loop
  over transponders and merge the XMLTV outputs.
- Char encoding: German DVB-C is usually Latin-1; the ISO 6937 path falls
  back to Latin-1 if Python lacks the `iso6937` codec.
- Section CRC is **not** validated (kept dependency-free).
- Schedule EIT for several days needs a longer `--cat` window (~30–120 s).

## Recording script (`mediaClientRecord.sh`)

Called by `MediaClientCommand` in the Python daemon. Parameters:
`durance freq qam symbolrate service_id target`

Key design points:
- Uses a **named FIFO** (`/tmp/dvb_XXXXXX`) instead of a shell pipeline,
  so that `mediaclient --cat` runs as a tracked background process with a
  known PID and can be killed explicitly on teardown.
- `tspidfilter -t "$durance" "$service_id"` runs in background; `wait
  $filter_pid` blocks until it exits. `wait` is interruptible by SIGTERM,
  so the daemon can kill the script and the EXIT trap cleans up all three
  child processes.
- Duration timer starts after tuner lock (inside tspidfilter), absorbing
  the few seconds the Sundtek device takes to go ACTIVE.
- EXIT trap kills tuner (`$mc`), reader (`$cat_pid`), and filter
  (`$filter_pid`) on any exit path.

**Known issue**: currently passes `service_id` (channels.conf last field)
to tspidfilter. If the service_id is stale (not in PAT), tspidfilter exits
with code 1 and the daemon removes the job from the queue. A more robust
approach (next phase) is to pass video/audio PIDs instead.

## Daemon changes (`RecorderDaemon.py`)

- `_monitorCurrentRecording`: when the recording process exits with a
  **non-zero return code**, the job is now removed from the record queue
  via `cancelRecording(..., force=True)`. Previously the daemon would
  re-attempt the same job on the next loop iteration (the "preventing
  reschedule" log message was aspirational, not implemented).
- Normal completion (exit 0) and the "no data written" retry path are
  unchanged.

## Open / pending

- **channels.conf service_ids**: some may be stale (WELT 53627 confirmed
  stale 2026-06-19). Needs a rescan with `mediaclient --tsscan` per
  transponder to rebuild. Alternatively, switch daemon to ES-PID mode
  (next item).
- **Switch recording to ES-PID mode**: `ChannelReader.py` needs
  `getVideoPid()` / `getAudioPid()` (tokens[6] and [7] from channels.conf).
  `MediaClientCommand.getArguments()` and `mediaClientRecord.sh` need
  updating to pass PIDs instead of service_id. This makes recording robust
  against stale service_ids.
- **EPG integration**: `EPGRead.py` + `mediaClientRecord.sh` pattern wired
  into `DVBC_MediaClientGrabber` in `DVBDevice.py` (replaces old
  `mediaclient` + `tv_grab_dvb`). Needs a `channels.map` generated from
  channels.conf. Not yet implemented.
- **Sundtek `--tsprogram` throttling bug**: Understale investigating. No fix
  yet. `tspidfilter` sidesteps it entirely so there's little reason to
  switch back even if fixed.
- **`tsduck`** was considered as a filter but won't build under GCC 16
  (`-Werror=array-bounds` in libstdc++). The `-bin` AUR package is x86_64
  only. `tspidfilter` has no dependencies and builds everywhere.
