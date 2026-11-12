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
    protocol_emulator u_protocol_emulator (
        .clk          (clk),
        .rst_n        (rst_n),
        .host_spi_sck (ui_in[0]),
        .host_spi_cs_n(ui_in[1]),
        .host_spi_mosi(ui_in[2]),
        .host_spi_miso(uo_out[0]),
        .host_irq     (uo_out[1]),
        .trig         (uo_out[2]),
        .pps_in       (ui_in[3]),
        .pps_out      (uo_out[3]),
        .engine_io_in (uio_in),       // P0-P7
        .engine_io_out(uio_out),      // P0-P7
        .engine_io_oe (uio_oe),       // P0-P7
        .engine_in    (ui_in[7:4]),   // P8-P11
        .engine_out   (uo_out[7:4])   // P12-P15
    );
endmodule
