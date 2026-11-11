// КлимаКлас – сензорен възел
// Чете CO2, температура и влажност веднъж в минута, показва ги на OLED дисплея
// и ги изпраща към облачния сървър (HTTPS) или към Raspberry Pi шлюза (MQTT).

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <time.h>

#include "config.h"
#include "root_ca.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Липсва include/secrets.h – копирайте secrets.example.h като secrets.h и го попълнете."
#endif

#ifdef SENSOR_SCD41
#include <SensirionI2cScd4x.h>
SensirionI2cScd4x sensor;
#else
#include <SensirionI2cStcc4.h>
SensirionI2cStcc4 sensor;
#endif

// Ако дисплеят е на същите пинове като сензора (класически ESP32), ползваме една шина.
#if (OLED_SDA == SENSOR_SDA) && (OLED_SCL == SENSOR_SCL)
#define OLED_WIRE Wire
#else
#define OLED_WIRE Wire1
#endif

Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &OLED_WIRE, -1);
bool displayOk = false;

struct Measurement {
  uint16_t co2;
  float temperature;
  float humidity;
  time_t timestamp;  // UNIX време (UTC); 0 = неизвестно
};

// Кръгов буфер за измервания, които още не са изпратени
Measurement buffer[BUFFER_SIZE];
size_t bufHead = 0, bufCount = 0;

WiFiClientSecure tlsClient;
WiFiClient plainClient;
PubSubClient mqtt(plainClient);

unsigned long lastMeasure = 0;
Measurement last = {0, NAN, NAN, 0};
String lastError = "";

// ---------------------------------------------------------------- сензор

bool sensorBegin() {
  Wire.begin(SENSOR_SDA, SENSOR_SCL);
#ifdef SENSOR_SCD41
  sensor.begin(Wire, SCD41_I2C_ADDR_62);
  sensor.wakeUp();
  sensor.stopPeriodicMeasurement();
  sensor.reinit();
  int16_t err = sensor.startPeriodicMeasurement();
#else
  sensor.begin(Wire, STCC4_I2C_ADDR_64);
  sensor.stopContinuousMeasurement();
  delay(1200);
  int16_t err = sensor.startContinuousMeasurement();
#endif
  if (err) {
    Serial.printf("Грешка при старт на сензора: %d\n", err);
    return false;
  }
  return true;
}

bool sensorRead(Measurement &m) {
#ifdef SENSOR_SCD41
  bool ready = false;
  if (sensor.getDataReadyStatus(ready) || !ready) return false;
  uint16_t co2;
  float t, h;
  if (sensor.readMeasurement(co2, t, h)) return false;
  m.co2 = co2;
#else
  int16_t co2;
  float t, h;
  uint16_t status;
  if (sensor.readMeasurement(co2, t, h, status)) return false;
  if (co2 <= 0) return false;  // първите секунди след старт сензорът още загрява
  m.co2 = (uint16_t)co2;
#endif
  m.temperature = t;
  m.humidity = h;
  m.timestamp = time(nullptr) > 1700000000 ? time(nullptr) : 0;
  return true;
}

// ---------------------------------------------------------------- дисплей

void showOnDisplay() {
  if (!displayOk) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);
  display.setCursor(0, 0);
  if (last.co2) display.printf("%u", last.co2);
  else display.print("----");
  display.setTextSize(1);
  display.print(" ppm");

  display.setCursor(0, 18);
  const char *label = last.co2 == 0 ? "zagryavane..." : last.co2 < CO2_WARN ? "OK" : last.co2 <= CO2_ALERT ? "PROVETRETE SKORO" : "OTVORETE PROZOREC!";
  display.print(label);  // OLED шрифтът няма кирилица, затова пишем на латиница

  display.setCursor(0, 26);
  if (!isnan(last.temperature)) display.printf("%.1fC %.0f%% ", last.temperature, last.humidity);
  display.print(WiFi.status() == WL_CONNECTED ? "WiFi" : "no WiFi");
  if (bufCount) display.printf(" +%u", (unsigned)bufCount);

  // При висок CO2 дисплеят мига, за да се забележи
  if (last.co2 > CO2_ALERT && (millis() / 1000) % 2) display.invertDisplay(true);
  else display.invertDisplay(false);
  display.display();
}

// ---------------------------------------------------------------- мрежа

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("Свързване към %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Wi-Fi OK, IP %s\n", WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "time.google.com");  // нужно за TLS и за времето на измерванията
  }
}

void bufferPush(const Measurement &m) {
  buffer[(bufHead + bufCount) % BUFFER_SIZE] = m;
  if (bufCount < BUFFER_SIZE) bufCount++;
  else bufHead = (bufHead + 1) % BUFFER_SIZE;  // пълен – губим най-старото
}

void appendReading(JsonObject o, const Measurement &m) {
  o["co2"] = m.co2;
  if (!isnan(m.temperature)) o["temperature"] = roundf(m.temperature * 10) / 10;
  if (!isnan(m.humidity)) o["humidity"] = roundf(m.humidity * 10) / 10;
  if (m.timestamp) {
    char iso[25];
    strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%SZ", gmtime(&m.timestamp));
    o["measured_at"] = iso;
  }
}

#if !USE_MQTT_GATEWAY
// Праща всички буферирани измервания с една заявка към /api/v1/readings/batch
bool flushHttps() {
  if (!bufCount || WiFi.status() != WL_CONNECTED) return false;
  JsonDocument doc;
  JsonArray arr = doc["readings"].to<JsonArray>();
  size_t n = min(bufCount, (size_t)100);
  for (size_t i = 0; i < n; i++) appendReading(arr.add<JsonObject>(), buffer[(bufHead + i) % BUFFER_SIZE]);
  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.setTimeout(10000);
  if (!http.begin(tlsClient, String(API_BASE_URL) + "/api/v1/readings/batch")) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
  int code = http.POST(body);
  String resp = http.getString();
  http.end();
  Serial.printf("POST %u измервания → %d %s\n", (unsigned)n, code, resp.c_str());

  if (code == 201) {
    bufHead = (bufHead + n) % BUFFER_SIZE;
    bufCount -= n;
    lastError = "";
    return true;
  }
  if (code == 422) {  // невалидни данни – няма смисъл да ги пращаме пак
    bufHead = (bufHead + n) % BUFFER_SIZE;
    bufCount -= n;
  }
  lastError = "HTTP " + String(code);
  return false;
}
#else
bool flushMqtt() {
  if (!bufCount || WiFi.status() != WL_CONNECTED) return false;
  if (!mqtt.connected() && !mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD)) {
    lastError = "MQTT " + String(mqtt.state());
    return false;
  }
  String topic = String("klimaklas/") + DEVICE_ID + "/reading";
  while (bufCount) {
    JsonDocument doc;
    appendReading(doc.to<JsonObject>(), buffer[bufHead]);
    doc["token"] = DEVICE_TOKEN;  // шлюзът го използва, за да препрати към API от наше име
    char payload[256];
    size_t len = serializeJson(doc, payload);
    if (!mqtt.publish(topic.c_str(), (const uint8_t *)payload, len, false)) return false;
    bufHead = (bufHead + 1) % BUFFER_SIZE;
    bufCount--;
  }
  return true;
}
#endif

// ---------------------------------------------------------------- setup/loop

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nКлимаКлас сензорен възел");

  OLED_WIRE.begin(OLED_SDA, OLED_SCL);
  displayOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  if (!displayOk) Serial.println("OLED дисплеят не е открит (продължаваме без него).");
  showOnDisplay();

  if (!sensorBegin()) Serial.println("Сензорът не отговаря – проверете кабелите (SDA/SCL/3V3/GND).");

  tlsClient.setCACert(ROOT_CA_PEM);
#if USE_MQTT_GATEWAY
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
#endif
  ensureWifi();
  lastMeasure = millis() - MEASURE_INTERVAL_MS + 10000;  // първо измерване след ~10 s
}

void loop() {
  if (millis() - lastMeasure >= MEASURE_INTERVAL_MS) {
    lastMeasure = millis();
    Measurement m;
    if (sensorRead(m)) {
      last = m;
      bufferPush(m);
      Serial.printf("CO2 %u ppm, %.1f C, %.1f %%\n", m.co2, m.temperature, m.humidity);
    } else {
      Serial.println("Няма ново измерване от сензора.");
    }
    ensureWifi();
#if USE_MQTT_GATEWAY
    flushMqtt();
#else
    flushHttps();
#endif
    if (lastError.length()) Serial.printf("Грешка при изпращане: %s (в буфера: %u)\n", lastError.c_str(), (unsigned)bufCount);
  }
#if USE_MQTT_GATEWAY
  mqtt.loop();
#endif
  showOnDisplay();
  delay(250);
}
