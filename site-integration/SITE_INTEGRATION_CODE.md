# Код для интеграции на сайт заказчика

## 📋 Описание

Этот документ содержит JavaScript код, который нужно вставить на сайт заказчика для инициации нейропродажника при вводе телефона и email.

## 🎯 Что делает код

1. **Отслеживает ввод телефона и email** в формах на сайте
2. **Отправляет событие в n8n webhook** для инициации агента продаж
3. **Отправляет событие в Яндекс.Метрику** (опционально)
4. **Генерирует уникальные ID** для отслеживания посетителя

---

## 📝 Код для вставки на сайт

### Вариант 1: Полный код (рекомендуется)

Вставьте этот код в `<head>` или перед закрывающим тегом `</body>` на всех страницах сайта:

```html
<script>
(function() {
    'use strict';
    
    // ============================================
    // КОНФИГУРАЦИЯ - ЗАМЕНИТЕ НА ВАШИ ЗНАЧЕНИЯ
    // ============================================
    const CONFIG = {
        // URL вашего n8n webhook (замените на реальный URL)
        n8nWebhookUrl: 'https://your-n8n-domain.com/webhook/sales-agent-kb',
        
        // ID счетчика Яндекс.Метрики (если используется)
        yandexMetrikaId: 103165578,
        
        // Канал для идентификации источника
        channel: 'site',
        
        // Включить отправку в Яндекс.Метрику
        enableYandexMetrika: true
    };
    
    // ============================================
    // УТИЛИТЫ
    // ============================================
    
    /**
     * Генерирует уникальный ID посетителя
     */
    function getVisitorId() {
        let visitorId = localStorage.getItem('brats_visitor_id');
        if (!visitorId) {
            visitorId = 'visitor_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('brats_visitor_id', visitorId);
        }
        return visitorId;
    }
    
    /**
     * Генерирует ID сессии
     */
    function getSessionId() {
        let sessionId = sessionStorage.getItem('brats_session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('brats_session_id', sessionId);
        }
        return sessionId;
    }
    
    /**
     * Нормализует телефон (удаляет все кроме цифр)
     */
    function normalizePhone(phone) {
        return phone.replace(/\D/g, '');
    }
    
    /**
     * Валидирует email
     */
    function isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    
    /**
     * Валидирует телефон (минимум 10 цифр)
     */
    function isValidPhone(phone) {
        const normalized = normalizePhone(phone);
        return normalized.length >= 10;
    }
    
    /**
     * Отправляет событие в n8n webhook
     */
    async function sendToN8N(eventData) {
        try {
            const response = await fetch(CONFIG.n8nWebhookUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: eventData.message || 'Пользователь начал заполнять форму',
                    channel: CONFIG.channel,
                    external_id: getVisitorId(),
                    metadata: {
                        visitor_id: getVisitorId(),
                        session_id: getSessionId(),
                        event_type: eventData.eventType,
                        form_type: eventData.formType || 'unknown',
                        phone: eventData.phone ? normalizePhone(eventData.phone) : null,
                        email: eventData.email || null,
                        page_url: window.location.href,
                        page_title: document.title,
                        user_agent: navigator.userAgent,
                        timestamp: new Date().toISOString(),
                        ...eventData.metadata
                    }
                })
            });
            
            if (!response.ok) {
                console.warn('N8N webhook error:', response.status, response.statusText);
            }
            
            return response;
        } catch (error) {
            console.error('Error sending to N8N:', error);
            // Не прерываем выполнение, просто логируем ошибку
        }
    }
    
    /**
     * Отправляет событие в Яндекс.Метрику
     */
    function sendToYandexMetrika(eventName, params) {
        if (!CONFIG.enableYandexMetrika || !CONFIG.yandexMetrikaId) {
            return;
        }
        
        try {
            if (typeof ym !== 'undefined') {
                ym(CONFIG.yandexMetrikaId, 'reachGoal', eventName, params || {});
            }
        } catch (error) {
            console.error('Yandex Metrika error:', error);
        }
    }
    
    /**
     * Обрабатывает ввод телефона
     */
    function handlePhoneInput(input) {
        const phone = input.value;
        
        // Проверяем, что телефон валидный и достаточно длинный
        if (isValidPhone(phone) && phone.length >= 10) {
            // Отправляем событие в n8n
            sendToN8N({
                eventType: 'phone_input',
                phone: phone,
                message: 'Пользователь ввел телефон в форму',
                formType: input.closest('form')?.getAttribute('data-form-type') || 'unknown',
                metadata: {
                    form_id: input.closest('form')?.id || null,
                    field_name: input.name || input.id || 'phone'
                }
            });
            
            // Отправляем событие в Яндекс.Метрику
            sendToYandexMetrika('phone_input', {
                form_type: input.closest('form')?.getAttribute('data-form-type') || 'unknown'
            });
        }
    }
    
    /**
     * Обрабатывает ввод email
     */
    function handleEmailInput(input) {
        const email = input.value;
        
        // Проверяем, что email валидный
        if (isValidEmail(email)) {
            // Отправляем событие в n8n
            sendToN8N({
                eventType: 'email_input',
                email: email,
                message: 'Пользователь ввел email в форму',
                formType: input.closest('form')?.getAttribute('data-form-type') || 'unknown',
                metadata: {
                    form_id: input.closest('form')?.id || null,
                    field_name: input.name || input.id || 'email'
                }
            });
            
            // Отправляем событие в Яндекс.Метрику
            sendToYandexMetrika('email_input', {
                form_type: input.closest('form')?.getAttribute('data-form-type') || 'unknown'
            });
        }
    }
    
    /**
     * Обрабатывает отправку формы
     */
    function handleFormSubmit(form) {
        const formData = new FormData(form);
        const phone = formData.get('phone') || formData.get('tel') || formData.get('telephone') || '';
        const email = formData.get('email') || formData.get('mail') || '';
        
        // Отправляем событие в n8n
        sendToN8N({
            eventType: 'form_submit',
            phone: phone,
            email: email,
            message: 'Пользователь отправил форму',
            formType: form.getAttribute('data-form-type') || 'unknown',
            metadata: {
                form_id: form.id || null,
                form_action: form.action || null,
                form_method: form.method || 'POST'
            }
        });
        
        // Отправляем событие в Яндекс.Метрику
        sendToYandexMetrika('form_submit', {
            form_type: form.getAttribute('data-form-type') || 'unknown'
        });
    }
    
    /**
     * Инициализация отслеживания
     */
    function initTracking() {
        // Находим все поля телефона
        const phoneInputs = document.querySelectorAll('input[type="tel"], input[name*="phone"], input[name*="tel"], input[id*="phone"], input[id*="tel"]');
        phoneInputs.forEach(input => {
            // Отслеживаем ввод (с задержкой, чтобы не спамить)
            let timeout;
            input.addEventListener('input', function() {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    handlePhoneInput(input);
                }, 1000); // Отправляем через 1 секунду после последнего ввода
            });
        });
        
        // Находим все поля email
        const emailInputs = document.querySelectorAll('input[type="email"], input[name*="email"], input[name*="mail"], input[id*="email"], input[id*="mail"]');
        emailInputs.forEach(input => {
            // Отслеживаем ввод (с задержкой)
            let timeout;
            input.addEventListener('input', function() {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    handleEmailInput(input);
                }, 1000);
            });
        });
        
        // Отслеживаем отправку форм
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', function(e) {
                handleFormSubmit(form);
            });
        });
        
        // Отслеживаем клики по телефону
        const phoneLinks = document.querySelectorAll('a[href^="tel:"]');
        phoneLinks.forEach(link => {
            link.addEventListener('click', function() {
                sendToN8N({
                    eventType: 'phone_click',
                    message: 'Пользователь кликнул по телефону',
                    metadata: {
                        phone_number: link.getAttribute('href').replace('tel:', '')
                    }
                });
                
                sendToYandexMetrika('phone_click');
            });
        });
        
        // Отслеживаем клики по WhatsApp
        const whatsappLinks = document.querySelectorAll('a[href*="wa.me"], a[href*="whatsapp.com"]');
        whatsappLinks.forEach(link => {
            link.addEventListener('click', function() {
                sendToN8N({
                    eventType: 'whatsapp_click',
                    message: 'Пользователь кликнул по WhatsApp',
                    metadata: {}
                });
                
                sendToYandexMetrika('whatsapp_click');
            });
        });
    }
    
    // Инициализация при загрузке страницы
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTracking);
    } else {
        initTracking();
    }
    
    // Также инициализируем для динамически добавленных элементов
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length) {
                // Переинициализируем для новых элементов
                initTracking();
            }
        });
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
})();
</script>
```

---

### Вариант 2: Минимальный код (только телефон и email)

Если нужен только базовый функционал:

```html
<script>
(function() {
    const N8N_WEBHOOK_URL = 'https://your-n8n-domain.com/webhook/sales-agent-kb';
    
    function getVisitorId() {
        let id = localStorage.getItem('brats_visitor_id');
        if (!id) {
            id = 'visitor_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('brats_visitor_id', id);
        }
        return id;
    }
    
    function sendEvent(eventType, data) {
        fetch(N8N_WEBHOOK_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: 'Пользователь ввел ' + (data.phone ? 'телефон' : 'email'),
                channel: 'site',
                external_id: getVisitorId(),
                metadata: {
                    event_type: eventType,
                    ...data,
                    page_url: window.location.href,
                    timestamp: new Date().toISOString()
                }
            })
        }).catch(console.error);
    }
    
    // Отслеживание телефона
    document.querySelectorAll('input[type="tel"], input[name*="phone"]').forEach(input => {
        let timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                if (input.value.replace(/\D/g, '').length >= 10) {
                    sendEvent('phone_input', {phone: input.value});
                }
            }, 1000);
        });
    });
    
    // Отслеживание email
    document.querySelectorAll('input[type="email"]').forEach(input => {
        let timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value)) {
                    sendEvent('email_input', {email: input.value});
                }
            }, 1000);
        });
    });
})();
</script>
```

---

## 🔧 Настройка

### 1. Замените URL webhook

В коде найдите строку:
```javascript
n8nWebhookUrl: 'https://your-n8n-domain.com/webhook/sales-agent-kb',
```

Замените на реальный URL вашего n8n webhook:
```javascript
n8nWebhookUrl: 'https://n8n.yourdomain.com/webhook/sales-agent-kb',
```

### 2. Настройте ID Яндекс.Метрики (опционально)

Если используете Яндекс.Метрику, укажите ID счетчика:
```javascript
yandexMetrikaId: 103165578, // Ваш ID счетчика
```

### 3. Добавьте атрибуты к формам (рекомендуется)

Для лучшей идентификации форм добавьте атрибут `data-form-type`:

```html
<form data-form-type="reservation_black_box">
    <input type="tel" name="phone" placeholder="Телефон">
    <input type="email" name="email" placeholder="Email">
    <button type="submit">Отправить</button>
</form>
```

Возможные значения `data-form-type`:
- `reservation_black_box` - Резервирование BLACK BOX
- `reservation_white_box` - Резервирование WHITE BOX
- `reservation_standard` - Резервирование STANDARD
- `reservation_design` - Резервирование DESIGN
- `mortgage_calculator` - Калькулятор ипотеки
- `viewing_appointment` - Запись на просмотр
- `contact_form` - Контактная форма

---

## 📊 Что отправляется в n8n

При вводе телефона или email отправляется следующий JSON:

```json
{
  "message": "Пользователь ввел телефон в форму",
  "channel": "site",
  "external_id": "visitor_1234567890_abc123",
  "metadata": {
    "visitor_id": "visitor_1234567890_abc123",
    "session_id": "session_1234567890_xyz789",
    "event_type": "phone_input",
    "form_type": "reservation_black_box",
    "phone": "79981234567",
    "email": null,
    "page_url": "https://innovatory-club.ru/katalog",
    "page_title": "Каталог коттеджей",
    "user_agent": "Mozilla/5.0...",
    "timestamp": "2025-02-07T15:30:00.000Z",
    "form_id": "reservation-form-1",
    "field_name": "phone"
  }
}
```

---

## 🧪 Тестирование

### 1. Проверка в браузере

1. Откройте сайт с установленным кодом
2. Откройте консоль разработчика (F12)
3. Введите телефон или email в форму
4. Проверьте, что в консоли нет ошибок
5. Проверьте Network tab - должен быть POST запрос к n8n webhook

### 2. Проверка в n8n

1. Откройте n8n
2. Перейдите в **Executions**
3. Найдите последнее выполнение workflow
4. Проверьте, что данные пришли корректно

### 3. Тест через curl

```bash
curl -X POST https://your-n8n-domain.com/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Тест инициации агента",
    "channel": "site",
    "external_id": "test_visitor_123",
    "metadata": {
      "event_type": "phone_input",
      "phone": "79981234567",
      "form_type": "reservation_black_box"
    }
  }'
```

---

## 🔒 Безопасность

### Рекомендации:

1. **HTTPS обязателен** - используйте только HTTPS для webhook URL
2. **Валидация на сервере** - не полагайтесь только на клиентскую валидацию
3. **Rate limiting** - настройте ограничение частоты запросов в n8n
4. **Не отправляйте полные данные** - телефон и email можно хешировать перед отправкой

### Пример с хешированием (опционально):

```javascript
async function hashData(data) {
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(data);
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Использование:
const phoneHash = await hashData(normalizePhone(phone));
sendToN8N({
    phone_hash: phoneHash, // Вместо phone
    // ...
});
```

---

## 📱 Поддержка мобильных устройств

Код автоматически работает на мобильных устройствах. Для лучшей поддержки:

1. Убедитесь, что поля телефона имеют правильный `type="tel"`
2. Используйте `inputmode="tel"` для мобильных клавиатур:
   ```html
   <input type="tel" inputmode="tel" name="phone">
   ```

---

## 🐛 Устранение проблем

### Проблема: События не отправляются

**Решение:**
1. Проверьте консоль браузера на ошибки
2. Убедитесь, что URL webhook правильный
3. Проверьте CORS настройки в n8n
4. Проверьте, что workflow опубликован в n8n

### Проблема: Слишком много запросов

**Решение:**
1. Увеличьте задержку в `setTimeout` (сейчас 1000ms)
2. Добавьте проверку, что значение изменилось перед отправкой

### Проблема: Не работает на динамических формах

**Решение:**
Код автоматически отслеживает новые элементы через `MutationObserver`. Если не работает:
1. Убедитесь, что код выполняется после загрузки DOM
2. Проверьте, что `MutationObserver` поддерживается браузером

---

## 📚 Дополнительные события

Код также отслеживает:
- ✅ Клики по телефону (`a[href^="tel:"]`)
- ✅ Клики по WhatsApp (`a[href*="wa.me"]`)
- ✅ Отправку форм

---

## 🔗 Связанные документы

- [`ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md`](./ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md) - активация агента через аналитику
- [`WEBHOOK_SETUP_CLARIFICATION.md`](./WEBHOOK_SETUP_CLARIFICATION.md) - настройка webhook
- [`SITE_ANALYTICS_INTEGRATION_ANALYSIS.md`](./SITE_ANALYTICS_INTEGRATION_ANALYSIS.md) - анализ интеграции с аналитикой

---

**Последнее обновление:** 2025-02-07

