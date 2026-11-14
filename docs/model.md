# Python golden model

## Structure

Each file is one part of the spec, with the cycle-stepped core small and everything else built around it:

```
model/
  consts.py    timing-contract constants (input latency 2, output 1, taken JMP, ...)
  isa.py       opcodes, instruction dataclasses, encode()/decode()
  asm.py       assembler: labels, .at/.to, config directives (period table, pin windows)
  engine.py    one engine's architectural state + tick()
  chip.py      counter, 2 engines, pin resolution, capture, matcher, buffer, host API
  stream.py    stream record encode/decode (shared with host tools)
  crc.py       reference CRC/LFSR
  trace.py     pin-event traces, diffing, VCD export
  peers/       reference devices: UART, SPI flash, I2C EEPROM
```

## Principles

- **One source of truth per fact.** The ISA encoding lives only in `isa.py`, and the assembler, disassembler and RTL decode tests all use it. Timing numbers live only in `consts.py`.
- **Cycle-stepped, with architectural state only.** `Chip.tick(pins_in) -> pins_out` advances one clock. Model registers, flags and FIFOs, not pipeline internals.
- **Same interface as the RTL harness.** If cocotb can drive either the model or the RTL through `tick()`, then the differential test is just "run both, diff the traces".
- **Fast-forward over stalls.** When every engine is waiting on `.at` or a WAIT, jump straight to the next deadline or input change. Python is slow at cycle stepping, and protocols spend most of their time waiting.
- **Transaction-level host API on `Chip`:** `write_reg`, `load_prog`, `push_tx`, `read_stream`. Tests read like host code, and the real RP2040 driver can mirror it.
- **Deterministic.** No wall-clock time, and every random choice comes from a seed, so any failure can be replayed exactly.
