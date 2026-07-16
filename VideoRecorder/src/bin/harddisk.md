# harddisk.sh

Disk-usage report for Samba shares. Answers the question: *which physical
disk backs each SMB share, and how full is it?*

## What it does

1. Reads the effective Samba configuration via `testparm -s` (so it works
   regardless of where `smb.conf` lives or what it includes).
2. Collects every share section (e.g. `[videos]`, `[recordings]`) together
   with its `path =` directory. The `[global]` section is skipped.
3. Runs `df -h` on each share path to determine the backing device and its
   size, used space, available space, and usage percentage.
4. Writes a sorted, aligned table to **stdout** and to `harddisk.txt` in the
   **current working directory**.

## Output

`harddisk.txt`, one line per share:

```
SMB-Name             Device                                Size   Used  Avail  Use%
recordings           /dev/sdb1                             1.8T   1.2T   600G   67%
videos               /dev/sda2                             932G   410G   522G   44%
```

Shares whose path cannot be resolved by `df` (e.g. the directory does not
exist) are silently omitted.

## Where to run it

On the machine that **exports the SMB shares** — for MicroDVBRecorder that
is the recorder box, whose recording disks are shared via Samba.

Running it on a machine without configured Samba shares (e.g. a desktop
client) produces only the header line, since `testparm` reports no share
sections there.

## When to use it

- Before scheduling recordings, to check whether the target disk has enough
  free space.
- Periodically via cron, so `harddisk.txt` always holds a fresh snapshot —
  e.g. to expose it over a share or have a UI pick it up:

  ```
  */15 * * * * cd /path/for/report && /path/to/harddisk.sh
  ```

  Note: because the output file is written relative to the working
  directory, `cd` to the desired location first (as above).

## Requirements

- `bash` (uses associative arrays, requires bash 4+)
- `samba` tools (`testparm`)
- `df` (coreutils)

No root privileges are needed as long as `testparm` can read the Samba
configuration (readable `smb.conf`).
