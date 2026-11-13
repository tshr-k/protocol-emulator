# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = tt_um_tshr_k_protocol_emulator.sv protocol_emulator.sv

# The design's top-level module is simulated directly (no tb.v wrapper)
COCOTB_TOPLEVEL = tt_um_tshr_k_protocol_emulator

# `make clean` still loads the simulator's makefile, and cocotb's Verilator makefile
# aborts if verilator isn't on PATH. The TT gate-level CI job runs a plain
# `make clean` (no GATES=yes) with only Icarus installed, so use Icarus for clean.
ifeq ($(MAKECMDGOALS),clean)
SIM ?= icarus
endif

ifneq ($(GATES),yes)

# RTL simulation (Verilator for proper SystemVerilog support):
SIM ?= verilator
SIM_BUILD = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

# Waveforms: run with `make WAVES=1` to get dump.fst (view with gtkwave or surfer)
ifeq ($(WAVES),1)
SIM_BUILD = sim_build/rtl_waves
COMPILE_ARGS += --trace-fst --trace-structs
SIM_ARGS += --trace
endif

else

# Gate level simulation (Icarus, since the PDK cell models use UDPs/timing
# constructs that Verilator handles poorly):
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
SIM_BUILD = sim_build/gl
COMPILE_ARGS += -DGL_TEST
COMPILE_ARGS += -DFUNCTIONAL
COMPILE_ARGS += -DSIM
# Cell models for the PDK in $(PDK) (ihp-sg13cmos5l or ihp-sg13g2), e.g. sg13cmos5l_stdcell.v
PDK ?= ihp-sg13cmos5l
PDK_CELL_PREFIX = $(patsubst ihp-%,%,$(PDK))
PDK_LIBS_REF = $(PDK_ROOT)/$(PDK)/libs.ref
VERILOG_SOURCES += $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_io/verilog/$(PDK_CELL_PREFIX)_io.v
# Newer PDK versions ship the UDP (user-defined primitive) models in a separate file
VERILOG_SOURCES += $(wildcard $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_stdcell/verilog/$(PDK_CELL_PREFIX)_udp.v)
VERILOG_SOURCES += $(PDK_LIBS_REF)/$(PDK_CELL_PREFIX)_stdcell/verilog/$(PDK_CELL_PREFIX)_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS += -I$(SRC_DIR)

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
