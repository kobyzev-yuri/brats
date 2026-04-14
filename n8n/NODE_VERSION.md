# Версия Node.js для n8n

n8n требует **Node.js >=20.19 и <=24.x**. Версия 18.x не поддерживается.

## Обновление до Node.js 20 (Ubuntu/Debian)

Выполните в терминале:

```bash
# Добавить репозиторий NodeSource для Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Установить Node.js (npm и npx войдут в комплекте)
sudo apt-get install -y nodejs

# Проверить
node -v   # должно быть v20.x.x
npm -v
npx -v
```

После этого перезапустите локальный n8n:

```bash
cd /projects/brats
./start_all_services.sh stop
./start_all_services.sh start
```

Или только n8n: `cd n8n && ./start_n8n_local.sh`
