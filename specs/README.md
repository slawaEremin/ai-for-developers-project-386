# Контракт API

Источник контракта — `main.tsp`. Сейчас описаны `GET /health` с ответом
`{"status":"ok"}` и `POST /api/meeting-types` с ответом 201 и объектом
`id`, `name`, `description`, `durationMinutes`.
`GET /api/meeting-types` возвращает `serverTime` в UTC и `items` с типами;
порядок — name, затем id, по кодовым точкам Unicode с учётом регистра.
`GET /api/meeting-types/{id}` возвращает тип без оболочки. Неправильный id —
422, корректный отсутствующий — 404 / `MEETING_TYPE_NOT_FOUND`.

Идентификатор содержит 1–64 строчных латинских букв, цифр и дефисов, по краям
буква или цифра. После удаления пробелов по краям название содержит 1–120
символов Unicode без переносов, описание — 1–2000 с допустимыми переносами.
Длительность — целое число 1–540: JSON `30.0` допустим, `"30"` и `true` нет.
Все поля обязательны, `null` и неизвестные поля запрещены.

POST принимает `application/json`. Ошибки 400/409/415/422/503/500 содержат
`code`, `message` и при необходимости `fieldErrors`. Ответы календаря имеют
`Cache-Control: no-store`. Доступность и бронирование добавляются следующими
задачами спецификации.

`make generate` создаёт `specs/generated/openapi.json`,
`apps/backend/app/generated/models.py` и `apps/frontend/src/api/generated`.
TypeSpec компилируется в OpenAPI 3.1 с закрытыми объектными схемами;
`datamodel-code-generator` создаёт Pydantic v2 с запретом лишних полей,
`@hey-api/openapi-ts` — SDK на Fetch API. Дополнительные смысловые проверки
выполняются сервером поверх сгенерированной модели.

Генераторы устанавливаются корневым npm workspace и uv-окружением бэкенда.
Результаты хранятся в Git и вручную не редактируются. `make lint` повторяет
генерацию во временном каталоге и проверяет соответствие файлов.

## Доступность

`GET /api/meeting-types/{id}/availability` возвращает `Availability`:
`serverTime`, `timeZone` (`Europe/Moscow`), включительные `windowStartDate`
и `windowEndDate`, а также ровно 14 элементов `days`. Каждый день содержит
`date` (YYYY-MM-DD) и `slots` с `startsAt`/`endsAt` в UTC с Z; пустые дни
имеют пустой массив. Ошибки 404/422/503/500 и `Cache-Control: no-store`
следуют общему формату. Слоты учитывают общую занятость всех типов.


## Предстоящие встречи владельца

`GET /api/bookings/upcoming` возвращает `UpcomingBookings`: `serverTime` (UTC Z)
и `items` полных объектов `Booking` (`id`, `meetingTypeId`, `meetingTypeName`,
`startsAt`, `endsAt`, `durationMinutes`, `timeZone`). Включаются записи
с `startsAt >= serverTime`, сортировка по началу и UUID, без фильтров,
пагинации и ограничения окном гостя. Пустой результат — 200 и пустой массив.
Ошибки 503/500 и `Cache-Control: no-store` соответствуют общему контракту.
