#pragma once
// Копирайте този файл като secrets.h и попълнете стойностите.
// secrets.h е в .gitignore – НЕ го качвайте в GitHub.

#define WIFI_SSID "ime-na-mrezhata"
#define WIFI_PASSWORD "parola-na-mrezhata"

// Адрес на API (без наклонена черта в края)
#define API_BASE_URL "https://klimaklas.onrender.com"  // адресът от Render (без / накрая)

// Токен на устройството – получава се от „Администрация → Устройства“ в уеб панела.
#define DEVICE_TOKEN "kk_..."

// Само при USE_MQTT_GATEWAY=1 (Raspberry Pi шлюз)
#define MQTT_HOST "192.168.1.50"
#define MQTT_PORT 1883
#define MQTT_USER "klimaklas"
#define MQTT_PASSWORD "mqtt-parola"
#define DEVICE_ID "room-214"
