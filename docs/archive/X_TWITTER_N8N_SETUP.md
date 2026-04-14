# Настройка X (Twitter) OAuth в n8n

## Где получить Consumer Key и Consumer Secret

### Шаг 1: Создать приложение в X Developer Portal

1. Перейдите на [developer.twitter.com](https://developer.twitter.com/)
2. Войдите в свой аккаунт X (Twitter)
3. Перейдите в **Developer Portal** → **Projects & Apps** → **Your App** (или создайте новое приложение)
4. Откройте вкладку **Keys and tokens**

### Шаг 2: Получить ключи

В разделе **Consumer Keys** вы увидите:
- **API Key** (это Consumer Key)
- **API Key Secret** (это Consumer Secret)

**Важно:** 
- Если ключи не видны, нажмите **Regenerate** или **Create** для создания новых
- Сохраните их сразу — Secret показывается только один раз!

---

## Заполнение формы в n8n

### Поля формы:

| Поле | Что указать |
|------|-------------|
| **OAuth Redirect URL** | Оставьте как есть: `http://localhost:5678/rest/oauth1-credential/callback` |
| **Consumer Key** | Вставьте **API Key** из X Developer Portal |
| **Consumer Secret** | Вставьте **API Key Secret** из X Developer Portal |
| **Allowed HTTP Request Domains** | Оставьте **All** (или укажите конкретные домены, если нужно) |

### Пример заполнения:

```
OAuth Redirect URL: http://localhost:5678/rest/oauth1-credential/callback
Consumer Key: your_api_key_here
Consumer Secret: your_api_key_secret_here
Allowed HTTP Request Domains: All
```

---

## После заполнения

1. Нажмите **Save** в форме n8n
2. n8n попросит авторизоваться в X — нажмите **Connect my account** или аналогичную кнопку
3. Войдите в X и разрешите доступ приложению
4. После успешной авторизации credentials будут сохранены и готовы к использованию

---

## Использование в workflow

После настройки credentials можно использовать X ноды в n8n:
- **X (Twitter)** ноды для чтения твитов, публикации, работы с лентами и т.д.
- Или **HTTP Request** ноды с использованием credentials для прямых вызовов X API

---

## Важные замечания

1. **OAuth1 vs OAuth2:** X API использует OAuth 1.0a (поэтому URL содержит `oauth1-credential`)
2. **Для локальной разработки:** используйте `http://localhost:5678`
3. **Для продакшена:** измените Redirect URL на ваш реальный домен n8n
4. **Безопасность:** Consumer Secret — это секретная информация, не публикуйте её в репозитории

---

## Если нет доступа к X Developer Portal

Для получения доступа к X Developer Portal нужно:
1. Иметь аккаунт X (Twitter)
2. Подать заявку на доступ к API (может потребоваться верификация)
3. Выбрать тип доступа (Free, Basic, Pro, Enterprise)

Подробнее: [developer.twitter.com/en/portal](https://developer.twitter.com/en/portal)
