# Push после отклонения (remote has work you don't have)

Если при `git push` видите:
```
! [rejected]        main -> main (fetch first)
Updates were rejected because the remote contains work that you do not have locally.
```

## Что сделать

```bash
cd /projects/Brotherly_hearts_analyst/Kobyzev_Yuri

# Подтянуть изменения с GitHub и слить с вашим коммитом
git pull --no-edit origin main

# Если pull прошёл без конфликтов — отправить снова
git push origin main
```

Если при `git pull` появятся конфликты — Git покажет файлы; их нужно разрешить, затем:

```bash
git add .
git commit -m "Merge remote main"
git push origin main
```

## Если используете прокси

При ошибке `Failed to connect to 127.0.0.1 port 1080` временно отключите прокси для git:

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
git pull --no-edit origin main
git push origin main
```
