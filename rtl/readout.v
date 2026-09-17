// Push the three latched counts out of the UART, most significant byte first.
//
// Serialising is not a nicety. Three 32-bit counters brought out as pins
// would need 96 of them; the small FPGAs this is aimed at have around 39 in
// total, so a parallel readout is not merely wasteful, it does not fit. This
// was found by trying to place the design, not by guessing.
//
// Twelve bytes go out per snapshot: A, then B, then coincidences.

module readout #(
    parameter CLKS_PER_BIT = 868
) (
    input  wire clk,
    input  wire rst,
    input  wire [31:0] a_count,
    input  wire [31:0] b_count,
    input  wire [31:0] c_count,
    input  wire start,                  // one cycle, ignored mid-transfer
    output wire tx,
    output wire busy
);

    reg [95:0] shifter;
    reg [3:0] bytes_left;
    reg [7:0] byte_out;
    reg send;

    wire uart_busy;
    assign busy = (bytes_left != 0) | uart_busy;

    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) uart (
        .clk(clk), .rst(rst),
        .data(byte_out), .send(send),
        .tx(tx), .busy(uart_busy)
    );

    always @(posedge clk) begin
        send <= 1'b0;

        if (rst) begin
            bytes_left <= 0;
        end else if (bytes_left == 0) begin
            if (start) begin
                shifter <= {a_count, b_count, c_count};
                bytes_left <= 12;
            end
        end else if (!uart_busy && !send) begin
            // `send` is checked as well as `uart_busy` because busy only
            // rises the cycle after send, and without the guard we would
            // push a second byte into that one-cycle gap.
            byte_out <= shifter[95:88];
            shifter <= {shifter[87:0], 8'h00};
            bytes_left <= bytes_left - 1'b1;
            send <= 1'b1;
        end
    end

endmodule
