/*
 * 8-bit programmable counter for Tiny Tapeout
 * - Async active-low reset (rst_n)
 * - Synchronous load
 * - Count enable
 * - Tri-stateable outputs on the uio_* bus (via uio_oe)
 *
 * Pin map (ui_in):
 *   ui_in[0] = en    (count enable)
 *   ui_in[1] = load  (synchronous load)
 *   ui_in[2] = oe    (1 = drive uio_out, 0 = tri-state)
 *   ui_in[7:3] = unused
 *
 * Parallel load data comes from the bidirectional uio_in[7:0].
 * The current count is always visible on uo_out[7:0] (dedicated outputs),
 * and is also driven onto the uio_* bus when oe=1.
 */

`default_nettype none

// ---------- Tiny Tapeout top-level wrapper ----------
module tt_um_example (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // Control signals from ui_in
    wire en   = ui_in[0];
    wire load = ui_in[1];
    wire oe   = ui_in[2];

    // Parallel load data comes in on the bidirectional IOs
    wire [7:0] d = uio_in;

    // Counter output
    wire [7:0] count;

    // Core counter (no internal tri-states)
    prog_counter8_core u_core (
        .clk  (clk),
        .rst_n(rst_n),
        .load (load),
        .en   (en),
        .d    (d),
        .q    (count)
    );

    // Drive dedicated outputs for easy observation
    assign uo_out = count;

    // Tri-stateable bus on uio_* (Tiny Tapeout style: use OE lines)
    assign uio_out = count;
    assign uio_oe  = {8{oe}};   // oe=1 -> drive; oe=0 -> High-Z (input)

    // List unused to avoid warnings
    wire _unused = &{ena, ui_in[7:3], 1'b0};

endmodule

// ---------- Counter core (async reset, sync load) ----------
module prog_counter8_core (
    input  wire       clk,
    input  wire       rst_n,  // async, active-low
    input  wire       load,   // sync parallel load
    input  wire       en,     // count enable
    input  wire [7:0] d,      // data to load
    output reg  [7:0] q
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= 8'h00;                 // asynchronous clear
        end else if (load) begin
            q <= d;                     // synchronous load
        end else if (en) begin
            q <= q + 8'd1;              // increment
        end
    end
endmodule
