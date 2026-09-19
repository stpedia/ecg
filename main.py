"""
Main script for NodeMCU ESP8266 reading ADS1293 ECG module and streaming
Lead I, Lead II, and Lead III signal data over USB Serial Port for Serial Plotter.
"""

import time
from machine import Pin, SPI
from ads1293 import ADS1293

# Pin mapping for NodeMCU ESP8266 (Hardware SPI HSPI)
# CS   -> D8 / GPIO15 (Note: Ensure pull-down resistor on D8 doesn't block CS if boot fails)
# SCLK -> D5 / GPIO14
# MISO -> D6 / GPIO12
# MOSI -> D7 / GPIO13
# DRDY -> D1 / GPIO5

CS_PIN_NUM = 15
DRDY_PIN_NUM = 5


def main():
    print("Initializing ADS1293 ECG Sensor...")

    # Hardware SPI setup for ESP8266 (HSPI = ID 1)
    spi = SPI(1, baudrate=1000000, polarity=0, phase=0)
    cs = Pin(CS_PIN_NUM, Pin.OUT, value=1)
    drdy = Pin(DRDY_PIN_NUM, Pin.IN)

    sensor = ADS1293(spi, cs_pin=cs, drdy_pin=drdy)

    # Allow sensor power stabilization
    time.sleep(0.2)

    # Verify SPI Connection by checking Revision/Config register
    cfg = sensor.read_reg(0x00)
    print("ADS1293 initial CONFIG reg (0x00): 0x{:02X}".format(cfg))

    if cfg == 0x00 or cfg == 0xFF:
        print("WARNING: SPI communication issue detected! Check CS, SCLK, MISO, MOSI connections & 3.3V power.")

    # Configure ADS1293 for standard 3-Lead ECG at 200 Hz
    sensor.config_3lead_ecg(sample_rate_hz=200)
    print("ADS1293 configured for 3-Lead ECG mode (Lead I, Lead II, Lead III).")
    print("Starting data streaming for Serial Plotter...")
    print("Format: Lead1:val,Lead2:val,Lead3:val")

    # Optional Exponential Moving Average (EMA) smoothing for plot stability
    alpha = 0.25
    filt_l1 = 0.0
    filt_l2 = 0.0
    filt_l3 = 0.0

    while True:
        # Check if data ready signal is asserted or poll status
        if sensor.is_data_ready():
            l1, l2, l3 = sensor.read_lead_voltage()

            # Apply lightweight Low-Pass Filter (EMA)
            filt_l1 = alpha * l1 + (1 - alpha) * filt_l1
            filt_l2 = alpha * l2 + (1 - alpha) * filt_l2
            filt_l3 = alpha * l3 + (1 - alpha) * filt_l3

            # Print formatted data for Serial Plotter (Arduino Serial Plotter / SerialPlot / Thonny)
            print("Lead1:{:.3f},Lead2:{:.3f},Lead3:{:.3f}".format(filt_l1, filt_l2, filt_l3))

        time.sleep_ms(5)


if __name__ == "__main__":
    main()
