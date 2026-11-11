#pragma once
// Общи настройки. Паролите и токенът са в secrets.h (не се качва в Git).

// ---------- Пинове (ESP32-S3 има две I²C шини – сензорът и дисплеят са на отделни, без бредборд) ----------
#ifndef SENSOR_SDA
#define SENSOR_SDA 4
#endif
#ifndef SENSOR_SCL
#define SENSOR_SCL 5
#endif
#ifndef OLED_SDA
#define OLED_SDA 6
#endif
#ifndef OLED_SCL
#define OLED_SCL 7
#endif

#define OLED_ADDRESS 0x3C
#define OLED_WIDTH 128
#define OLED_HEIGHT 32

// ---------- Измерване и изпращане ----------
#define MEASURE_INTERVAL_MS 60000UL  // веднъж в минута
#define CO2_WARN 800
#define CO2_ALERT 1200

// Ако няма връзка, пазим до толкова измервания в паметта и ги пращаме наведнъж после.
#define BUFFER_SIZE 240  // 4 часа

// ---------- Режим на изпращане ----------
// 0 = директно HTTPS към облачния сървър
// 1 = MQTT към Raspberry Pi шлюза (той буферира и препраща)
#ifndef USE_MQTT_GATEWAY
#define USE_MQTT_GATEWAY 0
#endif
