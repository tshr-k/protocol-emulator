# SystemVerilog Style Guide

This guide describes the coding, formatting and comment style for the hand-written SystemVerilog in this
project (`src/` and any formal property files). Use it when writing or editing RTL, and follow it exactly.

---

## 1. Whitespace and layout basics

- **Indent with 4 spaces.** Never use tabs.
- Every file ends with a single trailing newline. Avoid trailing whitespace.
- **There is no hard line length limit.** Most lines stay under ~100 characters, but long trailing comments
  are allowed to run past that (up to ~175 characters). Long *expressions* are wrapped (see section 9).
  Long *comments* are usually either left on one line or split into several `//` lines.
- Module bodies are indented by one level inside `module ... endmodule`. The same applies to
  `package ... endpackage`, `begin ... end`, `case ... endcase` and `function ... endfunction`.
- **Blank lines:**
  - 1 blank line separates logical groups: imports from the module, port groups, declaration groups,
    `always` blocks, instances and `assign` groups.
  - **2 blank lines** separate major sections inside large modules, e.g. between the `// Shift register`
    and `// Command decoder` sections, and before each `// ====` banner (see section 12).
  - There is no blank line directly after `module (...);` / `) (` / `begin`, and none before `endmodule`.
  - Inside an `always_comb`, a blank line separates the default assignments from the `case`/`if` that
    follows.
- A space goes around binary operators and `=` / `<=`, after commas, and after keywords such as `if (`,
  `case (`, `for (`, `@(`. There is no space between a function or system task name and its `(`:
  `$clog2(DEPTH)`, `max(a, b)`.
- Ranges in declarations have no spaces: `[DEPTH-1:0]`, `[7:0]`, `[$clog2(DEPTH+1)-1:0]`.
  Arithmetic in **declaration** widths is also written tight: `[PTR_WIDTH-1:0]`, `DEPTH-1`,
  `DATA_BITS-1`, `DIVIDER/2`.
  - Part-selects with a computed upper bound put spaces around the colon and the outer `-`:
    `addr[(ADDR_WIDTH+2) - 1 : 2]`, `frame[FRAME_BITS - 1 : DATA_BITS]`.
  - Indexed part-selects use spaces around `+:`: `write_data[8*b +: 8]`,
    `read_data[8*int'(byte_offset) +: 8]`. Multiplication inside them is tight (`8*b`).

## 2. File organisation

- **One module or package per file**, and the file name matches it: `fifo.sv` holds `module fifo`, and
  `spi_pkg.sv` holds `package spi_pkg`.
- Packages live in a `pkg/` subdirectory and are named `<thing>_pkg`.
- Closely related modules share a prefix: `spi_target`, `spi_shift_register`.
- Formal property wrappers live in a `formal/` directory and are named `<module>_props.sv` /
  `module <module>_props`.
- **Every `.sv` file starts with the Apache-2.0 licence block**, followed by a blank line. This is the only
  place a `/* */` comment is allowed. There are no other file header comments, author or date lines:
  ```systemverilog
  /*
   * SPDX-License-Identifier: Apache-2.0
   */
  ```

**File layout order:**

```systemverilog
/*                            // 1. Licence block
 * SPDX-License-Identifier: Apache-2.0
 */
                              // 2. Blank line
import spi_pkg::*;            // 3. Package imports at file scope, one per line
import utils_pkg::*;
                              // 4. Blank line
// Optional block comment     // 5. Optional description directly above `module`, with no blank line between them
// describing the module
module name #(                // 6. Module header
    ...
) (
    ...
);
    initial begin ... end     // 7. Parameter validation (if any)
    localparam / typedef ...  // 8. Local constants and types
    signals ...               // 9. Signal declarations, assigns, always blocks and instances
endmodule
```

A file with no imports goes straight from the licence block's blank line to the description or `module`.

- Imports are written as `import <pkg>::*;` at **file scope, before `module`**, never inside the module
  header. The only exception is a package that needs other packages, which imports them inside the package,
  right before the item that uses them.
- Import the module's main package first, then any others. Only import packages that are actually used.
- Formal `_props` modules have no imports.

## 3. Naming

| Kind | Convention | Examples |
|---|---|---|
| Modules, packages, files | `lower_snake_case` | `spi_target`, `spi_pkg`, `edge_detector` |
| Signals, ports, variables | `lower_snake_case` | `shift_reg`, `bit_count`, `host_irq` |
| Parameters, localparams | `UPPER_SNAKE_CASE` | `DEPTH`, `CLK_FREQ_HZ`, `DEVICE_ID`, `CMD_READ` |
| Enum values | `UPPER_SNAKE_CASE` with a shared prefix per enum | `SPI_IDLE`, `SPI_COMMAND`, `PIN_HIGH`, `PARITY_EVEN` |
| Types (typedef, enum, struct) | `lower_snake_case_t` | `byte_t`, `spi_state_t`, `control_t`, `count_t` |
| Type parameters | `UPPER_SNAKE_CASE`, ending in `_T` | `parameter type DATA_T = logic [7:0]` |
| Functions | `lower_snake_case`, verb-first for checks | `validate_spi_params`, `next_ptr`, `parity_error`, `min1_clog2` |
| Instances | **always** `u_` + module name (without a shared prefix); a numbered or role suffix may be added when there are several (`u_tx_fifo`, `u_rx_fifo`) | `u_fifo`, `u_edge_detector`, `u_protocol_emulator` |
| Instances (formal) | always `u_dut` | `counter #(...) u_dut (...)` |
| Assertion labels | `assert_<subject>_<behaviour>` / `assume_<...>` | `assert_count_wraps_when_enabled_at_max`, `assume_no_pop_when_empty` |
| Top-level pins | the names required by the board or template, verbatim | `ui_in`, `uo_out`, `uio_oe` |
| Loop variables | short, declared in the `for` | `for (int b = 0; b < 4; b++)` |

**Naming vocabulary and suffixes:**
- Use full words, apart from a small set of standard abbreviations: `addr`, `en`, `sel`, `cfg`, `ptr`,
  `acc`, `fmt`, `cmd` (in enum values and localparams only, signals use `command`).
- `_en`: an enable or "do this" flag (`shift_en`, `push_en`, `irq_en`).
- `_sel`: a mux select, typed with an enum (`pin_sel`, `response_sel`).
- `_next`: the combinational next-state value of a register (`state_next`, `bit_count_next`).
- `_raw` / `_eff`: a signal before / after some masking (`write_en_raw` → `write_en_eff`).
- `_in` / `_out`: the same signal entering and leaving a module that modifies or passes it on
  (`pps_in` / `pps_out`).
- `_d` (formal): a value delayed by one cycle (`rst_n_d`, `tick_d`).
- `_1` / `_2`: numbered ports / stages (`read_addr_1`, `sck_sync_1`, `sck_sync_2`).
- `_n`: an active-low signal (`cs_n`).
- `is_<x>`: a boolean classification (`is_read_command`).
- `debug_`: signals that only exist for observability (`debug_state`).
- Interface prefixes group related ports: `host_spi_*`, `engine_*`, `request_*` / `response_*`.
- Valid/ready handshakes use `_valid` / `_ready` (`request_valid`, `request_ready`).

## 4. Types and literals

- Use `logic` for all nets and variables. Never use `wire` or `reg`.
- **Prefer named typedefs over raw vectors** wherever a type exists (`byte_t`, `addr_t`, `count_t`). Raw
  `logic [N:0]` is used for odd widths that have no typedef (`logic [3:0] write_strobe`).
- Define local width-dependent types with `typedef` rather than repeating the expression:
  ```systemverilog
  typedef logic [min1_clog2(MODULO)-1:0] count_t;
  typedef logic [PTR_WIDTH-1:0] ptr_t;
  ```
- Encodings (mux selects, commands, states, formats) are **always `typedef enum` with an explicit base type
  and width**: `typedef enum logic [1:0] { ... } name_t;`. Enum values are **implicitly numbered unless the
  value matters** (e.g. values fixed by a spec or register map, which use explicit sized literals such as
  `= 8'h03`, padded so the `=` signs align).
- Group control signals into a `typedef struct packed` with aligned member names. Assignment patterns use
  names: `'{ field: value, ... }`.
- **Always use sized literals**: `1'b0`, `1'b1`, `4'b0011`, `8'h03`, `32'h0000_0013`.
  Use the fill literals `'0`, `'1` and `'x` for whole-vector constants.
- Underscores group digits: `32'h8000_0000`, `50_000_000`, `115_200`.
- Unsized decimal integers are fine in arithmetic: `count + 1`, `bit_count == 7`, `(addr != 0)`.
- Use explicit casts rather than relying on implicit widening/narrowing: `byte_t'(count)`,
  `count_t'(MODULO-1)`, `count_t'(LATENCY)`, `int'(byte_offset)`, `unsigned'($clog2(x))`, `$signed(a)`,
  `$unsigned(...)`.
- Use `!` for logical NOT and `~` only for bitwise operations. Use `&&` / `||` for logic, and reduction
  operators where they fit (`|addr[1:0]`, `^data_in`, `~^data_in`, `&frame[...]`).
- Unpacked memories put the depth after the name as `[DEPTH-1:0]` (`byte_t data [DEPTH-1:0];`).
  Byte-addressable memories use packed arrays: `logic [3:0][7:0] data [DEPTH-1:0];`.

## 5. Module headers: parameters and ports

- ANSI-style headers only. Layout:
  ```systemverilog
  module name #(
      parameter <type> NAME = default,
      ...
  ) (
      <ports>
  );
  ```
  Without parameters: `module name (` ... `);`.
- **Parameters always have an explicit type**: `parameter int unsigned DEPTH = 256`,
  `parameter bit WRITE_THROUGH = 1'b0`, `parameter spi_mode_t MODE = SPI_MODE_0`,
  `parameter type DATA_T = logic [7:0]`. The single exception is file-path parameters, which are left
  untyped on purpose (some tools reject `string` for `$readmemh`). The exception is commented where it is
  used, and the untyped parameter is padded so its name lines up with the typed ones:
  ```systemverilog
  parameter int unsigned DEPTH      = 256,
  parameter              IMAGE_PATH = DEFAULT_IMAGE_PATH
  ```
- **Column alignment in port and parameter lists:** direction, type, name and `=` each line up in columns.
  - `input` is padded with two spaces to match `output`'s width (`input  logic`) **whenever the list
    contains an `output`**. If every port is an input (testbench-style wrappers, `_props` modules), use a
    single space (`input logic clk,`).
  - Types are padded to the widest type in the list, so names start in one column.
  - Example:
    ```systemverilog
    module fifo #(
        parameter type         DATA_T = logic [7:0],
        parameter int unsigned DEPTH  = 16
    ) (
        input  logic  clk,
        input  logic  rst_n,

        // Write port
        input  logic  push_en,  // Ignored while full
        input  DATA_T push_data,
        output logic  full,

        // Read port
        input  logic  pop_en,  // Ignored while empty
        output DATA_T pop_data,
        output logic  empty
    );
    ```
  - Alignment is per list. A very long type can break alignment for one or two lines; that's acceptable
    but not preferred.
- One port per line. There is no comma after the last port, and the closing `);` sits on its own line at
  column 0.
- `clk` comes first, then `rst_n`, then a blank line, then the functional ports.
- **Port ordering:** ports are grouped by **interface or function**, with inputs and outputs mixed inside a
  group in dataflow order. Groups are separated by blank lines and usually headed by a `//` comment (see the
  example above).
- Trailing `// comments` on ports explain units, timing or semantics: `// Active low`,
  `// One bit per byte of write_data`, `// Held for one cycle`, `// In clk cycles`.

## 6. Declarations

- One signal per line, and declarations are aligned into a type column and a name column within each block:
  ```systemverilog
  logic [2:0] bit_count;
  byte_t      shift_reg;
  spi_state_t state;
  ```
  Large declaration blocks align to the longest type in the block, even when that leaves big gaps.
- **Declare signals close to where they are used**, at the top of the section that drives them, rather than
  all at the top of the module. Signals that are needed before their driving section are declared earlier
  under a `// Forward declaration(s)` comment:
  ```systemverilog
  // Forward declarations
  byte_t rx_byte;
  logic  rx_valid;
  ```
- `localparam`s always have a type (`localparam int unsigned PTR_WIDTH = $clog2(DEPTH);`,
  `localparam logic [7:0] CMD_READ = 8'h03;`). Values in a group of localparams are aligned on `=`.
- `localparam`s that depend on parameters are declared just after the validating `initial` block.
- Attributes go on the same line, before the declaration: `(* keep *) spi_state_t debug_state;`.

## 7. Procedural blocks

- **`always_comb`** for combinational logic and **`always_ff @(posedge clk)`** for sequential logic. Plain
  `always @(posedge clk)` is used **only** when an `initial` block (`$readmemh`, power-up values) also writes
  the same variables, and this is always explained with a comment:
  ```systemverilog
  // Not always_ff, since the initial block's $readmemh also writes to data
  always @(posedge clk) begin
  ```
- Reset style:
  - Use an **active-low synchronous** reset named `rst_n` (as required by Tiny Tapeout):
    `always_ff @(posedge clk) begin if (!rst_n) ...`. Never use an asynchronous reset.
  - Only reset the registers that need it. Datapath registers are typically left out of the reset branch,
    which only resets control/valid state, and this is sometimes commented (`// Only the valid bits need to
    be reset`). Flush and reset share a branch: `if (!rst_n || flush) begin`.
  - Priority chains run `if (!rst_n) ... else if (...) ... else if (...)`.
- **Blocking (`=`) in `always_comb`, non-blocking (`<=`) in `always_ff`.** Never mix them.
- **`always_comb` structure:** first assign a default to *every* output of the block, then a blank line,
  then the `case`/`if` logic. Defaults are aligned on `=`:
  ```systemverilog
  always_comb begin
      state_next     = state;
      bit_count_next = bit_count;

      unique case (state)
          ...
      endcase
  end
  ```
  - For a fully decoded `unique case` mux, the default is `'x`: `result = 'x;`.
  - For control decoders, the defaults are safe no-op values, commented
    (`// The default values do not change any state`).
  - State machines default `*_next` to the current value and pulses to `1'b0`.
- **FSMs** use two blocks: a `// Next state logic` `always_comb` computing `*_next`, and an `always_ff`
  that registers them. The state enum is local to the module or in the package, and each state gets a
  trailing comment explaining it:
  ```systemverilog
  typedef enum logic [1:0] {
      SPI_IDLE,     // Waiting for cs_n to be asserted
      SPI_COMMAND,  // Shifting in the command byte
      SPI_DATA      // Shifting data in or out until cs_n is deasserted
  } spi_state_t;
  ```
- Combinational loops that need iteration use `for (int b = 0; b < 4; b++)` inside `always`/`always_comb`,
  and generate blocks are avoided.
- Small helpers are written as `function automatic` with ANSI `input` arguments (see section 13).

## 8. `begin`/`end`, `if` and `case`

- `begin` goes on the **same line** as its `if` / `else` / `always` / `case item` / `initial`.
  `end else begin` and `end else if (...) begin` are written on one line.
- **`begin ... end` is omitted for single-statement bodies** in `if`/`else` chains. The statement goes on
  the next line, indented:
  ```systemverilog
  always_ff @(posedge clk) begin
      if (!rst_n)
          count <= '0;
      else
          count <= count_en ? count + 1 : count;
  end
  ```
  But if **any** branch of an `if`/`else` chain needs `begin`/`end`, all branches use it:
  ```systemverilog
  if (!rst_n) begin
      state <= SPI_IDLE;
  end else begin
      state     <= state_next;
      bit_count <= bit_count_next;
  end
  ```
  Wrapping a single-statement `if` in `begin`/`end` is accepted, but the brace-less form is preferred.
- The `always`/`initial` body itself always uses `begin`/`end`. The one exception is the formal files'
  one-liner `always_ff @(posedge clk)` followed by an indented single statement.
- **Case statements:**
  - Use `unique case` whenever the cases are exhaustive over an enum (muxes, decoders and FSMs over typed
    enums). Use plain `case` when matching raw bit patterns with a `default` (e.g. a command byte, or
    `{push_ok, pop_ok}`).
  - Enum `unique case` statements have **no `default`**. Every enum value is listed instead, including
    no-op ones (`PIN_NOP:` followed by an indented `;`).
  - Plain `case` always has a `default`. An intentional no-op is `default: ;`, with a trailing comment if
    it isn't obvious (`default: ;  // For now, ignore writes to unimplemented registers`).
  - **Single-statement items go on one line, with the statements aligned in a column** (the column after
    the longest label + `:` + one space):
    ```systemverilog
    unique case (pin_sel)
        PIN_LOW:    pin_out = 1'b0;
        PIN_HIGH:   pin_out = 1'b1;
        PIN_ENGINE: pin_out = engine_out;
    endcase
    ```
    When items assign different left-hand sides, the `=` signs are aligned as well:
    ```systemverilog
    case (command)
        CMD_READ:  read_en       = 1'b1;
        CMD_WRITE: write_en      = 1'b1;
        default:   command_error = 1'b1;
    endcase
    ```
  - When a statement is too long, or the case mixes one-line and `begin`/`end` items, put the label alone on
    its line and indent the statement below it:
    ```systemverilog
    unique case (state)
        SPI_IDLE:
            state_next = !cs_n ? SPI_COMMAND : SPI_IDLE;
        SPI_COMMAND:
            state_next = command_done ? SPI_DATA : SPI_COMMAND;
        SPI_DATA: begin
            shift_en   = 1'b1;
            state_next = cs_n ? SPI_IDLE : SPI_DATA;  // Deasserting cs_n ends the transaction
        end
    endcase
    ```
  - Multi-statement items use `LABEL: begin` ... `end`. Large decoders separate multi-line items with a blank
    line. Compact ones don't.
  - A nested `case` is indented normally inside a `begin`/`end` item.

## 9. Assignments and expressions

- `assign` statements: one per line, grouped, with `=` **aligned within a group**:
  ```systemverilog
  assign cs_active = !cs_n;
  assign sck_rise  = sck_sync && !sck_prev;
  assign sck_fall  = !sck_sync && sck_prev;
  ```
  The same applies to groups of `<=` and `=` in procedural blocks:
  ```systemverilog
  bit_count <= '0;
  shift_reg <= '0;
  state     <= SPI_IDLE;
  ```
- Parenthesise comparisons inside larger boolean expressions:
  `push_en && (count == DEPTH)`, `(state == SPI_IDLE) && !cs_n`. A lone comparison on the right of an
  `assign` is also often parenthesised: `assign empty = (count == '0);`.
- Ternaries are used for 2-way selects: `count_en ? count + 1 : count`.
- **Wrapping long boolean expressions:** break *before* the operator (`||`, `&&`) and align the operator
  under the first operand after `=`, so the operands line up:
  ```systemverilog
  assign transfer_error = (state == SPI_COMMAND && cs_n)
                       || (state == SPI_DATA    && overflow);
  ```
  (Note the extra spaces in `SPI_DATA    &&` to align the `&&` with the line above.)
- **Wrapping a long ternary:** put `?` and `:` at the start of indented continuation lines:
  ```systemverilog
  assign response = (state == SPI_DATA)
      ? register_read_data
      : STATUS_IDLE;
  ```
  or align the `:` under the `?`:
  ```systemverilog
  pin_out[b] = (override_en && override_mask[b]) ? override_value[b]
                                                 : engine_out[b];
  ```
- **Long concatenations** are split one element per line, with the braces on their own lines, and comments
  on individual elements as needed:
  ```systemverilog
  status = {
      busy,
      overflow,
      {2{1'b0}},
      channel,
      parity  // Odd parity over the other fields
  };
  ```
  Short ones stay inline: `{{4{data[3]}}, data[3:0]}`, `{addr[7:1], 1'b0}`.
- A grouped multi-line condition may open a parenthesis at the end of the line:
  ```systemverilog
  assign start_transfer = cs_active && !busy && (
      (command == CMD_READ) ||
      (command == CMD_WRITE)
  );
  ```
- Fields of packed words (commands, headers, frames) are extracted with `assign`s to named signals rather
  than used inline.

## 10. Module instantiation

- **Named port connections only**, one per line. The instance name goes on the line with the module name
  (or after the `#(...)` block):
  ```systemverilog
  edge_detector u_edge_detector (
      .clk    (clk),
      .rst_n  (rst_n),
      .in     (sck_sync),
      .rising (sck_rise),
      .falling(sck_fall)
  );
  ```
- **Alignment:** the opening `(` of every connection is aligned to the column just after the
  **longest port name**, so the longest port has *no* space before its `(` and the rest are padded:
  `.falling(sck_fall)` and `.in     (sck_sync)`. The same applies to parameter overrides:
  ```systemverilog
  fifo #(
      .DATA_T(byte_t),
      .DEPTH (TX_FIFO_DEPTH)
  ) u_tx_fifo (
  ```
- Parameterised instances: `module_name #(` / overrides / `) u_inst (` / ports / `);`. A short override
  may carry a trailing comment: `.DEPTH(4)  // Only needs to hold one SPI transaction`.
- Ports are listed in the same order as in the module's declaration. No blank lines go between connections.
- Unused outputs are left empty, and unused inputs are tied off with sized/fill constants. A comment above
  the instance explains why:
  ```systemverilog
  // The command FIFO is never flushed, and the decoder pops it without checking empty
  fifo u_command_fifo (
      ...
      .flush    (1'b0),
      .empty    (),
      ...
  ```
- `.*`, `.name` implicit connections and positional connections are never used.
- Struct fields may be connected directly: `.data(rx_frame.data)`.

## 11. Parameter validation and assertions

- Every parameterised module validates its parameters in an `initial` block at the **top of the module
  body**, using immediate assertions with `$fatal(1, "...")`. The `else` goes on the next line, indented
  one level:
  ```systemverilog
  initial begin
      assert (DEPTH >= 2 && (DEPTH & (DEPTH - 1)) == 0)
          else $fatal(1, "DEPTH must be a power of 2 and at least 2.");

      $readmemh(IMAGE_PATH, data);
  end
  ```
- Messages name the parameter in UPPER_CASE and state the requirement as a **full sentence ending in a
  period** (`"LATENCY must be at least 1."`).
- A space goes between `assert` and `(`: `assert (cond)`.
- Validation shared between modules goes in a package function (`validate_spi_params`) called from the
  `initial` block, with one argument per line:
  ```systemverilog
  initial begin
      validate_spi_params(
          CLK_FREQ_HZ,
          SCK_FREQ_HZ
      );
  end
  ```
- Structural checks that depend on the whole design (e.g. checking that a register map is consistent) may
  go in an `initial` block at the bottom of the module.

### Formal property files (`formal/*_props.sv`)

- Wrapper module `<dut>_props` with the same (or abstracted) parameters, **all DUT inputs as `input`
  ports** (single-space `input logic`), and DUT outputs declared as internal `logic`.
- The DUT instance is always named `u_dut`, and its connections follow section 10.
- Parameters that must match DUT defaults or are abstractions carry trailing comments
  (`// Must match counter's default WIDTH`, `// An abstraction, not a real gap (see below)`), with the
  comments aligned into one column.
- Section comments, in this order: `// Assume environment constraints`, `// Assert liveness properties`,
  `// Assert safety properties`.
- Every property is **labelled**, with the label on its own line and the property indented one level under
  it. The body sits on its own line, indented again, and `);` closes it on its own line:
  ```systemverilog
  assert_count_wraps_when_enabled_at_max:
      assert property (@(posedge clk)
          (past_valid && $past(en && count == MAX_COUNT)) |-> (count == 0)
      );
  ```
- Helper state (gap counters, `past_valid`, shadow models) is written as normal RTL right before the
  properties that use it, with a comment block explaining the abstraction. Tool limitations are documented
  inline (`// The guards are written explicitly because EBMC does not support disable iff`).
- Safety properties are guarded with `past_valid` / `rst_n` instead of `disable iff`. Liveness properties
  use `|=> s_eventually (...)`.

## 12. Comments

This is the most distinctive part of the style. Comments explain **why**, constraints, timing and
non-obvious behaviour. They never restate the code.

- **Only `//` line comments.** Never use `/* */`, except for the licence block at the top of each file
  (see section 2).
- **Trailing (inline) comments are separated from the code by two spaces** before `//`
  (`x = y;  // ...`), never one. Trailing comments on consecutive lines are usually **not** column-aligned
  with each other, except in enum value lists, FSM state lists and formal parameter lists. There they are
  aligned, with two spaces after the longest line.
- **Grammar:** comments are written in proper English, with correct grammar and punctuation.
  - A comment starts with a **capital letter**, unless it starts with an identifier, which keeps its own
    case (`// cs_n is synchronised before use`).
  - A comment that is a **single sentence** may leave out the terminating full stop
    (`// Synchronous write, with writes to address 0 ignored`).
  - A comment made of **more than one sentence** ends every sentence with a full stop, including the last.
    This applies whether the sentences share a line or are split over several `//` lines.
  - Short labels (section headers, port group headers, units such as `// In clk cycles`) are noun phrases
    and take no full stop.
- **British spelling** throughout: synchronise, optimise/optimised, synthesiser, initialised, organisation,
  modelled, behaviour.
- Identifiers are referenced verbatim inside comments without quotes or backticks
  (`// Byte at read_addr from the previous cycle`). Acronyms are uppercase (SPI, FIFO, IRQ, PPS).
- Arrows: `->` for data flow/paths (`// sck -> shift register -> rx FIFO`) and `<->` for interfaces between
  two blocks (`// SPI target <-> command decoder`).
- Ellipses and emphasis are avoided, though "etc." and "e.g." appear occasionally.

**Comment types and where they go:**

1. **Module description:** an optional `//` block directly above `module` (with no blank line between),
   saying what the module is, its key behaviour and its constraints. Wrap it at roughly 100 columns:
   ```systemverilog
   // Single-clock FIFO with a registered read port, so that it can be inferred as block RAM.
   // The read data is valid one cycle after pop_en.
   module fifo #(
   ```
   Simple modules have no description.
2. **Port group headers:** `// Host SPI interface`, `// Write port`, `// Status flags, to the host
   registers`. A header may span two lines when it gives extra context:
   ```systemverilog
   // Host SPI interface, synchronised to clk before use.
   // sck must run at no more than a quarter of the clk frequency.
   ```
3. **Section headers inside module bodies:** a short noun phrase naming the hardware block, placed above its
   declarations, e.g. `// Input synchronisers`, `// Shift register`, `// Command decoder`,
   `// Next state logic`, `// Status register`.
4. **Banner headers (large multi-stage modules only):** used to mark the major stages or paths of a large
   module. The `=` rule is 73 characters after `// ` and indented one level, with a blank line after the
   banner and two blank lines before the next one:
   ```systemverilog


       // =========================================================================
       // Receive path
       // =========================================================================

       // Input synchronisers
   ```
5. **Explanatory comments above a statement or block**, explaining design rationale:
   ```systemverilog
   // The edge detection runs on the synchronised sck, so a bit is sampled
   // two clk cycles after the sck edge that clocks it
   assign sck_rise = sck_sync && !sck_prev;
   ```
   ```systemverilog
   // Must stay disabled when the read data feeds back into the write data,
   // where the bypass would form a combinational loop
   parameter bit WRITE_THROUGH = 1'b0
   ```
   A comment inside a `case` sits above the item it explains, preceded by a blank line:
   ```systemverilog
           CMD_STATUS: response = status;

           // The ID register is read-only, so writes to it are ignored
           CMD_ID:     response = DEVICE_ID;
   ```
6. **Trailing comments** for short facts about one line: units (`// In clk cycles`), encodings
   (`// CPOL = 0, CPHA = 0`), priorities (`// Reset takes precedence over flush`), safety notes
   (`// Suppress the write if the FIFO is full`), sign behaviour (`// Sign extend`), and decoded command
   names on decoder lines (`// READ`, `// WRITE`).
   A trailing comment on `if`/`else if` explains the priority of that branch:
   ```systemverilog
   if (!rst_n)  // Global reset has top priority
       bit_count <= '0;
   else if (cs_n)  // Deasserting cs_n discards a partially received byte
       bit_count <= '0;
   else if (sck_rise)
       bit_count <= bit_count + 1;
   ```
7. **Spec/tool references and justifications** are explicit: `// Command encoding as per the datasheet`,
   `// Defined by the Makefile for gate-level simulation (GL_TEST=1)`,
   `// Untyped rather than string, since some tools reject string parameters as $readmemh file names`.
8. **"For now" / future notes** flag unimplemented behaviour: `// For now, return 0 for unimplemented
   registers`, `// This allows timeouts to be handled in the future`. There are no `TODO`/`FIXME` tags in
   the RTL.
9. **Behaviour notes for memories:** `// Synchronous write`, `// Asynchronous read`,
   `// Upper address bits are ignored, so out-of-range addresses wrap around`,
   `// Reading the word being written returns the old data`.

**Comment voice:** declarative present tense, describing what the hardware does or must do. Typical
patterns are "X, so Y" / "X, since Y" / "X, to Y" (`// Not always_ff, since the initial block also writes to
these`, `// The comparison is registered to keep it off the critical path`). Use "must" for invariants
(`// Must remain constant until the transfer finishes`). Avoid "we".

## 13. Packages

- A package holds typedefs, enums, structs, localparams and `function automatic` helpers, indented one level
  inside `package` / `endpackage`.
- Blank lines separate each typedef/enum/function.
- Enum lists put one value per line. Trailing comments on values are allowed (`CMD_READ,  // Reads one
  register`).
- Global constants are typed localparams with aligned `=`, and short trailing comments:
  ```systemverilog
  localparam logic [7:0] DEVICE_ID  = 8'hA5;

  // Mode 0 is the most widely supported SPI mode
  localparam spi_mode_t  RESET_MODE = SPI_MODE_0;  // CPOL = 0, CPHA = 0
  ```
- Preprocessor conditionals (`` `ifdef `` / `` `else `` / `` `endif ``) start at **column 0** even inside a
  package, while the code inside them keeps its normal indentation. Macros are otherwise avoided entirely.
- Struct-typed constants use a named assignment pattern with values aligned after the colons:
  ```systemverilog
  localparam control_t CONTROL_IDLE = '{
      shift_en:     1'b0,
      load_en:      1'b0,
      ...
      irq_en:       1'b0
  };
  ```
  (The variant `field : value` with aligned colons is also fine, but stay consistent within a block.)
- Functions: `function automatic <ret_type> name(` and then one `input <type> name` per line, with aligned
  types, then `);`. A single short argument may stay inline:
  `function automatic void validate_divider_param(input int unsigned divider);`. Return with `return`.
- A comment explaining the package-level decision goes above the item
  (`// Kept flat rather than nested, so that the cocotb testbenches can access each field`).

## 14. Quick checklist for generated code

- [ ] Apache-2.0 SPDX licence block at the top of every `.sv` file
- [ ] 4-space indent, no tabs, no trailing whitespace, newline at EOF
- [ ] `import pkg::*;` at file scope above `module`, then a blank line, then an optional `//` description
      directly above `module`
- [ ] ANSI header, typed parameters, and aligned direction/type/name columns (`input  ` padded when outputs exist)
- [ ] `clk`, `rst_n` first, then a blank line; ports grouped by interface with `//` headers
- [ ] `initial` parameter validation with `assert (...)` and an indented `else $fatal(1, "...");`
- [ ] `logic` only, with typedefs wherever they exist, enums for every select/command/state, sized literals
      and explicit casts
- [ ] Signals declared near their use, with `// Forward declarations` where needed
- [ ] `always_comb` defaults every output first (with `'x` for full `unique case` muxes), then a blank line,
      then the logic
- [ ] `always_ff` with `<=`, synchronous active-low `rst_n`, `if (!rst_n)` first
- [ ] Brace-less single-statement `if`/`else` (consistent within a chain); `end else begin` on one line
- [ ] `unique case` over enums with no `default`; plain `case` with a `default`; aligned one-line items
- [ ] `=`, `<=`, `assign` and declaration columns aligned within each group
- [ ] Instances: `u_<name>` (required), named connections, `(` aligned after the longest port, ports in declaration order
- [ ] Long boolean expressions wrapped with leading `||` / `&&` aligned under the first operand
- [ ] `//` comments only, two spaces before trailing comments, British spelling, explaining *why*
- [ ] Comments in proper English starting with a capital letter; a full stop is optional for a single
      sentence and required on every sentence of a multi-sentence comment
- [ ] Single blank lines between groups, two blank lines between major sections, `// ====` banners only
      for large multi-stage modules
