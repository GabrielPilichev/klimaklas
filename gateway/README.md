# Raspberry Pi шлюз

Шлюзът приема измерванията от сензорите в училищната мрежа по MQTT, пази ги в локална SQLite опашка и ги препраща към облачния API. Ако интернетът спре, данните чакат и се изпращат после. Нищо не се губи.

## Инсталация (Raspberry Pi OS)

```bash
sudo apt install -y mosquitto python3-venv
sudo cp mosquitto.conf /etc/mosquitto/conf.d/klimaklas.conf
sudo mosquitto_passwd -c /etc/mosquitto/passwd klimaklas
sudo systemctl restart mosquitto

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cat > .env <<EOF
KK_API_URL=https://klimaklas.example.bg
KK_MQTT_USER=klimaklas
KK_MQTT_PASSWORD=<паролата от mosquitto_passwd>
EOF

sudo cp klimaklas-gateway.service /etc/systemd/system/
sudo systemctl enable --now klimaklas-gateway
journalctl -u klimaklas-gateway -f
```

На всеки ESP32 задайте `USE_MQTT_GATEWAY 1` в `include/config.h` и `MQTT_HOST` (IP на Raspberry Pi) в `include/secrets.h`.

## Демо „изключваме интернета“

1. Издърпайте мрежовия кабел на Raspberry Pi (или спрете Wi-Fi рутера към интернет).
2. В лога се вижда, че опашката расте: `В опашката: 5`.
3. Включете кабела. Шлюзът изпраща всичко наведнъж и графиката в панела се попълва без дупка.
