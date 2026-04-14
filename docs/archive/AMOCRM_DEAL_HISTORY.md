# Получение истории заключенных сделок из amoCRM

## Описание

Workflow `amocrm-get-deal-history.json` позволяет получить историю всех заключенных сделок по контакту из amoCRM. Это полезно для:

- **Персонализации продаж** - использование истории покупок клиента при новой продаже
- **Контекст для нейропродажника** - передача информации о предыдущих взаимодействиях
- **Анализ клиента** - понимание паттернов покупок и предпочтений
- **Улучшение продаж** - использование успешных сделок как примеров

## Использование

### Базовый пример (по contact_id)

```bash
curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 46692527
  }'
```

### Поиск по телефону

```bash
curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+79991234567"
  }'
```

### Поиск по email

```bash
curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@example.com"
  }'
```

### С кастомными закрытыми статусами

```bash
curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 46692527,
    "closed_statuses": [142, 143, 80474570]
  }'
```

## Формат ответа

```json
{
  "contact_id": 46692527,
  "total_leads": 10,
  "closed_leads": 3,
  "closed_statuses_used": [142, 143],
  "deal_history": [
    {
      "lead_id": 32548389,
      "name": "Дом с участком в Подмосковье",
      "price": 8350000,
      "status_id": 142,
      "status_name": "Успешно реализовано",
      "pipeline_id": 10112058,
      "pipeline_name": "Продажа домов с участками",
      "closed_at": "2025-10-27T19:05:32.000Z",
      "created_at": "2025-10-10T13:04:07.000Z",
      "responsible_user_id": 12345,
      "custom_fields": []
    },
    {
      "lead_id": 32806637,
      "name": "Услуги по строительству",
      "price": 2500000,
      "status_id": 142,
      "status_name": "Объект сдан",
      "pipeline_id": 10140482,
      "pipeline_name": "Продажа услуг по строительству",
      "closed_at": "2025-09-15T12:30:00.000Z",
      "created_at": "2025-08-01T10:00:00.000Z",
      "responsible_user_id": 12345,
      "custom_fields": []
    }
  ]
}
```

## Использование в подфлоу

### Пример: Использование истории при новой продаже

Когда клиент обращается повторно, можно использовать историю его предыдущих покупок для персонализации:

```javascript
// В n8n Code node перед вызовом нейропродажника

// 1. Получаем историю сделок клиента
const contactId = $json.contact_id; // из предыдущего шага

const historyResponse = await fetch('http://localhost:5678/webhook/amocrm-get-deal-history', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ contact_id: contactId })
});

const history = await historyResponse.json();

// 2. Формируем контекст для нейропродажника
let context = '';

if (history.deal_history && history.deal_history.length > 0) {
  context += 'История покупок клиента:\n';
  
  history.deal_history.forEach((deal, index) => {
    context += `${index + 1}. ${deal.name} - ${deal.price.toLocaleString('ru-RU')} руб. `;
    context += `(${deal.pipeline_name}, закрыто: ${new Date(deal.closed_at).toLocaleDateString('ru-RU')})\n`;
  });
  
  context += '\nИспользуй эту информацию для персонализации предложения.\n';
} else {
  context = 'Это новый клиент без истории покупок.\n';
}

// 3. Передаем контекст в следующий шаг
return {
  json: {
    ...$json,
    client_history_context: context,
    previous_deals_count: history.closed_leads || 0
  }
};
```

### Пример: Анализ успешных сделок

```javascript
// Анализ паттернов покупок клиента

const history = $json.deal_history;

if (history && history.length > 0) {
  // Средний чек
  const avgPrice = history.reduce((sum, deal) => sum + deal.price, 0) / history.length;
  
  // Самые популярные воронки
  const pipelines = {};
  history.forEach(deal => {
    pipelines[deal.pipeline_name] = (pipelines[deal.pipeline_name] || 0) + 1;
  });
  
  const topPipeline = Object.entries(pipelines)
    .sort((a, b) => b[1] - a[1])[0];
  
  return {
    json: {
      ...$json,
      analysis: {
        avg_deal_price: avgPrice,
        total_deals: history.length,
        top_pipeline: topPipeline[0],
        top_pipeline_count: topPipeline[1]
      }
    }
  };
}
```

## Закрытые статусы по умолчанию

По умолчанию workflow фильтрует сделки со статусами:
- **142** - "Успешно реализовано" / "Объект сдан"
- **143** - "Закрыто и не реализовано"

Эти статусы являются стандартными финальными статусами в большинстве воронок amoCRM.

### Как определить закрытые статусы в вашей CRM

Запустите скрипт проверки:

```bash
cd /projects/brats/scripts
python3 check_amocrm_closed_statuses.py
```

Скрипт покажет все закрытые статусы в ваших воронках и их ID.

## Интеграция с нейропродажником

### Передача истории в контекст диалога

```python
# В sales-agent при обработке нового сообщения

async def get_client_context(contact_id: int) -> str:
    """Получение контекста клиента из истории сделок"""
    
    # Вызов n8n workflow
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://n8n:5678/webhook/amocrm-get-deal-history",
            json={"contact_id": contact_id}
        )
        history = response.json()
    
    if not history.get("deal_history"):
        return "Новый клиент без истории покупок."
    
    context = "История покупок клиента:\n"
    for deal in history["deal_history"][:3]:  # Последние 3 сделки
        context += f"- {deal['name']}: {deal['price']:,} руб. "
        context += f"({deal['pipeline_name']})\n"
    
    return context
```

## Обработка ошибок

Workflow обрабатывает следующие случаи:

1. **Контакт не найден** - возвращает ошибку с описанием
2. **Нет сделок** - возвращает пустой массив `deal_history`
3. **Нет закрытых сделок** - возвращает `closed_leads: 0`

Пример обработки в коде:

```javascript
try {
  const response = await fetch('http://localhost:5678/webhook/amocrm-get-deal-history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contact_id: 123 })
  });
  
  const result = await response.json();
  
  if (result.deal_history && result.deal_history.length > 0) {
    // Есть история
    console.log(`Найдено ${result.closed_leads} закрытых сделок`);
  } else {
    // Нет истории
    console.log('История сделок пуста');
  }
} catch (error) {
  console.error('Ошибка получения истории:', error);
}
```

## Производительность

- Workflow обрабатывает до **250 сделок** за один запрос (лимит amoCRM API)
- Для получения большего количества сделок используйте пагинацию (можно расширить workflow)
- Время выполнения: ~1-3 секунды в зависимости от количества сделок

## См. также

- [n8n Workflows README](../n8n/workflows/README.md)
- [amoCRM API Setup](./AMOCRM_API_SETUP.md)
- [amoCRM Integration Architecture](./AMOCRM_INTEGRATION_ARCHITECTURE.md)
