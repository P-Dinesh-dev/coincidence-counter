// Bring an asynchronous detector pulse into our clock domain, safely.
//
// The discriminator output has no idea our clock exists, so it can change
// exactly when a flip-flop is sampling it. That flip-flop then goes
// metastable: for a short while its output is neither 0 nor 1, and any logic
// reading it can disagree about which. Two flops in series fix this -- the
// first is allowed to go metastable and is given a full clock period to
// settle, and only the second is ever read.
//
// Having done that, we emit exactly one pulse per rising edge, so a wide
// input pulse counts once rather than once per clock cycle.

module pulse_in (
    input  wire clk,
    input  wire rst,
    input  wire async_in,
    output wire pulse        // one clock cycle, on each rising edge of async_in
);

    reg [2:0] shifted;

    always @(posedge clk) begin
        if (rst)
            shifted <= 3'b000;
        else
            // [0] may be metastable, [1] has settled, [2] is [1] delayed
            // so the pair can be compared for an edge.
            shifted <= {shifted[1:0], async_in};
    end

    assign pulse = shifted[1] & ~shifted[2];

endmodule
