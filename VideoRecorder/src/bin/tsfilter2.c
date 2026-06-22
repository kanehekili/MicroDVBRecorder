/*
 * tsfilter2 - filter MPEG-TS by PID with automatic PAT/PMT rewriting
 *
 * Drop-in replacement for tspidfilter with proper multi-packet PMT section
 * assembly.  tspidfilter parsed the PMT from the first TS packet only; if
 * the PMT section spans more than one TS packet (common for programs with
 * many streams and long descriptors) the ES PIDs in the second packet were
 * silently dropped from the output.
 *
 * Usage:
 *   tsfilter2 [-t <seconds>] <service_id>
 *   tsfilter2 [-t <seconds>] <pid> [<pid> ...]
 *
 *   -t <seconds>  Stop after <seconds> of actual stream data.
 *
 *   <service_id>  Value > 8191: service-id mode.  Discovers PMT PID from
 *                 the PAT, then gathers all ES PIDs from that PMT.
 *
 *   <pid> ...     Values <= 8191: ES-PID mode.  Scans candidate PMTs until
 *                 one containing a specified PID is found.
 *
 * Build:  gcc -O2 -o tsfilter2 tsfilter2.c
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
#define MAX_PIDS     64
#define MAX_PROGS    128
#define BLOCK_PKTS   1024
#define BLOCK_BYTES  (BLOCK_PKTS * TS_PACKET)

/* ---------- duration ---------- */
static int    want_duration = 0;
static time_t start_time   = 0;

/* ---------- mode and wanted IDs ---------- */
static int      sid_mode = 0;
static uint16_t want_sid = 0;
static uint16_t want_pid[MAX_PIDS];
static int      n_want   = 0;

/* ---------- program table ---------- */
static struct { uint16_t sid; uint16_t pmt_pid; } progs[MAX_PROGS];
static int      n_progs     = 0;
static int      pat_seen    = 0;
static int      fatal_error = 0;

/* ---------- matched program ---------- */
static uint16_t match_sid = 0;
static uint16_t match_pmt = 0xFFFF;

/* ---------- rewritten PAT ---------- */
static uint8_t original_pat[TS_PACKET];
static uint8_t rewritten_pat[TS_PACKET];
static int     have_rewritten_pat = 0;

/* ---------- PAT section assembly ---------- */
static uint8_t pat_sbuf[4096];
static int     pat_sbuf_have = 0;
static int     pat_sbuf_need = 0;

/* ---------- PMT section assembly ----------
 * Unlike tspidfilter, we accumulate continuation packets so the full section
 * is available before parsing ES PIDs.
 */
static uint8_t  pmt_sbuf[4096];
static int      pmt_sbuf_have         = 0;
static int      pmt_sbuf_need         = 0;
static uint16_t pmt_assembling_pid    = 0xFFFF;

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

/* ---------- payload start offset within a TS packet, or -1 ---------- */
static int payload_offset(const uint8_t *pkt, int pusi_only)
{
    uint8_t afc;
    int idx;

    if (pusi_only && !(pkt[1] & 0x40)) return -1;
    afc = (pkt[3] >> 4) & 0x3;
    if (afc == 0 || afc == 2) return -1;
    idx = 4;
    if (afc == 3) { idx += 1 + pkt[4]; if (idx >= TS_PACKET) return -1; }
    return idx;
}

/* ---------- section start offset (PUSI only), or -1 ---------- */
static int section_offset(const uint8_t *pkt)
{
    int idx = payload_offset(pkt, 1);
    if (idx < 0) return -1;
    idx += 1 + pkt[idx];
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
    sec[2] = 13;

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

/* ---------- parse fully assembled PAT section ---------- */
static void parse_pat(void)
{
    int i;
    const uint8_t *sec = pat_sbuf;
    int entry_end;

    if (pat_sbuf_have < 8) return;
    if (sec[0] != 0x00) return;

    entry_end = 3 + (int)(((sec[1] & 0x0F) << 8) | sec[2]) - 4;
    if (entry_end > pat_sbuf_have - 4) entry_end = pat_sbuf_have - 4;
    n_progs = 0;

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
    pat_seen = 1;

    if (sid_mode) {
        for (i = 0; i < n_progs; i++) {
            if (progs[i].sid == want_sid) {
                match_sid = want_sid;
                match_pmt = progs[i].pmt_pid;
                return;
            }
        }
        fprintf(stderr, "tsfilter2: service_id %u not found in PAT\n",
                (unsigned)want_sid);
        fprintf(stderr, "tsfilter2: PAT contains %d program(s):\n", n_progs);
        for (i = 0; i < n_progs; i++)
            fprintf(stderr, "  service_id=%-6u  pmt_pid=%u\n",
                    (unsigned)progs[i].sid, (unsigned)progs[i].pmt_pid);
        fatal_error = 1;
    }
}

/* ---------- accumulate PAT TS packet ---------- */
static void feed_pat_packet(const uint8_t *pkt)
{
    int idx, pusi, payload_len, copy, remaining;

    pusi = (pkt[1] & 0x40) != 0;
    idx  = payload_offset(pkt, 0);
    if (idx < 0) return;

    if (pusi) {
        int ptr = pkt[idx++];
        idx += ptr;
        if (idx + 3 > TS_PACKET) return;
        pat_sbuf_have = 0;
        pat_sbuf_need = 3 + (((pkt[idx + 1] & 0x0F) << 8) | pkt[idx + 2]);
        memcpy(original_pat, pkt, TS_PACKET);
    } else {
        if (pat_sbuf_need == 0) return;
    }

    payload_len = TS_PACKET - idx;
    if (payload_len <= 0) return;

    remaining = pat_sbuf_need - pat_sbuf_have;
    copy = payload_len < remaining ? payload_len : remaining;
    if (copy <= 0 || pat_sbuf_have + copy > (int)sizeof(pat_sbuf)) return;

    memcpy(pat_sbuf + pat_sbuf_have, pkt + idx, copy);
    pat_sbuf_have += copy;
}

/* ---------- accumulate PMT TS packet ---------- */
static void feed_pmt_packet(const uint8_t *pkt, uint16_t pid)
{
    int idx, pusi, payload_len, copy, remaining;

    pusi = (pkt[1] & 0x40) != 0;
    idx  = payload_offset(pkt, 0);
    if (idx < 0) return;

    if (pusi) {
        int ptr = pkt[idx++];
        idx += ptr;
        if (idx + 3 > TS_PACKET) return;
        pmt_sbuf_have      = 0;
        pmt_sbuf_need      = 3 + (((pkt[idx + 1] & 0x0F) << 8) | pkt[idx + 2]);
        pmt_assembling_pid = pid;
    } else {
        /* continuation: only accept if it belongs to the section we started */
        if (pmt_sbuf_need == 0 || pmt_assembling_pid != pid) return;
    }

    payload_len = TS_PACKET - idx;
    if (payload_len <= 0) return;

    remaining = pmt_sbuf_need - pmt_sbuf_have;
    copy = payload_len < remaining ? payload_len : remaining;
    if (copy <= 0 || pmt_sbuf_have + copy > (int)sizeof(pmt_sbuf)) return;

    memcpy(pmt_sbuf + pmt_sbuf_have, pkt + idx, copy);
    pmt_sbuf_have += copy;
}

/* ---------- parse fully assembled PMT section ---------- */
static void parse_pmt_section(uint16_t pid)
{
    int i;
    const uint8_t *sec = pmt_sbuf;
    uint16_t this_sid = 0;
    int entry_end, epos, found = 0;
    uint16_t prog_info_len;

    if (pmt_sbuf_have < 12) return;
    if (sec[0] != 0x02) return;

    for (i = 0; i < n_progs; i++) {
        if (progs[i].pmt_pid == pid) { this_sid = progs[i].sid; break; }
    }
    if (!this_sid) return;

    entry_end = 3 + (int)(((sec[1] & 0x0F) << 8) | sec[2]) - 4;
    /* clamp to the bytes we actually have */
    if (entry_end > pmt_sbuf_have - 4) entry_end = pmt_sbuf_have - 4;
    if (entry_end < 12) return;

    prog_info_len = ((sec[10] & 0x0F) << 8) | sec[11];
    epos          = 12 + (int)prog_info_len;

    if (sid_mode) {
        if (this_sid != want_sid) return;
        n_want = 0;
        while (epos + 5 <= entry_end) {
            uint16_t es_pid      = (((uint16_t)sec[epos+1] & 0x1F) << 8) | sec[epos+2];
            uint16_t es_info_len = (((uint16_t)sec[epos+3] & 0x0F) << 8) | sec[epos+4];
            if (n_want < MAX_PIDS) want_pid[n_want++] = es_pid;
            epos += 5 + (int)es_info_len;
        }
        found = 1;
    } else {
        while (epos + 5 <= entry_end) {
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
        fprintf(stderr, "tsfilter2: matched service_id=%u pmt_pid=%u es_pids=",
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

    i = 1;
    if (i < argc && strcmp(argv[i], "-t") == 0) {
        i++;
        if (i >= argc) { fprintf(stderr, "%s: -t requires a value\n", argv[0]); return 2; }
        want_duration = atoi(argv[i++]);
        if (want_duration <= 0) { fprintf(stderr, "%s: -t value must be > 0\n", argv[0]); return 2; }
    }

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
            fprintf(stderr, "tsfilter2: read error: %s\n", strerror(errno));
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
            int      is_pmt_candidate;

            if (p[0] != TS_SYNC) {
                off++;
                while (off < have && in[off] != TS_SYNC) off++;
                continue;
            }

            pid = (((uint16_t)p[1] & 0x1F) << 8) | p[2];

            if (pid == 0x0000) {
                if (!pat_seen) {
                    feed_pat_packet(p);
                    if (pat_sbuf_need > 0 && pat_sbuf_have >= pat_sbuf_need)
                        parse_pat();
                    if (fatal_error) break;
                }
                if (have_rewritten_pat) {
                    rewritten_pat[3] = (rewritten_pat[3] & 0xF0) | (p[3] & 0x0F);
                    memcpy(out + outlen, rewritten_pat, TS_PACKET);
                    outlen += TS_PACKET;
                }
            } else {
                /* Feed PMT packets (PUSI and continuations) until section complete */
                if (pat_seen && !have_rewritten_pat) {
                    is_pmt_candidate = 0;
                    if (sid_mode && match_pmt != 0xFFFF && pid == match_pmt) {
                        is_pmt_candidate = 1;
                    } else if (!sid_mode) {
                        for (i = 0; i < n_progs; i++)
                            if (progs[i].pmt_pid == pid) { is_pmt_candidate = 1; break; }
                    }
                    if (is_pmt_candidate) {
                        feed_pmt_packet(p, pid);
                        if (pmt_sbuf_need > 0 && pmt_sbuf_have >= pmt_sbuf_need)
                            parse_pmt_section(pid);
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
            if (want_duration && start_time == 0)
                start_time = time(NULL);

            if (write_full(1, out, outlen) < 0) {
                fprintf(stderr, "tsfilter2: write error: %s\n", strerror(errno));
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
