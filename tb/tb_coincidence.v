// Drive coincidence.v from a recorded stimulus file and report what it counts.
//
// The file holds one line per clock cycle, "a b", each 0 or 1. It is written
// by tb/run_tb.py from the same arrival times the Python model is given, so
// both implementations see byte-for-byte identical input and any difference
// in the answer is a real difference in behaviour.
//
// Sampling happens on the falling edge. By then the rising edge that opened
// this cycle has latched the previous cycle's state, and this cycle's inputs
// have been driven and settled, so the combinational output belongs entirely
// to one cycle. Sampling on the rising edge instead would straddle two.

`timescale 1ns / 1ps

module tb_coincidence;

    reg clk = 0;
    reg rst = 1;
    reg a_pulse = 0;
    reg b_pulse = 0;
    reg [15:0] window;

    wire coincident;

    integer stim, code, a_next, b_next;
    integer count = 0;

    coincidence #(.WINDOW_BITS(16)) dut (
        .clk(clk), .rst(rst),
        .a_pulse(a_pulse), .b_pulse(b_pulse),
        .window(window), .coincident(coincident)
    );

    always #5 clk = ~clk;          // 10 ns period, 100 MHz

    initial begin
        if (!$value$plusargs("window=%d", window)) window = 10;

        stim = $fopen("stim.txt", "r");
        if (stim == 0) begin
            $display("ERROR could not open stim.txt");
            $finish;
        end

        repeat (3) @(posedge clk);
        rst <= 0;
        @(posedge clk);

        forever begin
            code = $fscanf(stim, "%d %d\n", a_next, b_next);
            if (code != 2) begin
                $display("RESULT window=%0d count=%0d", window, count);
                $fclose(stim);
                $finish;
            end

            a_pulse <= a_next[0];
            b_pulse <= b_next[0];

            @(negedge clk);
            if (coincident) count = count + 1;
            @(posedge clk);
        end
    end

endmodule
