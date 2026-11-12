ARG VARIANT=ubuntu-24.04
FROM mcr.microsoft.com/vscode/devcontainers/base:${VARIANT}

ENV DEBIAN_FRONTEND=noninteractive
ENV PDK_ROOT=/home/vscode/ttsetup/pdk
ENV PDK=ihp-sg13cmos5l
ARG TT_SUPPORT_TOOLS_BRANCH=main

RUN apt update
RUN apt install -y iverilog gtkwave python3 python3-pip python3-venv python3-tk python-is-python3 libcairo2 libpng-dev libqhull-dev

# Build Verilator from source: Ubuntu 24.04's apt package (5.020) is too old for cocotb 2.x (needs >= 5.036)
ARG VERILATOR_VERSION=v5.052
RUN apt install -y git help2man perl make autoconf g++ flex bison ccache libfl2 libfl-dev zlib1g-dev && \
    git clone --depth 1 -b ${VERILATOR_VERSION} https://github.com/verilator/verilator /tmp/verilator && \
    cd /tmp/verilator && autoconf && ./configure && make -j"$(nproc)" && make install && \
    rm -rf /tmp/verilator

# Clone tt-support-tools
RUN mkdir -p /ttsetup
RUN git clone -b ${TT_SUPPORT_TOOLS_BRANCH} https://github.com/TinyTapeout/tt-support-tools /ttsetup/tt-support-tools

COPY test/requirements.txt /ttsetup/test_requirements.txt
COPY .devcontainer/copy_tt_support_tools.sh /ttsetup

RUN python -m venv /ttsetup/venv
RUN /ttsetup/venv/bin/pip install -r /ttsetup/test_requirements.txt -r /ttsetup/tt-support-tools/requirements.txt

# Install verible (for formatting)
RUN umask 022 && \
    curl -L https://github.com/chipsalliance/verible/releases/download/v0.0-4023-gc1271a00/verible-v0.0-4023-gc1271a00-linux-static-x86_64.tar.gz | \
    tar zxf - -C /usr/local --strip-components=1 && \
    chmod 755 /usr/local/bin

# Install LibreLane (3.1.0.dev4 or newer is required for ihp-sg13cmos5l)
RUN /ttsetup/venv/bin/pip install librelane==3.1.0.dev4
