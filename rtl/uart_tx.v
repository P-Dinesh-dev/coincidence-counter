// Minimal 8N1 UART transmitter.
//
// One start bit low, eight data bits least-significant first, one stop bit
// high, each held for CLKS_PER_BIT cycles. Idle is high, so a disconnected
// line looks like an idle line rather than a permanent start bit.
//
// The whole frame is loaded into a shift register up front and clocked out of
// bit 0, which is why there is no state machine here: the register position
// *is* the state.

module uart_tx #(
    parameter CLKS_PER_BIT = 868        // 100 MHz / 115200 baud
) (
    input  wire clk,
    input  wire rst,
    input  wire [7:0] data,
    input  wire send,                   // one cycle, ignored while busy
    output wire tx,
    output wire busy
);

    reg [9:0] frame;
    reg [3:0] bits_left;
    reg [15:0] tick;

    assign busy = (bits_left != 0);
    assign tx = busy ? frame[0] : 1'b1;

    always @(posedge clk) begin
        if (rst) begin
            frame <= 10'h3FF;
            bits_left <= 0;
            tick <= 0;
        end else if (!busy) begin
            if (send) begin
                frame <= {1'b1, data, 1'b0};    // stop, data, start
                bits_left <= 10;
                tick <= 0;
            end
        end else if (tick == CLKS_PER_BIT - 1) begin
            tick <= 0;
            frame <= {1'b1, frame[9:1]};        // shift in idle behind us
            bits_left <= bits_left - 1'b1;
        end else begin
            tick <= tick + 1'b1;
        end
    end

endmodule
