// Free-running counters, latched together on a strobe.
//
// All three counters must be read from the same instant, otherwise the
// singles and the coincidences describe slightly different experiments and
// the accidental-rate prediction stops meaning anything. So they are latched
// on one common strobe and read out from the latches at leisure.

module counters #(
    parameter WIDTH = 32
) (
    input  wire clk,
    input  wire rst,
    input  wire a_pulse,
    input  wire b_pulse,
    input  wire coincident,
    input  wire latch,                    // one cycle: freeze a snapshot
    output reg  [WIDTH-1:0] a_count,
    output reg  [WIDTH-1:0] b_count,
    output reg  [WIDTH-1:0] c_count
);

    reg [WIDTH-1:0] a_live, b_live, c_live;

    always @(posedge clk) begin
        if (rst) begin
            a_live <= 0; b_live <= 0; c_live <= 0;
            a_count <= 0; b_count <= 0; c_count <= 0;
        end else begin
            a_live <= a_live + a_pulse;
            b_live <= b_live + b_pulse;
            c_live <= c_live + coincident;

            if (latch) begin
                a_count <= a_live + a_pulse;
                b_count <= b_live + b_pulse;
                c_count <= c_live + coincident;
            end
        end
    end

endmodule
