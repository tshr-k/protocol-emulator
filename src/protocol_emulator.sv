/*
 * SPDX-License-Identifier: Apache-2.0
 */

module protocol_emulator (
    input  logic       clk,
    input  logic       rst_n,          // Active-low synchronous reset

    // Host SPI (slave)
    input  logic       host_spi_sck,
    input  logic       host_spi_cs_n,
    input  logic       host_spi_mosi,
    output logic       host_spi_miso,
    output logic       host_irq,

    output logic       trig,
    input  logic       pps_in,
    output logic       pps_out,

    // Engine pins
    input  logic [7:0]   engine_io_in,   // P0-P7 bidirectional: input path
    output logic [7:0]   engine_io_out,  // P0-P7 bidirectional: output path
    output logic [7:0]   engine_io_oe,   // P0-P7 bidirectional: 1 = drive
    input  logic [11:8]  engine_in,      // P8-P11 input only
    output logic [15:12] engine_out      // P12-P15 output only
);
    assign host_spi_miso = '0;
    assign host_irq      = '0;
    assign trig          = '0;
    assign pps_out       = '0;
    assign engine_io_out = '0;
    assign engine_io_oe  = '0;
    assign engine_out    = '0;
endmodule
