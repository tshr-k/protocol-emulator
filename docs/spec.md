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

Two identical engines (E0, E1), each a small PIO-like machine with 16-bit instructions, plus one new idea: a deadline register D and a `.at` flag that makes any instruction act on an exact cycle.

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

**How data moves.** Words from the host arrive in the TX FIFO. PULL, or autopull once the output shift register (OSR) has shifted out a host-set number of bits, loads the next word into OSR, and OUT shifts 1–16 bits at a time out of OSR to pins or a register. In the other direction, IN shifts 1–16 bits from pins or a register into the input shift register (ISR), and PUSH, or autopush at a threshold, moves ISR into the RX FIFO for the host. Each shift register's direction (MSB or LSB first) is host config. Pins are reached through windows: an n-bit OUT, SET or IN touches pins base to base + n − 1 of its window, so one program works on whichever pins the host maps it to.

**Instruction format**

```
 15      12   11   10    8   7                0
[  opcode  ] [.at] [   A   ] [        B        ]
```

- **A (bits 10:8)** is a selector: the JMP condition, a destination or source, or a sub-operation.
- **B (bits 7:0)** is data: the JMP address, an 8-bit immediate, a bit count in bits 3:0 (0 means 16), a second selector, or a set of flags.
- **Bit 11** is `.at` on every instruction except WAIT, where it is `.to`. A `.at` instruction waits until the counter reaches D, acts on that cycle, then adds P to D (timing contract, items 2–5). Any instruction can be timed: `set.at` for a pin edge, `evt.at` to wake the other engine on an exact cycle, `time.at stamp` to log exactly at D.
- Bits shown as 0 are ignored by the hardware, and the assembler writes them as 0. Reserved opcodes and reserved field values halt the engine and set ILLEGAL in STATUS.

| Op | Instruction | Bit 11 | Bits 10:8 | Bits 7:0 |
| --- | --- | --- | --- | --- |
| `0` | JMP | `.at` | condition | address |
| `1` | WAIT | `.to` | \[10\] polarity, \[9:8\] source | \[3:0\] index |
| `2` | IN | `.at` | source | \[3:0\] bit count |
| `3` | OUT | `.at` | destination | \[3:0\] bit count |
| `4` | SET | `.at` | destination | 8-bit immediate |
| `5` | MOV | `.at` | destination | \[4:3\] operation, \[2:0\] source |
| `6` | PUSH / PULL | `.at` | 0 = PUSH, 1 = PULL | \[1\] if-full / if-empty, \[0\] block |
| `7` | TIME | `.at` | 0 | \[3\] ADD, \[2\] NOW, \[1\] SETP, \[0\] STAMP |
| `8` | EVT | `.at` | 0 = RAISE, 1 = CLEAR | \[4\] IRQ, \[3:0\] event mask |
| `9` | ADDI | `.at` | destination (X or Y only) | signed 8-bit immediate |
| `A` | CRC | `.at` | READ destination (X, Y, OSR or ISR only) | \[4:3\] SRC, \[2\] HIGH, \[1\] READ, \[0\] RESET |
| `B`–`F` | reserved | — | — | Room for line-coding ops later |

For example, `set pins, 1` is `0x4001`, `out.at pins, 1` is `0x3801`, `jmp x--, 5` is `0x0205`, `pull block` is `0x6101` and `time start` is `0x700C`.

**Shared operand encodings.** OUT, SET, MOV, ADDI and CRC READ share one destination numbering, and IN and MOV share one source numbering. PINS, OSR, X, Y and ISR have the same value in both, so the decoder can route the field straight to the register file. OUT is the one exception: shifting OSR back into itself is meaningless, so for OUT value 1 means NULL.

| Value | Destination | Source |
| --- | --- | --- |
| 0 | PINS: the instruction's pin window (OUT window for OUT and MOV, SET window for SET) | PINS: the IN window |
| 1 | OSR: its shift count resets, so it is full again (for OUT: NULL, bits discarded) | OSR |
| 2 | X | X |
| 3 | Y | Y |
| 4 | PINDIRS: the same window as PINS, 1 = output | NULL: zeros |
| 5 | DADD: D ← D + (value << SCALE) | FLAGS, zero-extended |
| 6 | PC: jump to the value | reserved |
| 7 | ISR: its shift count becomes the number of bits written | ISR |

| Value | JMP condition | Jumps when |
| --- | --- | --- |
| 0 | *(none)* | Always |
| 1 | `!x` | X is 0 |
| 2 | `x--` | X is not 0; X is decremented either way |
| 3 | `y--` | Y is not 0; Y is decremented either way |
| 4 | `pin` | The JMP pin is high |
| 5 | `!txe` | The TX FIFO is not empty |
| 6 | `timeout` | TIMEOUT is set; the jump clears it |
| 7 | `match` | MATCH is set; the jump clears it |

**What each instruction does**

- **JMP** `jmp[.at] [condition,] target`: jumps to an 8-bit address when the condition holds. A taken jump costs one extra cycle. `!txe` lets a transmitter go straight to the next frame without re-anchoring its schedule (see the UART example).
- **WAIT** `wait[.to] polarity, source, index`: stalls until a signal equals the polarity (0 or 1). Source 0 is pin P*index* (0–15; the output-only P12–P15 read back what they drive). Source 1 is shared event *index* (0–3; 4–15 are reserved); a wait for 1 clears the event as it ends, so the next wait needs a new RAISE. Source 2 is the synchronised PPS input, with the index ignored, and source 3 is reserved. With `.to`, the wait also ends when the counter reaches D: TIMEOUT is set if it ended on D and cleared if it ended on the signal. D is not advanced either way.
- **IN** `in[.at] source, count`: shifts *count* bits (1–16) from the source into ISR, starting at the IN window's base pin for PINS. With autopush on, a full ISR then moves to the RX FIFO, stalling while the FIFO is full.
- **OUT** `out[.at] destination, count`: shifts *count* bits out of OSR to the destination (table above). With autopull on, an empty OSR first refills from the TX FIFO, stalling while the FIFO is empty. `out null` discards bits, and `out dadd` is what lets replay run as an ordinary program (see Match-and-act and replay).
- **SET** `set[.at] destination, value`: writes an 8-bit immediate, zero-extended. PINS and PINDIRS reach up to 8 pins of the SET window. `set.at pins` is the usual way to make a clock edge or start bit on an exact cycle.
- **MOV** `mov[.at] destination, [operation] source`: copies a 16-bit value, unchanged (0), inverted (1, written `~`) or bit-reversed (2, written `::`); operation 3 is reserved. Unlike OUT and IN it does not shift OSR or ISR. `mov osr, x` reloads OSR without the TX FIFO, for example to send the same word again.
- **PUSH / PULL** `push [iffull] [block]`, `pull [ifempty] [block]`: PUSH moves ISR into the RX FIFO and clears ISR; PULL loads OSR from the TX FIFO. With block, they stall while the FIFO is full (PUSH) or empty (PULL); without it, they do nothing in that case. `iffull` / `ifempty` make them do nothing unless ISR has reached the autopush threshold, or OSR the autopull threshold.
- **TIME** `time[.at] flags`: manages the deadline. Any mix of flags is allowed, applied in this order: STAMP logs the current time and X to the stream; SETP loads P from {Y\[7:0\], X}; NOW sets D to the current time; ADD adds P to D. The assembler also accepts `start` (NOW + ADD, so D ← now + P, which anchors a schedule), `adv` (ADD) and `waitd`, which is `time.at` with no flags: wait until D, then D += P.
- **EVT** `evt[.at] raise|clear, mask [, irq]`: sets or clears any of the four shared event flags at once. Both engines see them, WAIT waits on them and the matcher can raise them. With IRQ it also raises the host IRQ (if enabled in IRQ\_EN); an empty mask with IRQ just interrupts the host.
- **ADDI** `addi[.at] x|y, value`: adds a signed 8-bit immediate (−128 to 127) to X or Y, wrapping at 16 bits.
- **CRC** `crc[.at] flags [, destination]`: controls the engine's LFSR, applying its flags in this order. READ copies 16 bits of the CRC (bits 15:0, or 31:16 with HIGH) to X, Y, OSR or ISR; without READ, bits 10:8 are ignored. RESET loads CRC\_INIT. A nonzero SRC chooses what feeds it from then on: 1 = bits shifted through OSR, 2 = through ISR, 3 = nothing (the value after reset). `crc read|reset, x` finishes one frame and starts the next in one instruction.

## Timing contract

Every guarantee is stated in cycles of `clk`. Firmware and tests rely on these, and the formal proofs check them.

1. **Issue:** each instruction takes 1 cycle, and one that changes PC (a taken JMP, or a write to PC) takes 2. Program SRAM reads are synchronous, so a jump costs one bubble. Only stalls add more.
2. **Deadline actions:** a `.at` instruction stalls until the cycle where the counter reaches D and acts on that cycle; a pin change reaches the pad one cycle later (a fixed output latency of 1). If the instruction also has to wait for a FIFO, it acts on the first cycle at or after D when the FIFO allows.
3. **Wrap-safe compare:** D counts as reached when (counter − D), read as signed 32-bit, is ≥ 0. Deadlines can sit up to 2^31 cycles (44.7 s) ahead.
4. **Advance:** after each `.at` instruction, D ← D + P, applied after the instruction's own effect on D. With P = 0, D stays put.
5. **Late:** if a `.at` instruction acts on a cycle after D (it issued after D, or a FIFO held it past D), LATE is set and a LATE marker goes into the stream. With the late policy set to halt, the engine stops before acting instead.
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
| `0x02` | STATUS | Halted, LATE, TIMEOUT and ILLEGAL per engine, buffer level, overflow (read-only) |
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

UART 8N1 at 115,200 baud is thirteen instructions, and every edge lands on its exact cycle however long the loop body takes.

The config is P = 417 cycles (48 MHz / 115,200 = 416.67, so 0.08% slow), OUT and SET windows on P0, and OSR shifting right for LSB first.

```
        set    pins, 1     ; line idles high
idle:   pull   block       ; wait for the next byte
        time   start       ; D <- now + P: re-anchor after idle time
frame:  set    x, 7        ; 8 data bits
        set.at pins, 0     ; start bit at D, then D += P
bit:    out.at pins, 1     ; data bit at D, then D += P
        jmp    x--, bit
        set.at pins, 1     ; stop bit at D, then D += P
        jmp    !txe, next  ; another byte queued: keep the schedule
        time.at            ; hold the stop bit for a full period
        jmp    idle
next:   pull   block
        jmp    frame
```

- The loop body (`out.at` + a taken `jmp`) costs 3 cycles against a 417-cycle bit, so it never runs late.
- `jmp !txe` chains back-to-back bytes at exactly 10 bit times each. The schedule re-anchors only after the line has gone idle.
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
| Back-to-back frames | Re-anchor every frame vs a "TX FIFO not empty" jump | `!txe` jump condition, decided (it replaced `!OSRE`) | Needing a jump on OSR empty; autopull covers most of those uses |
| Clock rate | 48 MHz vs higher | 48 MHz | Timing slack at final hardening, or attempting 10BASE-T |
| Replay | Firmware on an engine vs a dedicated unit | Firmware | Needing replay edges closer than about 5 cycles |
| Matcher power | One masked pattern vs two or more pattern slots OR'd together, plus a range compare on one byte | One pattern; both added once v0 fits | Triggers like "write or erase command" or "any address ≥ 0x80"; both are cheap |
| Capture width | P0–P7 vs all 16 pins | P0–P7 (keeps short edges at 2 bytes) | Protocols needing more captured pins |
