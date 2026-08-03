# AARU Timers — Справочник для администратора

Все команды, кроме `/setup`, `/timer` и `/clear`, находятся внутри
одной команды `/config` (например, `/config roles ping`). Внутри `/config`
большинство подкоманд объединяют несколько старых отдельных команд в один
параметр-выпадающий список `action` (Set/Clear/List/Hide/Show и т.д.) вместо
отдельной команды на каждый глагол — чтобы список "/" оставался коротким.

## Команды

| Команда | Что делает |
|---|---|
| `/setup` | Опубликовать/переместить таймер-доску + сообщение с ролями в этот канал |
| `/timer start / list / cancel` | Ручные таймеры обратного отсчёта (start/cancel — автодополнение по 3 пресетам, локализовано) |
| `/config roles ping` (action: Set/Clear/List) | Привязать/отвязать/показать, какая роль пингуется перед таймером/событием |
| `/config roles message` | Переопубликовать кнопки самозаписи |
| `/config roles visibility` (action: Hide/Show) | Удалить/переопубликовать всё сообщение с подпиской на роли |
| `/config language` (action: Set/Show) | Переключить язык (английский/русский) |
| `/config names` (action: Set/Clear/List) | Свои названия событий/боссов на сервере, по языкам |
| `/config permissions` (action: Set/Clear/List) | Уровень прав для каждой защищённой функции, отдельно на сервер |
| `/config buttons` (action: Hide/Show/List) | Скрыть/показать отдельные кнопки |
| `/config pings message` (action: Set/Reset) | Свой текст пинга |
| `/config pings alerts` (action: Disable/Enable/List) | Отключить пинг для цели без отвязки роли |
| `/config board wording` (action: Set/Reset/List) | Свой текст «осталось 6м»/«через 1ч» на доске |
| `/config board category` (action: Set/Reset/List) | Переместить событие между «Боссы и PvP» и «Ближайшие события», отдельно на сервер |
| `/config board events` (action: Hide/Show/List) | Полностью убрать событие с доски (и его пинги) |
| `/clear` | Удалить сообщения самого бота в этом канале |

## Цели для пингов

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie или Invasion) — оповещения за 15 и 5 минут, Tokens — за 30 и 5 минут. Каждая привязывается к роли через `/config roles ping` (action: Set), участники подписываются сами кнопкой.

## Цели для прав (`/config permissions` action:Set target:\<x\>)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings, board — для каждой отдельно задаётся уровень: Everyone / Send Messages / Manage Messages / Manage Server.

По умолчанию: кнопки-пресеты = Everyone. `setup`, `language`, `board` (включает и `/config roles visibility`) = Manage Server — эти команды меняют то, как бот выглядит для *всего сервера* (расположение, язык, текст, видимость событий или само наличие сообщения с ролями). Всё остальное = Manage Messages. Сама `/config permissions` жёстко закреплена на Manage Server.

## Заметки

- Доска обновляется каждые 5с; проверка пингов идёт в отдельном цикле раз в 1с.
- Переименование через `/config names` (action: Set) никогда не ломает логику — внутренние ключи фиксированы, меняется только отображаемый текст.
- `/clear` удаляет только сообщения самого бота, чужие никогда не трогает.
- После смены кнопок/подписей/формулировок нужно переопубликовать (`/setup` или `/config roles message`), чтобы изменения появились на новом сообщении.
- Русские пинги и текст на доске («осталось {time}» / «через {time}») включены по умолчанию при `/config language` (action: Set) на русский — можно переопределить отдельно через `/config pings message` / `/config board wording`.
- Скрытие события (`/config board events` action:Hide) убирает его с доски И останавливает пинги, в отличие от `/config pings alerts` (action: Disable, глушит только пинги) или `/config board category` (action: Set, перемещает, но событие остаётся видимым).
