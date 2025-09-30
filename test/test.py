# test/test.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer

# ui_in bit mapping (must match project.v)
EN   = 0   # count enable
LOAD = 1   # synchronous load
OE   = 2   # tri-state control for uio_* (1=drive, 0=Z via uio_oe)

async def reset(dut):
    dut.rst_n.value = 0
    # make sure inputs are quiet during reset
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    await Timer(25, units="ns")
    dut.rst_n.value = 1
    # wait a little after deasserting reset
    await Timer(5, units="ns")

@cocotb.test()
async def counter_basic(dut):
    """Program, count, and tri-state checks."""

    # 50 MHz clock (period 20 ns)
    cocotb.start_soon(Clock(dut.clk, 20, units="ns").start())

    # ena is high when design is powered/selected
    dut.ena.value = 1

    # Reset
    await reset(dut)

    # Enable outputs (OE=1), EN=0, LOAD=0
    ui = 0
    ui |= (1 << OE)   # OE=1
    dut.ui_in.value = ui
    await Timer(1, units="ns")

    # After reset, count should be 0
    assert int(dut.uo_out.value) == 0, f"after reset got {int(dut.uo_out.value):02x}"

    # Program 0xF0 via uio_in and pulse LOAD
    dut.uio_in.value = 0xF0
    dut.ui_in.value = ui | (1 << LOAD)  # LOAD=1
    await RisingEdge(dut.clk)
    dut.ui_in.value = ui                # LOAD=0
    await Timer(1, units="ns")
    assert int(dut.uo_out.value) == 0xF0, f"after load got {int(dut.uo_out.value):02x}"

    # Count 3 cycles (EN=1)
    dut.ui_in.value = ui | (1 << EN)
    for _ in range(3):
        await RisingEdge(dut.clk)
    await Timer(1, units="ns")
    assert int(dut.uo_out.value) == 0xF3, f"after 3 inc got {int(dut.uo_out.value):02x}"

    # Tri-state the uio_* bus (OE=0 -> uio_oe should be 0x00)
    dut.ui_in.value = (ui & ~(1 << OE)) | (1 << EN)  # EN=1, OE=0
    await Timer(1, units="ns")
    uio_oe = int(dut.uio_oe.value)
    assert uio_oe == 0x00, f"uio_oe expected 00 got {uio_oe:02x}"

    # Re-enable OE and check uio_oe becomes 0xFF
    dut.ui_in.value = (dut.ui_in.value.integer | (1 << OE))
    await Timer(1, units="ns")
    uio_oe = int(dut.uio_oe.value)
    assert uio_oe == 0xFF, f"uio_oe expected FF got {uio_oe:02x}"
