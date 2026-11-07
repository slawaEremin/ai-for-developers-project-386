# Трекер задач: GitHub Issues

Задачи и спецификации проекта ведутся в GitHub Issues репозитория
`slawaEremin/ai-for-developers-project-386`. Используй CLI `gh`.

## Репозиторий

Перед первым созданием задачи в сессии проверь:
`gh repo view --json nameWithOwner`.

Целевой репозиторий — `slawaEremin/ai-for-developers-project-386`.
Если CLI выбрал другой репозиторий, укажи
`--repo slawaEremin/ai-for-developers-project-386`.
Создание задач в другом репозитории требует согласования с пользователем.

## Операции с задачами

- Создать: `gh issue create --title "..." --body-file <file>`.
- Прочитать: `gh issue view <number> --json number,title,body,labels,comments`.
- Получить список: `gh issue list --state open --json number,title,body,labels,comments`.
  При необходимости добавь фильтры `--label` и `--state`.
- Обновить описание: `gh issue edit <number> --body-file <file>`.
- Оставить комментарий: `gh issue comment <number> --body-file <file>`.
- Добавить или снять метку: `gh issue edit <number> --add-label "..."`
  или `--remove-label "..."`. Словарь меток — в `triage-labels.md`.
- Закрыть: сначала опубликуй объяснение отдельным комментарием,
  затем выполни `gh issue close <number>`. Это сохраняет объяснение,
  даже если задача уже закрыта.

Многострочный текст записывай во временный файл и передавай через
`--body-file`, сохраняя настоящие переводы строк.

Указание навыка «опубликовать в трекере» означает создать GitHub issue.
Указание «получить соответствующую задачу» означает прочитать её через
`gh issue view`.

## Подзадачи и зависимости

- Создать подзадачу: `gh issue create --parent <parent> ...`.
- Связать существующие задачи:
  `gh issue edit <parent> --add-sub-issue <child>`.
- Если подзадачи недоступны, добавь `Part of #<parent>` в начало описания
  дочерней задачи и ссылку на неё в список задач родителя.
- Зависимости оформляй штатными связями GitHub:
  `gh issue create --blocked-by <number>,<number> ...`
  или `gh issue edit <child> --add-blocked-by <blocker>`.
- Если штатные зависимости недоступны, добавь строку
  `Blocked by: #<number>, #<number>` в начало описания.
- Задача готова к работе, когда закрыты все блокирующие задачи.
  Количество открытых блокировок:
  `gh api repos/slawaEremin/ai-for-developers-project-386/issues/<number> --jq .issue_dependencies_summary.blocked_by`.
  Значение `0` означает отсутствие открытых блокировок.

## Pull requests

**PRs as a request surface: no.**

При переключении флага на `yes` triage обрабатывает внешние PR
по тем же ролям и состояниям, используя команды `gh pr`.

- Читать описание: `gh pr view <number>`, комментарии:
  `gh pr view <number> --comments`, изменения: `gh pr diff <number>`.
- Получить открытые внешние PR:
  `gh api --paginate 'repos/slawaEremin/ai-for-developers-project-386/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`.
- Комментировать, назначать метки и закрывать:
  `gh pr comment`, `gh pr edit --add-label` / `--remove-label`,
  `gh pr close`. Многострочный текст передавай через `--body-file`.

Номера issues и PR общие. Если тип ссылки `#<number>` неизвестен,
проверь `gh pr view <number>`, затем `gh issue view <number>`.

## Работа навыка wayfinder

- Карта — одна задача с меткой `wayfinder:map` и разделами
  Notes / Decisions-so-far / Fog.
- Рабочие задачи — её подзадачи с метками `wayfinder:research`,
  `wayfinder:prototype`, `wayfinder:grilling` или `wayfinder:task`.
  Если подзадачи недоступны, используй список задач в карте
  и строку `Part of #<map>` в дочерних задачах.
- Следующая задача — первая по порядку карты открытая подзадача
  без исполнителя и открытых блокировок.
- При взятии задачи назначь себя:
  `gh issue edit <number> --add-assignee @me`.
  Это первая запись сессии wayfinder.
- При завершении опубликуй результат комментарием, закрой задачу
  и добавь краткий вывод со ссылкой в Decisions-so-far карты.
