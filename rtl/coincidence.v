// Two-channel coincidence with a programmable window.
//
// A particle passing through both detectors fires them at essentially the
// same instant. Noise in one detector knows nothing about the other. So
// demanding that both channels fire within a window of WIDTH clock cycles
// throws away the uncorrelated noise and keeps the real events.
//
// It does not throw away all of it: two noise pulses will occasionally land
// inside the window by chance. That accidental rate is predictable --
// 2*tau*R1*R2 -- and this module is built to count exactly the pairs that
// formula counts, so the prediction can be tested rather than assumed.
//
// Each channel holds a "recently fired" flag for WIDTH cycles after its
// pulse, including the pulse cycle itself. A coincidence is declared when a
// pulse arrives on one channel while the other is still flagged. If both
// arrive together the OR collapses to a single count, not two.

module coincidence #(
    parameter WINDOW_BITS = 16
) (
    input  wire clk,
    input  wire rst,
    input  wire a_pulse,
    input  wire b_pulse,
    input  wire [WINDOW_BITS-1:0] window,   // in clock cycles
    output wire coincident
);

    reg [WINDOW_BITS-1:0] a_left, b_left;   // cycles of window remaining

    always @(posedge clk) begin
        if (rst) begin
            a_left <= 0;
            b_left <= 0;
        end else begin
            a_left <= a_pulse ? window : (a_left > 0 ? a_left - 1'b1 : 0);
            b_left <= b_pulse ? window : (b_left > 0 ? b_left - 1'b1 : 0);
        end
    end

    wire a_recent = a_pulse | (a_left > 0);
    wire b_recent = b_pulse | (b_left > 0);

    assign coincident = (a_pulse & b_recent) | (b_pulse & a_recent);

endmodule
