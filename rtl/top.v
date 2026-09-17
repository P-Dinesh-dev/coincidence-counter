// The counter, assembled.
//
// Two asynchronous detector inputs in, three counts out. Nothing here
// corrects anything -- correction happens in software, on a PC, where it can
// be inspected and argued with. The FPGA's job is to count honestly and to
// say exactly how long it counted for.

module top #(
    parameter WINDOW_BITS = 16,
    parameter COUNT_WIDTH = 32
) (
    input  wire clk,
    input  wire rst,
    input  wire a_in,                      // asynchronous, from discriminator A
    input  wire b_in,                      // asynchronous, from discriminator B
    input  wire [WINDOW_BITS-1:0] window,
    input  wire latch,
    output wire [COUNT_WIDTH-1:0] a_count,
    output wire [COUNT_WIDTH-1:0] b_count,
    output wire [COUNT_WIDTH-1:0] c_count
);

    wire a_pulse, b_pulse, coincident;

    pulse_in in_a (.clk(clk), .rst(rst), .async_in(a_in), .pulse(a_pulse));
    pulse_in in_b (.clk(clk), .rst(rst), .async_in(b_in), .pulse(b_pulse));

    coincidence #(.WINDOW_BITS(WINDOW_BITS)) coinc (
        .clk(clk), .rst(rst),
        .a_pulse(a_pulse), .b_pulse(b_pulse),
        .window(window), .coincident(coincident)
    );

    counters #(.WIDTH(COUNT_WIDTH)) counts (
        .clk(clk), .rst(rst),
        .a_pulse(a_pulse), .b_pulse(b_pulse), .coincident(coincident),
        .latch(latch),
        .a_count(a_count), .b_count(b_count), .c_count(c_count)
    );

endmodule
