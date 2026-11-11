# Публикуване в Oracle Cloud (безплатно)

Стъпките в **A–D** се правят на ръка в браузъра. Те изискват ваш акаунт и карта, затова не мога да ги направя вместо вас. Всичко след това се прави от скрипта [`deploy/oracle/setup.sh`](../deploy/oracle/setup.sh).

## A. Акаунт в Oracle Cloud (~10 мин)

1. Отворете https://signup.cloud.oracle.com и регистрирайте акаунт.
2. **Home Region:** изберете **Germany Central (Frankfurt)**. По-късно не може да се смени.
3. Картата се иска само за проверка. Не включвайте „Upgrade to Pay As You Go“, иначе може да започнат такси.

## B. Виртуална машина (~5 мин)

**Compute → Instances → Create instance**

| Поле | Стойност |
|------|----------|
| Name | `klimaklas` |
| Image | **Canonical Ubuntu 24.04** (Change image → Ubuntu) |
| Shape | **Ampere → VM.Standard.A1.Flex**, 2 OCPU, 12 GB RAM |
| Networking | остави по подразбиране, **Assign a public IPv4 address = Yes** |
| Add SSH keys | **Paste public keys** → поставете ключа отдолу |

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFNwQwRrMDy15PlAH8UnkeZQaQFWKQbVv/9xgZPIWESH klimaklas-oracle
```

> Ако излезе **„Out of capacity“** за Ampere, опитайте друг *Availability Domain* или изберете shape **VM.Standard.E2.1.Micro** (AMD, също безплатен). Скриптът добавя swap, така че и малката машина ще се справи.

След създаването запишете **Public IP address** от страницата на машината.

## C. Отваряне на портове 80 и 443 (~2 мин)

На страницата на машината: **Subnet → Security Lists → Default Security List → Add Ingress Rules**

| Source CIDR | IP Protocol | Destination Port Range |
|-------------|-------------|------------------------|
| `0.0.0.0/0` | TCP | `80,443` |

## D. Безплатен домейн от DuckDNS (~2 мин)

1. Отворете https://www.duckdns.org и влезте с GitHub или Google.
2. Добавете поддомейн, например `klimaklas` (ако е зает: `klimaklas-noit` и т.н.).
3. В полето **current ip** поставете публичния IP от стъпка B и натиснете **update ip**.

## E. Изпратете ми

- публичния IP адрес;
- домейна (напр. `klimaklas.duckdns.org`).

Оттук нататък продължавам аз: влизам по SSH и пускам

```bash
bash setup.sh klimaklas.duckdns.org
```

Скриптът инсталира Docker, отваря защитната стена на самия сървър, изтегля кода от GitHub и генерира случайни пароли. След това стартира PostgreSQL, сървъра и Caddy (той взима HTTPS сертификат автоматично) и зарежда демо училището с тестовите акаунти.

## Обновяване след промени в кода

```bash
ssh -i ~/.ssh/klimaklas_oracle ubuntu@<IP> "bash /opt/klimaklas/deploy/oracle/setup.sh <домейн>"
```
