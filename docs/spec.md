# Spec v0: timestamping protocol emulator

Two PIO-like engines, a capture path and a pattern matcher all take their timing from one 48-bit cycle counter; the RP2040 host loads programs and drains the stream over SPI.

## Pins and clock

One clock domain at a 48 MHz target (one cycle = 20.83 ns), and 16 engine-visible pins mapped onto the Tiny Tapeout pinout.

| Tiny Tapeout pin | Direction | Use |
| --- | --- | --- |
| `ui_in[0]` | in | Host SPI SCK |
| `ui_in[1]` | in | Host SPI CS\_n |
| `ui_in[2]` | in | Host SPI MOSI |
| `ui_in[3]` | in | PPS input |
| `ui_in[7:4]` | in | Engine pins P8–P11 (input only) |
| `uo_out[0]` | out | Host SPI MISO |
| `uo_out[1]` | out | IRQ to host (stream ready, late, overflow) |
| `uo_out[2]` | out | TRIG: match-and-act output |
| `uo_out[3]` | out | PPS\_OUT: pulse at a host-scheduled time |
| `uo_out[7:4]` | out | Engine pins P12–P15 (output only) |
| `uio[7:0]` | in/out | Engine pins P0–P7, per-pin output enable, optional open-drain |

- **Clock:** 48 MHz is 32 × USB low-speed's 1.5 MHz, so those edges carry no quantisation jitter. Everything else rounds to the nearest cycle.
- **Single domain:** every pin input, host SPI included, passes through a 2-flop synchroniser and is sampled by `clk`. The host SPI clock must therefore stay at or below `clk`/8 (6 MHz).
- **Reset:** `rst_n` is synchronised, and every register comes out of reset; nothing relies on power-up values.
- **Open-drain:** writing 0 drives the pin low; writing 1 releases it (output disabled), so an external pull-up raises it. This is how I2C works on P0–P7.

## Engine

Two identical engines (E0, E1), each a small PIO-like machine with 16-bit instructions, plus one new idea: a deadline register D and a `.at` flag that makes a pin action happen on an exact cycle.

**Registers (per engine)**

| Register | Width | Purpose |
| --- | --- | --- |
| PC | 8 | Program counter into a 256-word program memory |
| X, Y | 16 each | Scratch and loop counters |
| OSR | 16 + count | Output shift register; autopull from the TX FIFO at a threshold |
| ISR | 16 + count | Input shift register; autopush to the RX FIFO at a threshold |
| D | 32 | Next deadline, compared against the low 32 bits of the cycle counter |
| P | 24 | Period added to D after every `.at` action |
| FLAGS | 8 | LATE, TIMEOUT, MATCH, and four shared event flags |
| CRC | 32 | LFSR fed by every bit shifted through OSR or ISR, with a host-set polynomial and initial value. Parity is its 1-bit case |
| TX / RX FIFO | 4 × 16 each | To and from the host |

Host-written config per engine: OUT, SET and IN pin windows (base + count), the JMP pin, the open-drain mask, shift directions, autopull/autopush thresholds, and the late policy (flag or halt).

**Instruction encoding:** bits 15:12 are the opcode; bit 11 is `.at` (or `.to` on WAIT); bits 10:0 are operands.

| Op | Mnemonic | Operands | Stalls when |
| --- | --- | --- | --- |
| 0 | JMP | condition (always, X==0, X--, Y--, PIN, !OSRE, TIMEOUT, MATCH), 8-bit address | Never |
| 1 | WAIT\[.to\] | polarity, source (pin, event, PPS), index | Until true; with `.to`, until D at most (sets TIMEOUT) |
| 2 | IN\[.at\] | source (PINS, X, Y, NULL), 1–16 bits | `.at` until D; autopush to a full FIFO |
| 3 | OUT\[.at\] | destination (PINS, PINDIRS, X, Y, NULL, DADD, PC), 1–16 bits | `.at` until D; autopull from an empty FIFO |
| 4 | SET\[.at\] | destination (PINS, PINDIRS, X, Y), 8-bit immediate | `.at` until D |
| 5 | MOV | destination, operation (none, invert, bit-reverse), source | Never |
| 6 | PUSH / PULL | block, if-full / if-empty | If blocking and the FIFO is full / empty |
| 7 | TIME | START (D ← now + P), ADV (D ← D + P), WAITD (wait until D, then D += P), STAMP (log the time + X to the stream), SETP (P ← Y:X) | WAITD until D |
| 8 | EVT | RAISE / CLEAR shared event *i*, IRQ to host | Never |
| 9 | ADDI | X or Y, signed 8-bit immediate | Never |
| A | CRC | RESET (load the initial value), SRC (feed from OSR or ISR shifts), READ (result to ISR, X or Y) | Never |
| B–F | reserved | Room for line-coding ops later | — |

`OUT DADD` adds the shifted-out bits to D. That one destination is what lets replay run as an ordinary program (see Match-and-act and replay).

## Timing contract

Every guarantee is stated in cycles of `clk`. Firmware and tests rely on these, and the formal proofs check them.

1. **Issue:** each instruction takes 1 cycle, and a taken JMP takes 2. Program SRAM reads are synchronous, so a taken branch costs one bubble. Only stalls add more.
2. **Deadline actions:** a `.at` instruction stalls until the cycle where the counter reaches D. Its register update happens on that cycle, and the pad changes one cycle later (a fixed output latency of 1).
3. **Wrap-safe compare:** D counts as reached when (counter − D), read as signed 32-bit, is ≥ 0. Deadlines can sit up to 2^31 cycles (44.7 s) ahead.
4. **Advance:** after each `.at` action, D ← D + P. With P = 0, D stays put.
5. **Late:** if D has already passed when a `.at` instruction issues, the action happens at once, LATE is set and a LATE marker goes into the stream. With the late policy set to halt, the engine stops before acting instead.
6. **Timeout:** `WAIT.to` ends on its condition or on D, whichever comes first. Ending on D sets TIMEOUT and does not advance D.
7. **Inputs:** pin values seen by engines and capture are 2 cycles old (the synchroniser). The optional 3-sample glitch filter adds 1 more. Capture reports raw timestamps; the host subtracts the constant.
8. **Cross-engine:** both engines read one counter, so `.at` actions with the same D land on the same cycle.
9. **PPS:** a PPS rising edge latches the counter into PPS\_LAST, with the same 2-cycle input latency.
10. **Match:** TRIG changes exactly 2 cycles after the cycle the final matching byte enters an engine's RX path. This is a formal proof target.

## Timebase, PPS and capture stream

A free-running 48-bit cycle counter is the chip's only clock. PPS discipline happens on the host, and every edge goes into a compressed byte stream.

- **Counter:** 48 bits, +1 every cycle, never adjusted. It wraps after about 67.9 days at 48 MHz.
- **PPS (v0, software discipline):** each PPS edge latches the counter into PPS\_LAST and logs a PPS record. The host servo fits cycles-per-second and offset, converts timestamps to real time, and schedules real-time events (such as PPS\_OUT on the next second) as cycle counts. A hardware-disciplined clock is an open decision below.
- **Capture:** watches P0–P7 through a host-set mask. Any masked change logs an edge record: the time since the previous record, plus all 8 pin values.
- **Buffer:** records queue in a 512 × 16 SRAM (1 KB), drained by the host over SPI. When it fills, records are dropped and counted, and an OVERFLOW record says how many. Nothing is ever lost silently.

**Stream records** (deltas count from the previous record's time; records carrying an absolute time reset that base)

| First byte | Record | Total bytes | Contents |
| --- | --- | --- | --- |
| `0x00`–`0x7F` | Short edge | 2 | Delta of 1–128 cycles in the first byte, pins in the second |
| `0x81`–`0x86` | Long edge | 3–8 | Low bits give the delta's byte count (1–6), then the delta, then pins |
| `0xC0` | SYNC | 7 | 48-bit absolute time; sent at start, after an overflow, and every 4,096 records |
| `0xC1` | PPS | 7 | 48-bit time of the PPS edge |
| `0xC2`/`0xC3` | STAMP E0/E1 | 9 | 48-bit time + the engine's X |
| `0xC4`/`0xC5` | LATE E0/E1 | 7 | 48-bit time the late action happened |
| `0xC6` | MATCH | 7 | 48-bit time the trigger fired |
| `0xC7` | OVERFLOW | 3 | 16-bit count of dropped records |

**Bandwidth budget:** SPI at 6 MHz moves about 750 KB/s, so roughly 375,000 short edges per second can stream live. Faster bursts fill the 1 KB buffer, which holds 512 short edges. A 1 Mbaud UART (up to 1,000,000 edges per second) therefore gets captured into the buffer and drained afterwards.

## Match-and-act and replay

Match-and-act is one small shared block; replay needs no hardware of its own, because it runs as an ordinary engine program.

**Match-and-act**

- Watches the RX path of one engine (host selects E0 or E1). The low 8 bits of every word pushed there shift into a 4-byte window.
- The host sets PATTERN (32 bits), MASK (32 bits) and LEN (1–4 bytes). A match fires when the last LEN bytes equal PATTERN under MASK.
- On a match it can do any mix of: pulse or toggle TRIG, set MATCH in both engines, raise a shared event (waking an engine blocked in WAIT, e.g. one about to replay), and log a MATCH record.
- One-shot or auto re-arm, set by the host.
- TRIG changes exactly 2 cycles after the final matching byte arrives (timing contract, item 10).

**Replay**

The host turns a capture into 16-bit replay words: delta cycles in the high byte, pin values in the low byte. Gaps over 255 cycles become filler words that leave the pins unchanged. The words go to an engine's TX FIFO, or are preloaded into the shared buffer for bursts the SPI link can't feed live. A four-instruction program plays them:

```
        time   start       ; D <- now (P = 0, so .at never moves D itself)
loop:   pull   block       ; next replay word
        out    dadd, 8     ; D += delta << SCALE
        out.at pins, 8     ; pins change exactly at D
        jmp    loop
```

- SCALE (0–7, host config) stretches the playback by 2^SCALE.
- Edges in a replay can be no closer than the loop time, about 5 cycles (104 ns). Closer edges arrive late and get flagged.
- Jitter injection is left for later; a small LFSR added to DADD would do it.

## Host interface

The host (the demo board's RP2040) talks SPI mode 0, MSB first, at up to 6 MHz. Each transaction is CS low, one command byte, its arguments and data, then CS high.

| Cmd | Name | Arguments, then data | Does |
| --- | --- | --- | --- |
| `0x01` | WRITE\_REG | address, then 32-bit values | Writes registers, auto-incrementing |
| `0x02` | READ\_REG | address, one dummy byte, then values out | Reads registers, auto-incrementing |
| `0x10` | LOAD\_PROG | engine, start address, then 16-bit words | Writes program memory (engine halted) |
| `0x20` | PUSH\_TX | engine, then 16-bit words | Fills an engine's TX FIFO |
| `0x21` | POP\_RX | engine, then words out | Drains an engine's RX FIFO |
| `0x30` | READ\_STREAM | stream bytes out until CS goes high | Drains the capture stream; `0x80` means empty |
| `0x31` | LOAD\_BUFFER | address, then 16-bit words | Preloads the shared buffer for replay |
| `0x40` | CONTROL | one byte | Run, halt or step each engine; start or stop capture |
| `0x41` | READ\_TIME | 6 bytes out | The counter, latched as the command byte ends |
| `0x42` | EXEC | engine, then one 16-bit instruction | Runs one instruction now (debugging) |

**Register map** (8-bit addresses, 32-bit registers)

| Address | Register | Contents |
| --- | --- | --- |
| `0x00` | ID | Chip ID and spec version (read-only) |
| `0x01` | CTRL | Engine run bits, capture enable, matcher enable |
| `0x02` | STATUS | Halted, LATE and TIMEOUT per engine, buffer level, overflow (read-only) |
| `0x03`, `0x04` | IRQ\_EN, IRQ\_STATUS | Which events raise the IRQ pin; writing 1 to an IRQ\_STATUS bit clears it |
| `0x05` | CAP\_CFG | Capture pin mask, glitch filter enable |
| `0x06` | BUF\_CFG | Shared buffer used for capture or for replay |
| `0x08`, `0x09` | PPS\_LAST | Counter at the last PPS edge (low 32, high 16) |
| `0x0A` | PPS\_COUNT | PPS edges seen |
| `0x0B`, `0x0C` | PPS\_OUT\_AT | Counter value for the next PPS\_OUT pulse |
| `0x10`–`0x12` | MATCH\_PATTERN, MATCH\_MASK, MATCH\_CFG | Pattern, mask, length, source engine, actions, re-arm, TRIG width |
| `0x20`+ / `0x40`+ | E0 / E1 block | PINCFG, SHIFTCFG (directions, thresholds, late policy, SCALE), OD\_MASK, P, D, CRC\_POLY, CRC\_INIT, PC, X, Y, FLAGS, FIFO levels |

D and PC are writable only while that engine is halted; X, Y, FLAGS and FIFO levels are read-only debug views.

## Worked example: UART TX

UART 8N1 at 115,200 baud is ten instructions, and every edge lands on its exact cycle however long the loop body takes.

The config is P = 417 cycles (48 MHz / 115,200 = 416.67, so 0.08% slow), OUT and SET windows on P0, and OSR shifting right for LSB first.

```
        set    pins, 1     ; line idles high
frame:  pull   block       ; next byte from the TX FIFO
        time   start       ; D <- now + P: re-anchor after any idle time
        set    x, 7        ; 8 data bits
        set.at pins, 0     ; start bit at D, then D += P
bit:    out.at pins, 1     ; data bit at D, then D += P
        jmp    x--, bit
        set.at pins, 1     ; stop bit at D, then D += P
        time   waitd       ; hold the stop bit for a full period
        jmp    frame
```

- The loop body (`out.at` + a taken `jmp`) costs 3 cycles against a 417-cycle bit, so it never runs late.
- Re-anchoring each frame adds one idle bit between back-to-back bytes (11 bit times per byte, not 10). A "TX FIFO not empty" jump condition would remove that; it's listed under decisions.
- SPI has the same shape, with P as half a clock period: an `out.at` for data, then a `set.at` for the clock edge. I2C adds open-drain pins and `WAIT.to` for clock stretching and missing ACKs.

## Area budget

The budget is now 8x4 (about 960,000 µm²), but v0 still aims to fit the original 6x4 tiles, leaving the extra 8 tiles as headroom for stretch features and easier timing. The SRAM macros take about 11% of 8x4; the logic figures are estimates, to be replaced by measured area.

| Block | Area | Share of 8x4 | Basis |
| --- | --- | --- | --- |
| Program memory, 2 × 256×16 SRAM | 56,254 µm² | 5.9% | Tiny Tapeout's [memory table](https://www.tinytapeout.com/specs/memory/) |
| Capture/replay buffer, 512×16 SRAM | 45,309 µm² | 4.7% | Same table |
| Two engines | ≤ 216,000 µm² target | ≤ 22.5% | Estimate, not yet measured |
| Counter, PPS, capture, encoder | ≤ 86,000 µm² target | ≤ 9% | Estimate, not yet measured |
| Host SPI, registers, IRQ | ≤ 58,000 µm² target | ≤ 6% | Estimate, not yet measured |
| Matcher | ≤ 29,000 µm² target | ≤ 3% | Estimate, not yet measured |
| Routing, clock tree, margin within 6x4 | \~229,000 µm² | \~24% | Reserved |
| Headroom: the extra 8 tiles | \~240,000 µm² | \~25% | Reserved until the 6x4-sized design closes |

- The macro sizes come from IHP's SG13G2 library, which the CMOS5L PDK links to. Powering a macro on CMOS5L needs hand-built power stripes, which is a known risk.
- If the macros can't be powered, the fallback is flip-flop memory, 32 × 16 per engine (about 1.6 tiles each, at roughly 320 flops per tile) and a small flop FIFO in place of the 1 KB buffer. Latch arrays are ruled out; the 8x4 headroom absorbs the flop fallback.
- Candidates for the headroom, once v0 closes: the Manchester serialiser for 10BASE-T, small latency histograms, more program memory, or a third engine.

## Decisions to weigh

The first three shape the rest of the design, so they are settled first; the others can wait for measurements.

| Decision | Options | v0 pick | What would change it |
| --- | --- | --- | --- |
| Clock discipline | Software (latch PPS, host converts) vs a hardware-disciplined counter (fractional increment, roughly an 80-bit accumulator) | Software | Wanting real-time outputs or PTP without host round trips, if area allows |
| Host link | SPI (4 pins, ≤ 6 MHz) vs a 4-bit parallel port (more pins, about 4× the throughput) | SPI | Streaming bandwidth becoming the capture bottleneck |
| Program memory | SRAM macros, decided. Ruled out: latch arrays | SRAM | If macro power fails on CMOS5L: 32 × 16 flip-flop memory per engine |
| Engine count | 1, 2 or 4 | 2 | Measured area |
| Instruction width | 16 bits vs 24 or 32 | 16 (matches the 256×16 macro) | Frequently needing wide immediates |
| Deadline compare width | 32 bits (44.7 s horizon) vs the full 48 | 32 | Needing schedules more than 44 s ahead without host help |
| Late policy default | Flag and continue vs halt | Flag | A target where a late edge does more harm than stopping |
| Side-set | None vs PIO-style side-set | None (`.at` covers most uses) | Fast SPI needing a pin change and another operation in one cycle |
| Back-to-back frames | Re-anchor every frame vs a "TX FIFO not empty" jump | Re-anchor | Throughput mattering; it costs a fourth condition bit in JMP |
| Clock rate | 48 MHz vs higher | 48 MHz | Timing slack at final hardening, or attempting 10BASE-T |
| Replay | Firmware on an engine vs a dedicated unit | Firmware | Needing replay edges closer than about 5 cycles |
| Matcher power | One masked pattern vs two or more pattern slots OR'd together, plus a range compare on one byte | One pattern; both added once v0 fits | Triggers like "write or erase command" or "any address ≥ 0x80"; both are cheap |
| Capture width | P0–P7 vs all 16 pins | P0–P7 (keeps short edges at 2 bytes) | Protocols needing more captured pins |
