"""Instruction set: opcodes, operand encodings, instruction dataclasses, encode()/decode().

Encoding (spec, "Engine"):

     15      12   11   10    8   7                0
    [  opcode  ] [.at] [   A   ] [        B        ]

Bit 11 is `.at` on every opcode except WAIT, where it is `.to`. A (bits 10:8) is a selector,
B (bits 7:0) is data: an address, an immediate, a bit count, a second selector or flags.
Values not listed in an enum below are reserved: they halt the engine and set ILLEGAL.
"""

from dataclasses import dataclass
from enum import IntEnum, IntFlag
from typing import ClassVar

# =========================================================================
# Opcodes and operand encodings
# =========================================================================


class Opcode(IntEnum):
    """Bits 15:12. Values 0xB-0xF are reserved."""

    JMP = 0x0        # A: JmpCond         B: address
    WAIT = 0x1       # A: polarity, WaitSource   B[3:0]: index
    IN = 0x2         # A: Source          B[3:0]: bit count (0 = 16)
    OUT = 0x3        # A: OutDest         B[3:0]: bit count (0 = 16)
    SET = 0x4        # A: Dest            B: 8-bit immediate
    MOV = 0x5        # A: Dest            B[4:3]: MovOp, B[2:0]: Source
    PUSH_PULL = 0x6  # A: PushPullOp      B: PushPullFlag
    TIME = 0x7       # A: 0               B: TimeFlag
    EVT = 0x8        # A: EvtOp           B: EvtFlag
    ADDI = 0x9       # A: Dest (X or Y)   B: signed 8-bit immediate
    CRC = 0xA        # A: Dest (READ)     B[4:3]: CrcSource, B[2:0]: CrcFlag


class JmpCond(IntEnum):
    """JMP condition, bits 10:8."""

    ALWAYS = 0
    NOT_X = 1    # `!x`: X is 0
    X_DEC = 2    # `x--`: X is not 0; X decremented either way
    Y_DEC = 3    # `y--`: Y is not 0; Y decremented either way
    PIN = 4      # the JMP pin is high
    NOT_TXE = 5  # `!txe`: the TX FIFO is not empty
    TIMEOUT = 6  # TIMEOUT is set; the jump clears it
    MATCH = 7    # MATCH is set; the jump clears it


class WaitSource(IntEnum):
    """WAIT source, bits 9:8 (bit 10 is the polarity). Value 3 is reserved."""

    PIN = 0    # index = pin P0-P15
    EVENT = 1  # index = shared event 0-3; a wait for 1 clears it as it ends
    PPS = 2    # synchronised PPS input; index ignored


class Dest(IntEnum):
    """Destination, bits 10:8, shared by OUT, SET, MOV, ADDI and CRC READ.

    PINS, OSR, X, Y and ISR have the same values as in `Source`.
    """

    PINS = 0     # the instruction's pin window (OUT window for OUT and MOV, SET window for SET)
    OSR = 1      # shift count resets, so OSR is full again; NULL for OUT (see OutDest)
    X = 2
    Y = 3
    PINDIRS = 4  # same window as PINS, 1 = output
    DADD = 5     # D <- D + (value << SCALE)
    PC = 6       # jump to the value
    ISR = 7      # shift count becomes the number of bits written


class OutDest(IntEnum):
    """OUT destination, bits 10:8: `Dest` with NULL in place of OSR.

    Shifting OSR back into itself is meaningless, so for OUT that value discards the bits.
    """

    PINS = Dest.PINS.value
    NULL = Dest.OSR.value  # bits discarded
    X = Dest.X.value
    Y = Dest.Y.value
    PINDIRS = Dest.PINDIRS.value
    DADD = Dest.DADD.value
    PC = Dest.PC.value
    ISR = Dest.ISR.value


ADDI_DESTS = frozenset({Dest.X, Dest.Y})
CRC_READ_DESTS = frozenset({Dest.X, Dest.Y, Dest.OSR, Dest.ISR})


class Source(IntEnum):
    """Source, shared by IN (bits 10:8) and MOV (bits 2:0). Value 6 is reserved."""

    PINS = 0   # the IN window
    OSR = 1
    X = 2
    Y = 3
    NULL = 4   # zeros
    FLAGS = 5  # zero-extended
    ISR = 7


class MovOp(IntEnum):
    """MOV operation, bits 4:3. Value 3 is reserved."""

    NONE = 0
    INVERT = 1   # `~`
    REVERSE = 2  # `::`, bit-reverse


class PushPullOp(IntEnum):
    """PUSH / PULL operation, bits 10:8. Values 2-7 are reserved."""

    PUSH = 0
    PULL = 1


class PushPullFlag(IntFlag):
    """PUSH / PULL flags, bits 7:0."""

    BLOCK = 1 << 0  # stall while the FIFO is full (PUSH) / empty (PULL); else do nothing
    IF = 1 << 1     # `iffull` / `ifempty`: act only once ISR / OSR reaches its threshold


class TimeFlag(IntFlag):
    """TIME flags, bits 7:0, applied in bit order: STAMP, SETP, NOW, ADD."""

    STAMP = 1 << 0  # log the current time and X to the stream
    SETP = 1 << 1   # P <- {Y[7:0], X}
    NOW = 1 << 2    # D <- current time
    ADD = 1 << 3    # D <- D + P


# Assembler names for common TIME flag sets. `waitd` is `time.at` with no flags.
TIME_START = TimeFlag.NOW | TimeFlag.ADD  # D <- now + P: anchor a schedule
TIME_ADV = TimeFlag.ADD


class EvtOp(IntEnum):
    """EVT operation, bits 10:8. Values 2-7 are reserved."""

    RAISE = 0
    CLEAR = 1


class EvtFlag(IntFlag):
    """EVT flags, bits 7:0: which shared events to raise or clear, and the host IRQ."""

    EVENT0 = 1 << 0
    EVENT1 = 1 << 1
    EVENT2 = 1 << 2
    EVENT3 = 1 << 3
    IRQ = 1 << 4  # also raise the host IRQ (if enabled in IRQ_EN)


class CrcFlag(IntFlag):
    """CRC flags, bits 2:0, applied in this order: READ, RESET (then CrcSource)."""

    RESET = 1 << 0  # load CRC_INIT
    READ = 1 << 1   # copy 16 bits of the CRC to the destination in A
    HIGH = 1 << 2   # READ takes bits 31:16 instead of 15:0


class CrcSource(IntEnum):
    """CRC feed source, bits 4:3. A nonzero value takes effect from then on."""

    KEEP = 0  # leave the current feed unchanged
    OSR = 1   # bits shifted through OSR
    ISR = 2   # bits shifted through ISR
    OFF = 3   # nothing (the value after reset)


# =========================================================================
# Instructions
# =========================================================================

# One frozen dataclass per instruction, holding its operands as decoded values (enums, flags,
# plain ints in their natural range). The opcode is a class attribute, not a field. `at` is bit 11
# (`to` on WAIT). Constructors check ranges and legal values, so an instance always encodes.


def _check_range(name: str, value: int, lo: int, hi: int) -> None:
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be in {lo}..{hi}, got {value}")


@dataclass(frozen=True)
class Jmp:
    OPCODE: ClassVar[Opcode] = Opcode.JMP

    cond: JmpCond
    addr: int  # 0-255
    at: bool = False

    def __post_init__(self) -> None:
        _check_range("addr", self.addr, 0, 255)


@dataclass(frozen=True)
class Wait:
    OPCODE: ClassVar[Opcode] = Opcode.WAIT

    polarity: int  # 0 or 1
    source: WaitSource
    index: int  # pin 0-15, event 0-3, ignored for PPS (0)
    to: bool = False

    def __post_init__(self) -> None:
        _check_range("polarity", self.polarity, 0, 1)
        match self.source:
            case WaitSource.PIN:
                _check_range("pin index", self.index, 0, 15)
            case WaitSource.EVENT:
                _check_range("event index", self.index, 0, 3)
            case WaitSource.PPS:
                _check_range("PPS index", self.index, 0, 0)


@dataclass(frozen=True)
class In:
    OPCODE: ClassVar[Opcode] = Opcode.IN

    source: Source
    count: int  # 1-16 bits
    at: bool = False

    def __post_init__(self) -> None:
        _check_range("count", self.count, 1, 16)


@dataclass(frozen=True)
class Out:
    OPCODE: ClassVar[Opcode] = Opcode.OUT

    dest: OutDest
    count: int  # 1-16 bits
    at: bool = False

    def __post_init__(self) -> None:
        _check_range("count", self.count, 1, 16)


@dataclass(frozen=True)
class Set:
    OPCODE: ClassVar[Opcode] = Opcode.SET

    dest: Dest
    value: int  # 0-255, zero-extended
    at: bool = False

    def __post_init__(self) -> None:
        _check_range("value", self.value, 0, 255)


@dataclass(frozen=True)
class Mov:
    OPCODE: ClassVar[Opcode] = Opcode.MOV

    dest: Dest
    source: Source
    op: MovOp = MovOp.NONE
    at: bool = False


@dataclass(frozen=True)
class Push:
    OPCODE: ClassVar[Opcode] = Opcode.PUSH_PULL

    block: bool = True
    iffull: bool = False  # push only once ISR reaches the autopush threshold
    at: bool = False


@dataclass(frozen=True)
class Pull:
    OPCODE: ClassVar[Opcode] = Opcode.PUSH_PULL

    block: bool = True
    ifempty: bool = False  # pull only once OSR reaches the autopull threshold
    at: bool = False


@dataclass(frozen=True)
class Time:
    OPCODE: ClassVar[Opcode] = Opcode.TIME

    flags: TimeFlag = TimeFlag(0)  # noqa: RUF009 (immutable); no flags + at = `waitd`
    at: bool = False


@dataclass(frozen=True)
class Evt:
    OPCODE: ClassVar[Opcode] = Opcode.EVT

    op: EvtOp
    flags: EvtFlag
    at: bool = False


@dataclass(frozen=True)
class Addi:
    OPCODE: ClassVar[Opcode] = Opcode.ADDI

    dest: Dest  # X or Y
    value: int  # -128 to 127
    at: bool = False

    def __post_init__(self) -> None:
        if self.dest not in ADDI_DESTS:
            raise ValueError(f"ADDI destination must be X or Y, got {self.dest.name}")
        _check_range("value", self.value, -128, 127)


@dataclass(frozen=True)
class Crc:
    OPCODE: ClassVar[Opcode] = Opcode.CRC

    flags: CrcFlag = CrcFlag(0)  # noqa: RUF009 (immutable)
    source: CrcSource = CrcSource.KEEP
    dest: Dest | None = None  # READ destination: X, Y, OSR or ISR; None without READ
    at: bool = False

    def __post_init__(self) -> None:
        if CrcFlag.READ in self.flags:
            if self.dest not in CRC_READ_DESTS:
                got = self.dest.name if self.dest is not None else None
                raise ValueError(f"CRC READ needs a destination of X, Y, OSR or ISR, got {got}")
        elif self.dest is not None:
            raise ValueError("CRC destination is only used with READ")


Instr = Jmp | Wait | In | Out | Set | Mov | Push | Pull | Time | Evt | Addi | Crc



# =========================================================================
# Encoding and decoding
# =========================================================================

# Field positions, from the format diagram at the top of this file
_OPCODE_SHIFT = 12
_BIT11_SHIFT = 11
_A_SHIFT = 8
_A_MASK = 0b111
_B_MASK = 0xFF
_COUNT_MASK = 0xF  # IN/OUT bit count and WAIT index, B[3:0]


class IllegalInstruction(ValueError):
    """A word with a reserved opcode or field value; the engine halts and sets ILLEGAL."""


def _pack(opcode: Opcode, bit11: bool, a: int, b: int) -> int:
    return (opcode << _OPCODE_SHIFT) | (int(bit11) << _BIT11_SHIFT) | (a << _A_SHIFT) | b


def encode(instr: Instr) -> int:
    """Encode an instruction as its 16-bit word. Bits the hardware ignores are written as 0."""
    match instr:
        case Jmp():
            a, b = instr.cond, instr.addr
        case Wait():
            return _pack(Opcode.WAIT, instr.to, (instr.polarity << 2) | instr.source, instr.index)
        case In():
            a, b = instr.source, instr.count & _COUNT_MASK  # 16 encodes as 0
        case Out():
            a, b = instr.dest, instr.count & _COUNT_MASK  # 16 encodes as 0
        case Set():
            a, b = instr.dest, instr.value
        case Mov():
            a, b = instr.dest, (instr.op << 3) | instr.source
        case Push():
            flags = (PushPullFlag.BLOCK if instr.block else 0) | (PushPullFlag.IF if instr.iffull else 0)
            a, b = PushPullOp.PUSH, flags
        case Pull():
            flags = (PushPullFlag.BLOCK if instr.block else 0) | (PushPullFlag.IF if instr.ifempty else 0)
            a, b = PushPullOp.PULL, flags
        case Time():
            a, b = 0, instr.flags
        case Evt():
            a, b = instr.op, instr.flags
        case Addi():
            a, b = instr.dest, instr.value & _B_MASK  # two's complement
        case Crc():
            a = instr.dest if instr.dest is not None else 0
            b = (instr.source << 3) | instr.flags
    return _pack(instr.OPCODE, instr.at, a, b)


def decode(word: int) -> Instr:
    """Decode a 16-bit word. Raises IllegalInstruction for reserved opcodes and field values.

    Bits the spec shows as 0 are ignored, as in the hardware, so encode(decode(word)) can differ
    from word in those bits only.
    """
    if not 0 <= word <= 0xFFFF:
        raise ValueError(f"instruction word must be 16 bits, got {word:#x}")

    bit11 = bool((word >> _BIT11_SHIFT) & 1)
    a = (word >> _A_SHIFT) & _A_MASK
    b = word & _B_MASK
    count = (word & _COUNT_MASK) or 16  # IN/OUT: 0 means 16

    # Enum constructors and the dataclasses' own checks reject reserved values with ValueError
    try:
        match Opcode(word >> _OPCODE_SHIFT):
            case Opcode.JMP:
                return Jmp(JmpCond(a), b, at=bit11)
            case Opcode.WAIT:
                source = WaitSource(a & 0b11)
                index = 0 if source is WaitSource.PPS else word & _COUNT_MASK  # PPS ignores it
                return Wait(a >> 2, source, index, to=bit11)
            case Opcode.IN:
                return In(Source(a), count, at=bit11)
            case Opcode.OUT:
                return Out(OutDest(a), count, at=bit11)
            case Opcode.SET:
                return Set(Dest(a), b, at=bit11)
            case Opcode.MOV:
                return Mov(Dest(a), Source(b & 0b111), MovOp((b >> 3) & 0b11), at=bit11)
            case Opcode.PUSH_PULL:
                flags = PushPullFlag(b & 0b11)
                block = PushPullFlag.BLOCK in flags
                cond = PushPullFlag.IF in flags
                if PushPullOp(a) is PushPullOp.PUSH:
                    return Push(block, iffull=cond, at=bit11)
                return Pull(block, ifempty=cond, at=bit11)
            case Opcode.TIME:
                return Time(TimeFlag(b & 0xF), at=bit11)
            case Opcode.EVT:
                return Evt(EvtOp(a), EvtFlag(b & 0x1F), at=bit11)
            case Opcode.ADDI:
                return Addi(Dest(a), b - 0x100 if b & 0x80 else b, at=bit11)  # sign extend
            case Opcode.CRC:
                flags = CrcFlag(b & 0b111)
                dest = Dest(a) if CrcFlag.READ in flags else None  # A is ignored without READ
                return Crc(flags, CrcSource((b >> 3) & 0b11), dest, at=bit11)
    except ValueError as e:
        raise IllegalInstruction(f"{word:#06x}: {e}") from e
