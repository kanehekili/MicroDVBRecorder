/*
 * tspidfilter - filter MPEG-TS by PID with automatic PAT/PMT rewriting
 *
 * Reads a transport stream on stdin, passes only the packets for a selected
 * program, and produces a clean single-program TS with a rewritten PAT.
 *
 * Usage:
 *   tspidfilter [-t <seconds>] <service_id>
 *   tspidfilter [-t <seconds>] <pid> [<pid> ...]
 *
 *   -t <seconds>  Stop after <seconds> of actual stream data.  The timer
 *                 starts when the first output packet is written (i.e. after
 *                 PMT discovery, when the tuner has locked).  Exiting closes
 *                 the pipe, which sends SIGPIPE to the upstream mediaclient
 *                 --cat process.
 *
 *   <service_id>  Value > 8191: service-id mode.  Discovers PMT PID from
 *                 the PAT, then gathers all ES PIDs from that PMT.
 *
 *   <pid> ...     Values <= 8191: ES-PID mode.  Scans candidate PMTs until
 *                 one containing a specified PID is found.
 *
 * PID 0 (PAT) is always kept and rewritten to list only the matched program.
 *
 * Example:
 *   mediaclient -d /dev/dvb/adapter0/frontend0 -m DVBC -D DVBC \
 *       -f 546000000 -M Q256 -S 6900000 &
 *   mc=$!
 *   mediaclient --cat /dev/dvb/adapter0/dvr0 | tspidfilter -t 120 53002 > out.m2t
 *   kill $mc
 *
 * Build:  gcc -O2 -o tspidfilter tspidfilter.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
#include <time.h>

#define TS_SYNC      0x47
#define TS_PACKET    188
#define MAX_PIDS     32
#define MAX_PROGS    64
#define BLOCK_PKTS   1024
#define BLOCK_BYTES  (BLOCK_PKTS * TS_PACKET)

/* ---------- duration ---------- */
static int want_duration = 0;          /* seconds; 0 = run until EOF */
static time_t start_time = 0;         /* set on first output packet */

/* ---------- mode and wanted IDs ---------- */
static int      sid_mode = 0;
static uint16_t want_sid = 0;
static uint16_t want_pid[MAX_PIDS];
static int      n_want   = 0;

/* ---------- program table ---------- */
static struct { uint16_t sid; uint16_t pmt_pid; } progs[MAX_PROGS];
static int      n_progs    = 0;
static int      pat_seen   = 0;
static int      fatal_error = 0;   /* set on unrecoverable errors; main loop exits */

/* ---------- matched program ---------- */
static uint16_t match_sid = 0;
static uint16_t match_pmt = 0xFFFF;

/* ---------- rewritten PAT ---------- */
static uint8_t original_pat[TS_PACKET];
static uint8_t rewritten_pat[TS_PACKET];
static int     have_rewritten_pat = 0;

/* ---------- CRC-32 (MPEG-2 / DVB, poly 0x04C11DB7) ---------- */
static uint32_t crc_table[256];

static void build_crc_table(void)
{
    int i, j;
    for (i = 0; i < 256; i++) {
        uint32_t c = (uint32_t)i << 24;
        for (j = 0; j < 8; j++)
            c = (c & 0x80000000u) ? ((c << 1) ^ 0x04C11DB7u) : (c << 1);
        crc_table[i] = c;
    }
}

static uint32_t crc32_dvb(const uint8_t *data, int len)
{
    uint32_t crc = 0xFFFFFFFFu;
    int i;
    for (i = 0; i < len; i++)
        crc = (crc << 8) ^ crc_table[((crc >> 24) ^ data[i]) & 0xFF];
    return crc;
}

/* ---------- I/O ---------- */
static ssize_t read_full(int fd, uint8_t *buf, size_t n)
{
    size_t got = 0;
    while (got < n) {
        ssize_t r = read(fd, buf + got, n - got);
        if (r < 0) { if (errno == EINTR) continue; return -1; }
        if (r == 0) break;
        got += (size_t)r;
    }
    return (ssize_t)got;
}

static int write_full(int fd, const uint8_t *buf, size_t n)
{
    size_t put = 0;
    while (put < n) {
        ssize_t w = write(fd, buf + put, n - put);
        if (w < 0) { if (errno == EINTR) continue; return -1; }
        put += (size_t)w;
    }
    return 0;
}

/* ---------- section start offset within a TS packet, or -1 ---------- */
static int section_offset(const uint8_t *pkt)
{
    uint8_t afc;
    int idx;

    if (!(pkt[1] & 0x40)) return -1;    /* PUSI not set */
    afc = (pkt[3] >> 4) & 0x3;
    if (afc == 0 || afc == 2) return -1; /* no payload */
    idx = 4;
    if (afc == 3) { idx += 1 + pkt[4]; if (idx >= TS_PACKET) return -1; }
    idx += 1 + pkt[idx];                /* pointer_field */
    if (idx >= TS_PACKET) return -1;
    return idx;
}

/* ---------- build rewritten PAT (single-program) ---------- */
static void build_rewritten_pat(void)
{
    int      idx, fill;
    uint32_t crc;
    uint8_t *sec;

    memcpy(rewritten_pat, original_pat, TS_PACKET);
    idx = section_offset(rewritten_pat);
    if (idx < 0) return;
    sec = rewritten_pat + idx;

    sec[1] = (sec[1] & 0xF0) | 0x00;
    sec[2] = 13;                         /* section_length */

    sec[8]  = (match_sid  >> 8) & 0xFF;
    sec[9]  =  match_sid        & 0xFF;
    sec[10] = 0xE0 | ((match_pmt >> 8) & 0x1F);
    sec[11] =  match_pmt        & 0xFF;

    crc     = crc32_dvb(sec, 12);
    sec[12] = (crc >> 24) & 0xFF;
    sec[13] = (crc >> 16) & 0xFF;
    sec[14] = (crc >>  8) & 0xFF;
    sec[15] =  crc        & 0xFF;

    fill = idx + 3 + 13;
    if (fill < TS_PACKET)
        memset(rewritten_pat + fill, 0xFF, TS_PACKET - fill);

    have_rewritten_pat = 1;
}

/* ---------- parse PAT ---------- */
static void parse_pat(const uint8_t *pkt)
{
    int i, idx;
    const uint8_t *sec;
    int entry_end;

    idx = section_offset(pkt);
    if (idx < 0) return;
    sec = pkt + idx;
    if (sec[0] != 0x00) return;

    entry_end = 3 + (int)(((sec[1] & 0x0F) << 8) | sec[2]) - 4;
    n_progs   = 0;

    for (i = 8; i + 4 <= entry_end; i += 4) {
        uint16_t sid     = ((uint16_t)sec[i]     << 8) | sec[i + 1];
        uint16_t pmt_pid = (((uint16_t)sec[i + 2] & 0x1F) << 8) | sec[i + 3];
        if (sid == 0) continue;
        if (n_progs < MAX_PROGS) {
            progs[n_progs].sid     = sid;
            progs[n_progs].pmt_pid = pmt_pid;
            n_progs++;
        }
    }
    memcpy(original_pat, pkt, TS_PACKET);
    pat_seen = 1;

    if (sid_mode) {
        for (i = 0; i < n_progs; i++) {
            if (progs[i].sid == want_sid) {
                match_sid = want_sid;
                match_pmt = progs[i].pmt_pid;
                return;
            }
        }
        fprintf(stderr, "tspidfilter: service_id %u not found in PAT\n",
                (unsigned)want_sid);
        fatal_error = 1;
    }
}

/* ---------- parse PMT and complete the match ---------- */
static void try_parse_pmt(const uint8_t *pkt, uint16_t pid)
{
    int i, idx, epos, found = 0;
    const uint8_t *sec;
    uint16_t this_sid = 0, entry_end, prog_info_len;

    for (i = 0; i < n_progs; i++) {
        if (progs[i].pmt_pid == pid) { this_sid = progs[i].sid; break; }
    }
    if (!this_sid) return;

    idx = section_offset(pkt);
    if (idx < 0) return;
    sec = pkt + idx;
    if (sec[0] != 0x02) return;

    entry_end     = 3 + (int)(((sec[1] & 0x0F) << 8) | sec[2]) - 4;
    if (entry_end < 12) return;
    prog_info_len = ((sec[10] & 0x0F) << 8) | sec[11];
    epos          = 12 + (int)prog_info_len;

    if (sid_mode) {
        if (this_sid != want_sid) return;
        n_want = 0;
        while (epos + 5 <= (int)entry_end) {
            uint16_t es_pid      = (((uint16_t)sec[epos+1] & 0x1F) << 8) | sec[epos+2];
            uint16_t es_info_len = (((uint16_t)sec[epos+3] & 0x0F) << 8) | sec[epos+4];
            if (n_want < MAX_PIDS) want_pid[n_want++] = es_pid;
            epos += 5 + (int)es_info_len;
        }
        found = 1;
    } else {
        while (epos + 5 <= (int)entry_end) {
            uint16_t es_pid      = (((uint16_t)sec[epos+1] & 0x1F) << 8) | sec[epos+2];
            uint16_t es_info_len = (((uint16_t)sec[epos+3] & 0x0F) << 8) | sec[epos+4];
            for (i = 0; i < n_want; i++)
                if (want_pid[i] == es_pid) { found = 1; break; }
            epos += 5 + (int)es_info_len;
        }
        if (found) { match_sid = this_sid; match_pmt = pid; }
    }

    if (found) {
        build_rewritten_pat();
        fprintf(stderr, "tspidfilter: matched service_id=%u pmt_pid=%u es_pids=",
                (unsigned)match_sid, (unsigned)match_pmt);
        for (i = 0; i < n_want; i++)
            fprintf(stderr, i ? ",%u" : "%u", (unsigned)want_pid[i]);
        if (want_duration)
            fprintf(stderr, " duration=%ds", want_duration);
        fprintf(stderr, "\n");
    }
}

static int pid_wanted(uint16_t pid)
{
    int i;
    if (match_pmt != 0xFFFF && pid == match_pmt) return 1;
    for (i = 0; i < n_want; i++)
        if (want_pid[i] == pid) return 1;
    return 0;
}

/* ---------- main ---------- */
int main(int argc, char **argv)
{
    int     i;
    uint8_t *in, *out;
    uint8_t  carry[TS_PACKET];
    size_t   carry_len = 0;

    if (argc < 2) {
        fprintf(stderr,
            "usage: %s [-t seconds] <service_id>       (value > 8191)\n"
            "       %s [-t seconds] <pid> [<pid> ...]  (value <= 8191)\n",
            argv[0], argv[0]);
        return 2;
    }

    build_crc_table();

    /* parse options */
    i = 1;
    if (i < argc && strcmp(argv[i], "-t") == 0) {
        i++;
        if (i >= argc) { fprintf(stderr, "%s: -t requires a value\n", argv[0]); return 2; }
        want_duration = atoi(argv[i++]);
        if (want_duration <= 0) { fprintf(stderr, "%s: -t value must be > 0\n", argv[0]); return 2; }
    }

    /* parse PIDs / service_id */
    for (; i < argc; i++) {
        long v = strtol(argv[i], NULL, 0);
        if (v < 0 || v > 0xFFFF) {
            fprintf(stderr, "%s: value '%s' out of range\n", argv[0], argv[i]);
            return 2;
        }
        if (v > 0x1FFF) {
            if (sid_mode) { fprintf(stderr, "%s: only one service_id allowed\n", argv[0]); return 2; }
            sid_mode = 1;
            want_sid = (uint16_t)v;
        } else {
            if (sid_mode) { fprintf(stderr, "%s: cannot mix service_id and ES PIDs\n", argv[0]); return 2; }
            if (n_want < MAX_PIDS) want_pid[n_want++] = (uint16_t)v;
        }
    }

    in  = malloc(BLOCK_BYTES);
    out = malloc(BLOCK_BYTES);
    if (!in || !out) { fprintf(stderr, "%s: out of memory\n", argv[0]); return 1; }

    for (;;) {
        size_t  have, off, outlen;
        ssize_t r;

        if (carry_len) memcpy(in, carry, carry_len);
        r = read_full(0, in + carry_len, BLOCK_BYTES - carry_len);
        if (r < 0) {
            fprintf(stderr, "tspidfilter: read error: %s\n", strerror(errno));
            free(in); free(out); return 1;
        }
        have = carry_len + (size_t)r;
        carry_len = 0;
        if (have == 0) break;

        off = 0;
        while (off < have && in[off] != TS_SYNC) off++;

        outlen = 0;
        while (off + TS_PACKET <= have) {
            uint8_t *p = in + off;
            uint16_t pid;
            int      pusi;

            if (p[0] != TS_SYNC) {
                off++;
                while (off < have && in[off] != TS_SYNC) off++;
                continue;
            }

            pid  = (((uint16_t)p[1] & 0x1F) << 8) | p[2];
            pusi = (p[1] & 0x40) != 0;

            if (pid == 0x0000) {
                if (pusi && !pat_seen) {
                    parse_pat(p);
                    if (fatal_error) break;
                }
                if (have_rewritten_pat) {
                    rewritten_pat[3] = (rewritten_pat[3] & 0xF0) | (p[3] & 0x0F);
                    memcpy(out + outlen, rewritten_pat, TS_PACKET);
                    outlen += TS_PACKET;
                }
            } else {
                if (pusi && pat_seen && !have_rewritten_pat) {
                    if (!sid_mode && match_pmt == 0xFFFF) {
                        for (i = 0; i < n_progs; i++) {
                            if (progs[i].pmt_pid == pid) { try_parse_pmt(p, pid); break; }
                        }
                    } else if (sid_mode && match_pmt != 0xFFFF && pid == match_pmt) {
                        try_parse_pmt(p, pid);
                    }
                }
                if (pid_wanted(pid)) {
                    memcpy(out + outlen, p, TS_PACKET);
                    outlen += TS_PACKET;
                }
            }

            off += TS_PACKET;
        }

        if (off < have) {
            carry_len = have - off;
            if (carry_len > TS_PACKET) carry_len = 0;
            else memcpy(carry, in + off, carry_len);
        }

        if (fatal_error) break;

        if (outlen) {
            /* start the clock on the first byte of real output */
            if (want_duration && start_time == 0)
                start_time = time(NULL);

            if (write_full(1, out, outlen) < 0) {
                fprintf(stderr, "tspidfilter: write error: %s\n", strerror(errno));
                free(in); free(out); return 1;
            }

            if (want_duration && start_time &&
                    (time(NULL) - start_time) >= (time_t)want_duration)
                break;
        }
    }

    free(in); free(out);
    return fatal_error ? 1 : 0;
}
