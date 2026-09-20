/*
 * ADS1293 3-Lead ECG Reader for NodeMCU ESP8266 (Arduino C++)
 *
 * Hardware Connections (NodeMCU ESP8266):
 * CS   -> D8 (GPIO15)
 * SCK  -> D5 (GPIO14)
 * MISO -> D6 (GPIO12)
 * MOSI -> D7 (GPIO13)
 * DRDY -> D1 (GPIO5)
 * VCC  -> 3V3
 * GND  -> GND
 */

#include <SPI.h>

#define CS_PIN   15 // D8 / GPIO15
#define DRDY_PIN 5  // D1 / GPIO5

// ADS1293 Registers
#define REG_CONFIG       0x00
#define REG_FLEX_CH1_CN  0x01
#define REG_FLEX_CH2_CN  0x02
#define REG_FLEX_CH3_CN  0x03
#define REG_RLD_CN       0x0A
#define REG_AFE_RES      0x12
#define REG_AFE_SHDN_CN  0x13
#define REG_R2_RATE      0x17
#define REG_R3_RATE_CH1  0x18
#define REG_R3_RATE_CH2  0x19
#define REG_R3_RATE_CH3  0x1A
#define REG_DRDYB_SRC    0x21
#define REG_CH_CNFG      0x27
#define REG_DATA_STATUS  0x30
#define REG_DATA_CH1_ECG 0x31

// VREF = 2.4V, Gain = 3.5
const float VREF = 2.4;
const float GAIN = 3.5;
const float LSB_TO_MV = (VREF / (8388607.0 * GAIN)) * 1000.0;

// Exponential Moving Average (EMA) smoothing filter
float filt_l1 = 0.0;
float filt_l2 = 0.0;
float filt_l3 = 0.0;
const float alpha = 0.25;

uint8_t readRegister(uint8_t reg) {
  digitalWrite(CS_PIN, LOW);
  SPI.transfer((reg & 0x7F) | 0x80); // Read command: bit 7 set
  uint8_t value = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  return value;
}

void writeRegister(uint8_t reg, uint8_t value) {
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(reg & 0x7F); // Write command: bit 7 cleared
  SPI.transfer(value);
  digitalWrite(CS_PIN, HIGH);
}

int32_t parse24BitSigned(uint8_t b1, uint8_t b2, uint8_t b3) {
  int32_t val = ((int32_t)b1 << 16) | ((int32_t)b2 << 8) | (int32_t)b3;
  if (val >= 0x800000) {
    val -= 0x1000000;
  }
  return val;
}

void config3LeadECG() {
  // Stop continuous conversion
  writeRegister(REG_CONFIG, 0x00);

  // Flex Routing: Lead I (IN1-IN2), Lead II (IN3-IN2), Lead III (IN3-IN1)
  writeRegister(REG_FLEX_CH1_CN, 0x0A);
  writeRegister(REG_FLEX_CH2_CN, 0x1A);
  writeRegister(REG_FLEX_CH3_CN, 0x19);

  // Enable RLD (Right Leg Drive) on IN4
  writeRegister(REG_RLD_CN, 0x04);

  // Set 24-bit high resolution on Ch1, Ch2, Ch3
  writeRegister(REG_AFE_RES, 0x07);

  // Power up analog front end
  writeRegister(REG_AFE_SHDN_CN, 0x00);

  // Decimation rates for ~200Hz output
  writeRegister(REG_R2_RATE, 0x04);
  writeRegister(REG_R3_RATE_CH1, 0x10);
  writeRegister(REG_R3_RATE_CH2, 0x10);
  writeRegister(REG_R3_RATE_CH3, 0x10);

  // Set DRDY interrupt source
  writeRegister(REG_DRDYB_SRC, 0x08);

  // Enable loop conversion
  writeRegister(REG_CH_CNFG, 0x70);

  // Start conversion
  writeRegister(REG_CONFIG, 0x01);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Initializing ADS1293 (Arduino C++)...");

  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  pinMode(DRDY_PIN, INPUT);

  SPI.begin();
  SPI.setBitOrder(MSBFIRST);
  SPI.setDataMode(SPI_MODE0);
  SPI.setClockDivider(SPI_CLOCK_DIV16); // ~1MHz clock

  delay(200);

  uint8_t cfg = readRegister(REG_CONFIG);
  Serial.print("ADS1293 initial CONFIG reg: 0x");
  Serial.println(cfg, HEX);

  config3LeadECG();
  Serial.println("ADS1293 Configured. Streaming 3-Lead ECG data for Serial Plotter...");
}

void loop() {
  if (digitalRead(DRDY_PIN) == LOW) {
    digitalWrite(CS_PIN, LOW);
    SPI.transfer((REG_DATA_CH1_ECG & 0x7F) | 0x80);

    uint8_t buf[9];
    for (int i = 0; i < 9; i++) {
      buf[i] = SPI.transfer(0x00);
    }
    digitalWrite(CS_PIN, HIGH);

    int32_t raw_l1 = parse24BitSigned(buf[0], buf[1], buf[2]);
    int32_t raw_l2 = parse24BitSigned(buf[3], buf[4], buf[5]);
    int32_t raw_l3 = parse24BitSigned(buf[6], buf[7], buf[8]);

    float l1 = raw_l1 * LSB_TO_MV;
    float l2 = raw_l2 * LSB_TO_MV;
    float l3 = raw_l3 * LSB_TO_MV;

    // Apply EMA Filter
    filt_l1 = alpha * l1 + (1.0 - alpha) * filt_l1;
    filt_l2 = alpha * l2 + (1.0 - alpha) * filt_l2;
    filt_l3 = alpha * l3 + (1.0 - alpha) * filt_l3;

    // Print for Serial Plotter
    Serial.print("Lead1:");
    Serial.print(filt_l1, 3);
    Serial.print(",Lead2:");
    Serial.print(filt_l2, 3);
    Serial.print(",Lead3:");
    Serial.println(filt_l3, 3);
  }

  delayMicroseconds(500);
}
