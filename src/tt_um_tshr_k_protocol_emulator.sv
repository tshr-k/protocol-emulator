/*
 * SPDX-License-Identifier: Apache-2.0
 */

// Tiny Tapeout wrapper: maps the generic TT pins onto protocol_emulator's named ports.
// Pin assignment must match the pinout in `info.yaml`.
module tt_um_tshr_k_protocol_emulator (
    input  logic [7:0] ui_in,    // Dedicated inputs
    output logic [7:0] uo_out,   // Dedicated outputs
    input  logic [7:0] uio_in,   // IOs: Input path
    output logic [7:0] uio_out,  // IOs: Output path
    output logic [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  logic       ena,      // Always 1 when the design is powered, so you can ignore it
    input  logic       clk,      // Clock
    input  logic       rst_n     // Active-low synchronous reset
);
    logic [7:0] core_uo;

    protocol_emulator u_protocol_emulator (
        .clk          (clk),
        .rst_n        (rst_n),
        .host_spi_sck (ui_in[0]),
        .host_spi_cs_n(ui_in[1]),
        .host_spi_mosi(ui_in[2]),
        .host_spi_miso(core_uo[0]),
        .host_irq     (core_uo[1]),
        .trig         (core_uo[2]),
        .pps_in       (ui_in[3]),
        .pps_out      (core_uo[3]),
        .engine_io_in (uio_in),       // P0-P7
        .engine_io_out(uio_out),      // P0-P7
        .engine_io_oe (uio_oe),       // P0-P7
        .engine_in    (ui_in[7:4]),   // P8-P11
        .engine_out   (core_uo[7:4])   // P12-P15
    );

    // TEMPORARY placeholder -- remove once protocol_emulator has real logic.
    // The core is still a stub, so synthesis strips every input. LibreLane's
    // Checker.DisconnectedPins then flags all 19 top-level inputs as critical,
    // since it only does so when *no* input reaches a cell. Registering an XOR of
    // the inputs onto TRIG keeps them connected.
    logic placeholder_q;
    always_ff @(posedge clk) begin
        if (!rst_n) placeholder_q <= 1'b0;
        else        placeholder_q <= ^{ui_in, uio_in, ena};
    end

    assign uo_out = core_uo ^ {5'b0, placeholder_q, 2'b0};
endmodule
