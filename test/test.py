# test/test.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
import os

# ui_in bit mapping (must match project.v)
EN   = 0   # count enable
LOAD = 1   # synchronous load
OE   = 2   # tri-state control for uio_* (1=drive, 0=Z via uio_oe)

# Check if we're running gate-level simulation (for logging only)
is_gl = os.environ.get('GATES', 'no') == 'yes'

async def wait_for_propagation(dut):
    """Wait for signals to propagate through logic after a clock edge.
    
    In RTL: signals change on clock edge, need small delay for delta cycles.
    In gate-level: signals need time to propagate through multiple gates (1ns per gate).
    
    Wait for falling edge to sample in the stable middle of the clock period.
    """
    await FallingEdge(dut.clk)
    await Timer(1, units="ns")

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
    
    dut._log.info(f"Running test in {'GATE-LEVEL' if is_gl else 'RTL'} mode")

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
    await wait_for_propagation(dut)

    # After reset, count should be 0
    assert int(dut.uo_out.value) == 0, f"after reset got {int(dut.uo_out.value):02x}"

    # Program 0xF0 via uio_in and pulse LOAD
    dut.uio_in.value = 0xF0
    dut.ui_in.value = ui | (1 << LOAD)  # LOAD=1
    await RisingEdge(dut.clk)
    dut.ui_in.value = ui                # LOAD=0
    await wait_for_propagation(dut)
    
    actual_val = int(dut.uo_out.value)
    dut._log.info(f"After LOAD: expected 0xF0, got 0x{actual_val:02X}")
    assert actual_val == 0xF0, f"after load got {actual_val:02x}"

    # Count 3 cycles (EN=1)
    dut.ui_in.value = ui | (1 << EN)
    for _ in range(3):
        await RisingEdge(dut.clk)
    await wait_for_propagation(dut)
    
    actual_val = int(dut.uo_out.value)
    dut._log.info(f"After 3 counts: expected 0xF3, got 0x{actual_val:02X}")
    assert actual_val == 0xF3, f"after 3 inc got {actual_val:02x}"

    # Tri-state the uio_* bus (OE=0 -> uio_oe should be 0x00)
    dut.ui_in.value = (ui & ~(1 << OE)) | (1 << EN)  # EN=1, OE=0
    await wait_for_propagation(dut)
    
    uio_oe = int(dut.uio_oe.value)
    dut._log.info(f"After OE=0: expected uio_oe=0x00, got 0x{uio_oe:02X}")
    assert uio_oe == 0x00, f"uio_oe expected 00 got {uio_oe:02x}"

    # Re-enable OE and check uio_oe becomes 0xFF
    dut.ui_in.value = (dut.ui_in.value.integer | (1 << OE))
    await wait_for_propagation(dut)
    
    uio_oe = int(dut.uio_oe.value)
    dut._log.info(f"After OE=1: expected uio_oe=0xFF, got 0x{uio_oe:02X}")
    assert uio_oe == 0xFF, f"uio_oe expected FF got {uio_oe:02x}"
    
    # Test counter overflow (wraparound from 0xFF -> 0x00)
    dut._log.info("Testing counter overflow...")
    # Load 0xFE to be close to overflow
    dut.uio_in.value = 0xFE
    dut.ui_in.value = ui | (1 << LOAD)  # LOAD=1, OE=1
    await RisingEdge(dut.clk)
    dut.ui_in.value = ui                # LOAD=0, keep EN=0 for now
    await wait_for_propagation(dut)
    
    actual_val = int(dut.uo_out.value)
    dut._log.info(f"  Loaded 0xFE, got 0x{actual_val:02X}")
    assert actual_val == 0xFE, f"after load 0xFE got {actual_val:02x}"
    
    # Now enable counting
    dut.ui_in.value = ui | (1 << EN)    # EN=1, OE=1
    
    # Count: 0xFE -> 0xFF
    await RisingEdge(dut.clk)
    await wait_for_propagation(dut)  # Just wait for propagation, no extra clock
    actual_val = int(dut.uo_out.value)
    dut._log.info(f"  After 1 count: 0x{actual_val:02X} (should be 0xFF)")
    assert actual_val == 0xFF, f"expected 0xFF got {actual_val:02x}"
    
    # Count: 0xFF -> 0x00 (OVERFLOW!)
    await RisingEdge(dut.clk)
    await wait_for_propagation(dut)  # Just wait for propagation, no extra clock
    actual_val = int(dut.uo_out.value)
    dut._log.info(f"  After overflow: 0x{actual_val:02X} (should be 0x00)")
    assert actual_val == 0x00, f"after overflow expected 0x00 got {actual_val:02x}"
    
    # Count a few more to confirm it continues: 0x00 -> 0x01 -> 0x02 -> 0x03
    for i in range(1, 4):
        await RisingEdge(dut.clk)
        await wait_for_propagation(dut)  # Just wait for propagation, no extra clock
        actual_val = int(dut.uo_out.value)
        dut._log.info(f"  Count continues: 0x{actual_val:02X}")
        assert actual_val == i, f"expected {i:02x} got {actual_val:02x}"
    
    dut._log.info(f"✓ All tests passed in {'GATE-LEVEL' if is_gl else 'RTL'} mode")
