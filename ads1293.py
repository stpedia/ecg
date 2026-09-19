"""
ADS1293 MicroPython Driver
Hardware SPI driver for TI ADS1293 3-Channel, 24-Bit Analog Front-End for ECG.

Designed for NodeMCU ESP8266 & ESP32 running MicroPython.
"""

import time
from machine import Pin, SPI

# ADS1293 Register Map
REG_CONFIG       = 0x00  # Main Configuration Register
REG_FLEX_CH1_CN  = 0x01  # Flex Routing Sw. Control for Ch1
REG_FLEX_CH2_CN  = 0x02  # Flex Routing Sw. Control for Ch2
REG_FLEX_CH3_CN  = 0x03  # Flex Routing Sw. Control for Ch3
REG_RLD_CN       = 0x0A  # Right Leg Drive Control
REG_WILSON_CN    = 0x0C  # Wilson Central Terminal Control
REG_BATW_CN      = 0x0D  # Heart Rate Monitor Control
REG_AFE_RES      = 0x12  # AFE Resolution Register
REG_AFE_SHDN_CN  = 0x13  # AFE Shutdown Control Register
REG_R2_RATE      = 0x17  # Decimation Rate R2
REG_R3_RATE_CH1  = 0x18  # Decimation Rate R3 for Channel 1
REG_R3_RATE_CH2  = 0x19  # Decimation Rate R3 for Channel 2
REG_R3_RATE_CH3  = 0x1A  # Decimation Rate R3 for Channel 3
REG_DRDYB_SRC    = 0x21  # DRDYB Signal Source
REG_CH_CNFG      = 0x27  # Converter Channel Enable / Loop Read Control
REG_DATA_STATUS  = 0x30  # ECG Data Read Status
REG_DATA_CH1_ECG = 0x31  # Channel 1 ECG Data (3 bytes: 0x31, 0x32, 0x33)
REG_DATA_CH2_ECG = 0x34  # Channel 2 ECG Data (3 bytes: 0x34, 0x35, 0x36)
REG_DATA_CH3_ECG = 0x37  # Channel 3 ECG Data (3 bytes: 0x37, 0x38, 0x39)


class ADS1293:
    """MicroPython driver for TI ADS1293 ECG AFE."""

    def __init__(self, spi: SPI, cs_pin: Pin, drdy_pin: Pin = None, vref: float = 2.4):
        """
        Initialize ADS1293 device.

        :param spi: Initialized machine.SPI object (Mode 0, polarity 0, phase 0).
        :param cs_pin: machine.Pin object configured as OUT for Chip Select.
        :param drdy_pin: Optional machine.Pin object configured as IN for Data Ready signal.
        :param vref: Reference voltage in Volts (default internal VREF = 2.4V).
        """
        self.spi = spi
        self.cs = cs_pin
        self.drdy = drdy_pin
        self.vref = vref

        self.cs.init(Pin.OUT, value=1)
        if self.drdy:
            self.drdy.init(Pin.IN)

    def _select(self):
        self.cs.value(0)

    def _deselect(self):
        self.cs.value(1)

    def read_reg(self, reg: int) -> int:
        """Read a single byte from a register."""
        self._select()
        # Read command bit 7 is 1
        header = bytearray([(reg & 0x7F) | 0x80])
        self.spi.write(header)
        buf = self.spi.read(1)
        self._deselect()
        return buf[0]

    def write_reg(self, reg: int, value: int):
        """Write a single byte to a register."""
        self._select()
        # Write command bit 7 is 0
        header = bytearray([reg & 0x7F, value & 0xFF])
        self.spi.write(header)
        self._deselect()

    def read_bytes(self, reg: int, length: int) -> bytearray:
        """Read multiple bytes starting from register reg."""
        self._select()
        header = bytearray([(reg & 0x7F) | 0x80])
        self.spi.write(header)
        buf = self.spi.read(length)
        self._deselect()
        return buf

    def is_data_ready(self) -> bool:
        """Check if data is ready via DRDY pin or status register."""
        if self.drdy:
            return self.drdy.value() == 0
        else:
            status = self.read_reg(REG_DATA_STATUS)
            return (status & 0x01) != 0

    def config_3lead_ecg(self, sample_rate_hz: int = 200):
        """
        Configure ADS1293 for standard 3-Lead ECG mode:
          - Lead I   (LA - RA) -> Channel 1
          - Lead II  (LL - RA) -> Channel 2
          - Lead III (LL - LA) -> Channel 3

        :param sample_rate_hz: Desired output data rate (200, 400, or 800 Hz).
        """
        # Stop conversion during setup
        self.write_reg(REG_CONFIG, 0x00)

        # 1. Flex Routing Setup:
        # IN1 = LA, IN2 = RA, IN3 = LL
        # Ch1 = IN1(+) - IN2(-)  => LA - RA (Lead I)   = 0b001010 = 0x0A
        # Ch2 = IN3(+) - IN2(-)  => LL - RA (Lead II)  = 0b011010 = 0x1A
        # Ch3 = IN3(+) - IN1(-)  => LL - LA (Lead III) = 0b011001 = 0x19
        self.write_reg(REG_FLEX_CH1_CN, 0x0A)
        self.write_reg(REG_FLEX_CH2_CN, 0x1A)
        self.write_reg(REG_FLEX_CH3_CN, 0x19)

        # 2. Enable RLD (Right Leg Drive) on IN4 or internal feedback
        # RLD connected to IN4 (0x04) or automated feedback
        self.write_reg(REG_RLD_CN, 0x04)

        # 3. Set Resolution: 24-bit resolution on all 3 channels
        # AFE_RES register = 0x07 (high resolution on Ch1, Ch2, Ch3)
        self.write_reg(REG_AFE_RES, 0x07)

        # 4. Power up AFE channels (Ch1, Ch2, Ch3 enabled)
        # Bit 0, 1, 2 = 0 -> enable analog front end for Ch1, Ch2, Ch3
        self.write_reg(REG_AFE_SHDN_CN, 0x00)

        # 5. Set Decimation Rates (R2, R3) for desired sample rate
        # Clock = 4.096 MHz
        # If R2=4 (0x04), R3=16 (0x10) -> Output rate = 4096000 / (4 * 16 * 320) ~ 200 Hz
        if sample_rate_hz <= 200:
            self.write_reg(REG_R2_RATE, 0x04)      # R2 = 4
            self.write_reg(REG_R3_RATE_CH1, 0x10)  # R3 = 16
            self.write_reg(REG_R3_RATE_CH2, 0x10)
            self.write_reg(REG_R3_RATE_CH3, 0x10)
        elif sample_rate_hz <= 400:
            self.write_reg(REG_R2_RATE, 0x02)      # R2 = 2
            self.write_reg(REG_R3_RATE_CH1, 0x10)  # R3 = 16
            self.write_reg(REG_R3_RATE_CH2, 0x10)
            self.write_reg(REG_R3_RATE_CH3, 0x10)
        else:
            self.write_reg(REG_R2_RATE, 0x01)      # R2 = 1
            self.write_reg(REG_R3_RATE_CH1, 0x10)  # R3 = 16
            self.write_reg(REG_R3_RATE_CH2, 0x10)
            self.write_reg(REG_R3_RATE_CH3, 0x10)

        # 6. Configure DRDY interrupt source (Channel 1 ECG ready)
        self.write_reg(REG_DRDYB_SRC, 0x08)

        # 7. Enable Channel 1, 2, and 3 ECG conversion loop
        self.write_reg(REG_CH_CNFG, 0x70)

        # 8. Start continuous conversion mode
        self.write_reg(REG_CONFIG, 0x01)

    def _parse_24bit_signed(self, raw_bytes: bytearray, offset: int = 0) -> int:
        """Parse 3 bytes into a signed 24-bit integer."""
        val = (raw_bytes[offset] << 16) | (raw_bytes[offset + 1] << 8) | raw_bytes[offset + 2]
        if val >= 0x800000:
            val -= 0x1000000
        return val

    def read_lead_raw(self) -> tuple:
        """
        Read raw 24-bit values for (Lead I, Lead II, Lead III).
        :return: (raw_lead1, raw_lead2, raw_lead3)
        """
        # Read 9 consecutive bytes starting from REG_DATA_CH1_ECG (0x31)
        data = self.read_bytes(REG_DATA_CH1_ECG, 9)
        lead1 = self._parse_24bit_signed(data, 0)
        lead2 = self._parse_24bit_signed(data, 3)
        lead3 = self._parse_24bit_signed(data, 6)
        return lead1, lead2, lead3

    def read_lead_voltage(self, gain: float = 3.5) -> tuple:
        """
        Read ECG voltages in millivolts (mV) for (Lead I, Lead II, Lead III).

        :param gain: Instrumentation amplifier gain (default = 3.5 for ADS1293).
        :return: (mV_lead1, mV_lead2, mV_lead3)
        """
        r1, r2, r3 = self.read_lead_raw()
        # LSB = VREF / ( (2^23 - 1) * Gain )
        scale = (self.vref / (8388607.0 * gain)) * 1000.0  # Output in mV
        return r1 * scale, r2 * scale, r3 * scale
