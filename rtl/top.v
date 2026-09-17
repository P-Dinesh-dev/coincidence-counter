// The counter, assembled.
//
// Two asynchronous detector inputs in, three counts out over one serial wire.
// Nothing here corrects anything -- correction happens in software, on a PC,
// where it can be inspected and argued with. Burning an estimator into fabric
// would make it the one part of the instrument nobody can check.
//
// Six pins: clk, rst, two detectors, a trigger and a serial line. The
// coincidence window is a synthesis parameter rather than a port, because
// bringing it out would cost sixteen pins on a device that has thirty-nine.
// A production build would set it through a config register over UART RX.

module top #(
    parameter WINDOW = 100,             // coincidence window, in clock cycles
    parameter CLKS_PER_BIT = 868,       // 100 MHz / 115200 baud
    parameter COUNT_WIDTH = 32
) (
    input  wire clk,
    input  wire rst,
    input  wire a_in,                   // asynchronous, from discriminator A
    input  wire b_in,                   // asynchronous, from discriminator B
    input  wire sample,                 // one cycle: freeze and send a snapshot
    output wire tx,
    output wire busy
);

    wire a_pulse, b_pulse, coincident;
    wire [COUNT_WIDTH-1:0] a_count, b_count, c_count;

    pulse_in in_a (.clk(clk), .rst(rst), .async_in(a_in), .pulse(a_pulse));
    pulse_in in_b (.clk(clk), .rst(rst), .async_in(b_in), .pulse(b_pulse));

    coincidence #(.WINDOW_BITS(16)) coinc (
        .clk(clk), .rst(rst),
        .a_pulse(a_pulse), .b_pulse(b_pulse),
        .window(WINDOW[15:0]), .coincident(coincident)
    );

    counters #(.WIDTH(COUNT_WIDTH)) counts (
        .clk(clk), .rst(rst),
        .a_pulse(a_pulse), .b_pulse(b_pulse), .coincident(coincident),
        .latch(sample),
        .a_count(a_count), .b_count(b_count), .c_count(c_count)
    );

    readout #(.CLKS_PER_BIT(CLKS_PER_BIT)) send (
        .clk(clk), .rst(rst),
        .a_count(a_count), .b_count(b_count), .c_count(c_count),
        .start(sample), .tx(tx), .busy(busy)
    );

endmodule
