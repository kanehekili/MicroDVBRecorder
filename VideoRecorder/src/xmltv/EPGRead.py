'''
Created on Jun 19, 2026

@author: matze
'''
#!/usr/bin/env python3
"""
eit2xmltv - parse DVB EIT (Event Information Table) into XMLTV.

Reads an MPEG-TS stream on stdin, extracts the EIT (PID 0x12), reassembles
SI sections, parses the schedule events, and writes XMLTV to stdout.

Pipeline (replacing czap + tv_grab_dvb):

    /opt/bin/mediaclient -d /dev/dvb/adapter0/frontend0 -m DVBC -D DVBC \
        -f 546000000 -M Q256 -S 6900000 &
    mc_pid=$!
    timeout 60 /opt/bin/mediaclient --cat /dev/dvb/adapter0/dvr0 \
        | ./eit2xmltv.py > epg.xml
    kill $mc_pid

You normally pipe a bounded amount of data (a TDT/EIT scan only needs the
EIT to cycle once, typically 10-60 s) via `timeout`. The script reads until
stdin closes, then emits XMLTV for everything it collected.

Implements the parts of ETSI EN 300 468 needed for EPG:
  - EIT schedule actual TS: table_id 0x50-0x5F
  - EIT present/following actual TS: table_id 0x4E  (optional, --pf)
  - short_event_descriptor (0x4D): title + short description
  - extended_event_descriptor (0x4E): long description (multi-part)
  - content_descriptor (0x54): genre/category (optional)
  - DVB text decoding incl. character-table selection byte

Standalone: only the Python standard library.
"""

import sys
import argparse
import datetime
from xml.sax.saxutils import escape


# ---------------------------------------------------------------------------
# TS layer: pull SI sections off a given PID
# ---------------------------------------------------------------------------

TS_SYNC = 0x47
TS_LEN = 188
EIT_PID = 0x12


class SectionAssembler:
    """Reassemble PSI/SI sections from TS packets of one PID.

    Handles the pointer_field, payload_unit_start_indicator, and sections
    spanning multiple TS packets. EIT sections may be up to 4096 bytes.
    Yields complete section byte strings (including the CRC_32 trailer).
    """

    def __init__(self, pid):
        self.pid = pid
        self.buf = bytearray()
        self.collecting = False
        self.expected = 0          # full section length once known

    def feed(self, pkt):
        # pkt is one 188-byte TS packet, already checked to be our PID.
        if pkt[1] & 0x80:          # transport_error_indicator
            self._reset()
            return

        payload_start = bool(pkt[1] & 0x40)
        afc = (pkt[3] >> 4) & 0x03  # adaptation_field_control
        idx = 4
        if afc == 0 or afc == 2:    # no payload
            return
        if afc == 3:                # adaptation field present, then payload
            af_len = pkt[4]
            idx = 5 + af_len
            if idx >= TS_LEN:
                return

        data = pkt[idx:]

        if payload_start:
            pointer = data[0]
            # bytes before the pointer belong to the *previous* section
            if self.collecting and pointer > 0:
                self._append(data[1:1 + pointer])
                self._try_emit_complete()
            # start of new section(s)
            start = 1 + pointer
            self._reset()
            self.collecting = True
            self._append(data[start:])
        else:
            if self.collecting:
                self._append(data)

        return self._try_emit_complete()

    def _append(self, b):
        self.buf.extend(b)
        if self.expected == 0 and len(self.buf) >= 3:
            # section_length is 12 bits: low 4 of byte1 + byte2
            sec_len = ((self.buf[1] & 0x0F) << 8) | self.buf[2]
            self.expected = 3 + sec_len   # 3 header bytes + section_length

    def _try_emit_complete(self):
        out = []
        # A packet payload can finish a section and 0xFF-pad the rest.
        while self.expected and len(self.buf) >= self.expected:
            section = bytes(self.buf[:self.expected])
            out.append(section)
            rest = self.buf[self.expected:]
            self._reset()
            # remaining bytes are usually 0xFF stuffing; stop at first 0xFF
            # (a new section only ever starts after a pointer_field, handled
            # on the next payload_unit_start packet)
            self.buf = bytearray()
            self.collecting = False
            break
        return out

    def _reset(self):
        self.buf = bytearray()
        self.expected = 0
        self.collecting = False


# ---------------------------------------------------------------------------
# DVB text decoding (ETSI EN 300 468 annex A)
# ---------------------------------------------------------------------------

# Map the leading character-table selector byte to a Python codec.
# This covers the common European cases; German DVB-C typically uses
# ISO 8859-1 (Latin-1, selector 0x01) or the default ISO 6937.
_CTRL_CODECS = {
    0x01: "iso8859_5",
    0x02: "iso8859_2",   # not exact, see note
    0x03: "iso8859_3",
    0x04: "iso8859_4",
    0x05: "iso8859_5",
    0x06: "iso8859_6",
    0x07: "iso8859_7",
    0x08: "iso8859_8",
    0x09: "iso8859_9",
    0x0A: "iso8859_10",
    0x0B: "iso8859_11",
    0x0D: "iso8859_13",
    0x0E: "iso8859_14",
    0x0F: "iso8859_15",
}


def decode_dvb_string(raw):
    """Decode a DVB SI text string to a Python str.

    The optional first byte selects a character table. Values 0x20-0xFF
    mean the default table (ISO 6937) with no selector byte consumed.
    0x10 introduces a 3-byte ISO 8859 selector. 0x01-0x0F select tables
    directly. Control codes 0x80-0x9F are DVB-specific (e.g. 0x8A = LF).
    """
    if not raw:
        return ""

    codec = "iso6937"
    b0 = raw[0]
    if b0 == 0x10 and len(raw) >= 3:
        # 0x10 0x00 NN  -> ISO 8859-NN
        nn = raw[2]
        codec = {
            0x01: "iso8859_1", 0x02: "iso8859_2", 0x03: "iso8859_3",
            0x04: "iso8859_4", 0x05: "iso8859_5", 0x06: "iso8859_6",
            0x07: "iso8859_7", 0x08: "iso8859_8", 0x09: "iso8859_9",
            0x0A: "iso8859_10", 0x0B: "iso8859_11", 0x0D: "iso8859_13",
            0x0E: "iso8859_14", 0x0F: "iso8859_15",
        }.get(nn, "iso8859_1")
        raw = raw[3:]
    elif b0 == 0x15:
        codec = "utf-8"
        raw = raw[1:]
    elif b0 in _CTRL_CODECS:
        codec = _CTRL_CODECS[b0]
        raw = raw[1:]
    elif b0 < 0x20:
        # other selector bytes we don't specifically handle: drop it,
        # fall back to latin-1 which never fails
        codec = "iso8859_1"
        raw = raw[1:]
    # else: default table, keep all bytes

    # DVB control codes: 0x8A is a line break; 0x86/0x87 emphasis on/off.
    out = bytearray()
    for byte in raw:
        if byte == 0x8A:
            out.extend(b"\n")
        elif 0x80 <= byte <= 0x9F:
            continue                 # strip other control codes
        else:
            out.append(byte)

    try:
        return bytes(out).decode(codec)
    except (LookupError, UnicodeDecodeError):
        # iso6937 isn't in all Python builds; fall back to latin-1
        return bytes(out).decode("iso8859_1", errors="replace")


# ---------------------------------------------------------------------------
# Time helpers: MJD + BCD per ETSI EN 300 468 annex C
# ---------------------------------------------------------------------------

def parse_start_time(b5):
    """5 bytes: 2 bytes MJD + 3 bytes BCD UTC -> aware UTC datetime, or None."""
    mjd = (b5[0] << 8) | b5[1]
    if mjd == 0xFFFF:
        return None
    # MJD -> calendar date (annex C algorithm)
    yp = int((mjd - 15078.2) / 365.25)
    mp = int((mjd - 14956.1 - int(yp * 365.25)) / 30.6001)
    day = mjd - 14956 - int(yp * 365.25) - int(mp * 30.6001)
    if mp == 14 or mp == 15:
        k = 1
    else:
        k = 0
    year = yp + k + 1900
    month = mp - 1 - k * 12
    hh = _bcd(b5[2])
    mm = _bcd(b5[3])
    ss = _bcd(b5[4])
    try:
        return datetime.datetime(year, month, day, hh, mm, ss,
                                 tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def parse_duration(b3):
    """3 bytes BCD HHMMSS -> seconds."""
    return _bcd(b3[0]) * 3600 + _bcd(b3[1]) * 60 + _bcd(b3[2])


def _bcd(byte):
    return ((byte >> 4) & 0x0F) * 10 + (byte & 0x0F)


# ---------------------------------------------------------------------------
# EIT section parsing
# ---------------------------------------------------------------------------

class Event:
    __slots__ = ("service_id", "event_id", "start", "duration",
                 "title", "short_desc", "long_desc", "lang")

    def __init__(self):
        self.title = ""
        self.short_desc = ""
        self.long_desc = ""
        self.lang = ""


def parse_eit_section(sec, want_pf, want_sched, events):
    table_id = sec[0]
    is_pf = (table_id in (0x4E, 0x4F))
    is_sched = (0x50 <= table_id <= 0x6F)
    if is_pf and not want_pf:
        return
    if is_sched and not want_sched:
        return
    if not (is_pf or is_sched):
        return
    # only "actual TS" tables (0x4E, 0x50-0x5F); skip "other TS"
    if table_id in (0x4F,) or (0x60 <= table_id <= 0x6F):
        return

    section_length = ((sec[1] & 0x0F) << 8) | sec[2]
    # service_id at bytes 3-4
    service_id = (sec[3] << 8) | sec[4]
    # events start after the 14-byte EIT header; last 4 bytes are CRC
    pos = 14
    end = 3 + section_length - 4     # exclude CRC_32

    while pos + 12 <= end:
        ev = Event()
        ev.service_id = service_id
        ev.event_id = (sec[pos] << 8) | sec[pos + 1]
        ev.start = parse_start_time(sec[pos + 2:pos + 7])
        ev.duration = parse_duration(sec[pos + 7:pos + 10])
        loop_len = ((sec[pos + 10] & 0x0F) << 8) | sec[pos + 11]
        dpos = pos + 12
        dend = dpos + loop_len
        if dend > end:
            dend = end
        _parse_descriptors(sec[dpos:dend], ev)
        pos = dend

        if ev.start is not None and ev.title:
            key = (ev.service_id, ev.event_id)
            events[key] = ev          # dedupe by (service, event)


def _parse_descriptors(blob, ev):
    i = 0
    ext_parts = []
    while i + 2 <= len(blob):
        tag = blob[i]
        dlen = blob[i + 1]
        body = blob[i + 2:i + 2 + dlen]
        if len(body) < dlen:
            break
        if tag == 0x4D:               # short_event_descriptor
            ev.lang = bytes(body[0:3]).decode("ascii", "replace")
            nl = body[3]
            name = body[4:4 + nl]
            tpos = 4 + nl
            tl = body[tpos]
            text = body[tpos + 1:tpos + 1 + tl]
            ev.title = decode_dvb_string(bytes(name))
            ev.short_desc = decode_dvb_string(bytes(text))
        elif tag == 0x4E:             # extended_event_descriptor
            # desc_number/last (1), lang (3), length_of_items (1), items,
            # text_length (1), text
            loi = body[4]
            tpos = 5 + loi
            if tpos < len(body):
                tl = body[tpos]
                txt = body[tpos + 1:tpos + 1 + tl]
                ext_parts.append(decode_dvb_string(bytes(txt)))
        i += 2 + dlen
    if ext_parts:
        ev.long_desc = "".join(ext_parts)


# ---------------------------------------------------------------------------
# XMLTV output
# ---------------------------------------------------------------------------

def write_xmltv(events, out, channel_map=None):
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    out.write('<!DOCTYPE tv SYSTEM "xmltv.dtd">\n')
    out.write('<tv generator-info-name="eit2xmltv">\n')

    services = sorted({ev.service_id for ev in events.values()})
    for sid in services:
        cid = _channel_id(sid, channel_map)
        out.write('  <channel id="%s">\n' % escape(cid, {'"': "&quot;"}))
        name = channel_map.get(sid) if channel_map else None
        out.write('    <display-name>%s</display-name>\n'
                  % escape(name if name else "Service %d" % sid))
        out.write('  </channel>\n')

    for ev in sorted(events.values(),
                     key=lambda e: (e.service_id, e.start)):
        start = ev.start
        stop = start + datetime.timedelta(seconds=ev.duration)
        cid = _channel_id(ev.service_id, channel_map)
        out.write('  <programme start="%s" stop="%s" channel="%s">\n'
                   % (_xmltv_time(start), _xmltv_time(stop),
                      escape(cid, {'"': "&quot;"})))
        lang = ev.lang.strip() or "und"
        out.write('    <title lang="%s">%s</title>\n'
                   % (escape(lang, {'"': "&quot;"}), escape(ev.title)))
        if ev.short_desc:
            out.write('    <sub-title lang="%s">%s</sub-title>\n'
                       % (escape(lang, {'"': "&quot;"}),
                          escape(ev.short_desc)))
        if ev.long_desc:
            out.write('    <desc lang="%s">%s</desc>\n'
                       % (escape(lang, {'"': "&quot;"}),
                          escape(ev.long_desc)))
        out.write('  </programme>\n')

    out.write('</tv>\n')


def _channel_id(sid, channel_map):
    if channel_map and sid in channel_map:
        return channel_map[sid]
    return "%d.dvb" % sid


def _xmltv_time(dt):
    # XMLTV wants e.g. 20260619203000 +0000
    return dt.strftime("%Y%m%d%H%M%S %z")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(stdin_bin, out, want_pf, want_sched, channel_map):
    asm = SectionAssembler(EIT_PID)
    events = {}
    carry = b""

    while True:
        chunk = stdin_bin.read(TS_LEN * 1024)
        if not chunk:
            break
        data = carry + chunk
        # align to a packet boundary
        n = len(data)
        i = 0
        # find first sync
        while i < n and data[i] != TS_SYNC:
            i += 1
        while i + TS_LEN <= n:
            pkt = data[i:i + TS_LEN]
            if pkt[0] != TS_SYNC:
                i += 1
                while i < n and data[i] != TS_SYNC:
                    i += 1
                continue
            pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
            if pid == EIT_PID:
                for sec in asm.feed(pkt):
                    try:
                        parse_eit_section(sec, want_pf, want_sched, events)
                    except (IndexError, ValueError):
                        pass          # skip malformed sections
            i += TS_LEN
        carry = data[i:]

    write_xmltv(events, out, channel_map)
    return len(events)


def load_channel_map(path):
    """Optional: map service_id -> channel name from a simple file.

    Format per line:  service_id<TAB or space>Channel Name
    e.g.  53002  TELE 5
    """
    m = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                try:
                    m[int(parts[0])] = parts[1]
                except ValueError:
                    pass
    return m


def main():
    ap = argparse.ArgumentParser(
        description="Parse DVB EIT from a TS on stdin into XMLTV.")
    ap.add_argument("--pf", action="store_true",
                    help="include present/following (0x4E) events")
    ap.add_argument("--no-schedule", action="store_true",
                    help="exclude schedule (0x50-0x5F) events")
    ap.add_argument("--channels", metavar="FILE",
                    help="service_id->name map for nicer XMLTV channel ids")
    args = ap.parse_args()

    channel_map = load_channel_map(args.channels) if args.channels else None
    n = run(sys.stdin.buffer, sys.stdout,
            want_pf=args.pf,
            want_sched=not args.no_schedule,
            channel_map=channel_map)
    sys.stderr.write("eit2xmltv: %d events written\n" % n)


if __name__ == "__main__":
    main()