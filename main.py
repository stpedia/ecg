"""
Main script for NodeMCU ESP8266 reading ADS1293 ECG module and streaming
Lead I, Lead II, and Lead III signal data over USB Serial Port for Serial Plotter.
"""

import time
from machine import Pin, SPI
from ads1293 import ADS1293

# Pin mapping for NodeMCU ESP8266 (Hardware SPI HSPI)
# CS   -> D8 / GPIO15
# SCLK -> D5 / GPIO14
# MISO -> D6 / GPIO12
# MOSI -> D7 / GPIO13
# DRDY -> D1 / GPIO5 (Optional data ready interrupt pin)

CS_PIN_NUM = 15
DRDY_PIN_NUM = 5


def main():
    print("Initializing ADS1293 ECG Sensor...")

    # Hardware SPI setup for ESP8266
    spi = SPI(1, baudrate=4000000, polarity=0, phase=0)
    cs = Pin(CS_PIN_NUM, Pin.OUT, value=1)
    drdy = Pin(DRDY_PIN_NUM, Pin.IN)

    sensor = ADS1293(spi, cs_pin=cs, drdy_pin=drdy)

    # Allow sensor power stabilization
    time.sleep(0.1)

    # Test register read to verify communication (REG_CONFIG should be readable)
    try:
        cfg = sensor.read_reg(0x00)
        print("ADS1293 initial CONFIG register: 0x{:02X}".format(cfg))
    except Exception as e:
        print("Error reading from ADS1293 via SPI:", e)

    # Configure ADS1293 for standard 3-Lead ECG at 200 Hz
    sensor.config_3lead_ecg(sample_rate_hz=200)
    print("ADS1293 configured for 3-Lead ECG mode (Lead I, Lead II, Lead III).")
    print("Starting data streaming for Serial Plotter...")
    print("Format: Lead1:val,Lead2:val,Lead3:val")

    # Simple Exponential Moving Average (EMA) smoothing for noise filtering
    alpha = 0.2
    filt_l1 = 0.0
    filt_l2 = 0.0
    filt_l3 = 0.0

    while True:
        # Wait until data ready signal toggles LOW
        if sensor.is_data_ready():
            l1, l2, l3 = sensor.read_lead_voltage()

            # Apply lightweight Low-Pass Filter (EMA)
            filt_l1 = alpha * l1 + (1 - alpha) * filt_l1
            filt_l2 = alpha * l2 + (1 - alpha) * filt_l2
            filt_l3 = alpha * l3 + (1 - alpha) * filt_l3

            # Print formatted data for Serial Plotter (Arduino Serial Plotter / SerialPlot)
            print("Lead1:{:.3f},Lead2:{:.3f},Lead3:{:.3f}".format(filt_l1, filt_l2, filt_l3))

        # Yield execution briefly
        time.sleep_us(500)


if __name__ == "__main__":
    main()
