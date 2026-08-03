# AARU Timers — Справочник для администратора

Все команды, кроме `/setup`, `/timer`, `/events` и `/clear`, находятся внутри
одной команды `/config` (например, `/roles set` ниже на деле — `/config roles set`).

## Команды

| Команда | Что делает |
|---|---|
| `/setup` | Опубликовать/переместить таймер-доску + сообщение с ролями в этот канал |
| `/timer start / list / cancel` | Ручные таймеры обратного отсчёта |
| `/config roles set / clear / list / message` | Привязать/отвязать роль для пинга; переопубликовать кнопки самозаписи |
| `/config roles hide / show` | Удалить/переопубликовать всё сообщение с подпиской на роли |
| `/config language set / show` | Переключить язык (английский/русский) |
| `/config names set / clear / list` | Свои названия событий/боссов на сервере, по языкам |
| `/config permissions set / clear / list` | Уровень прав для каждой защищённой функции, отдельно на сервер |
| `/config buttons hide / show / list` | Скрыть/показать отдельные кнопки |
| `/config pings message / message-reset / disable / enable / list` | Свой текст пинга; отключить пинг для цели без отвязки роли |
| `/config board time-format / time-reset / time-list` | Свой текст «осталось 6м»/«через 1ч» на доске |
| `/config board category-set / category-reset / category-list` | Переместить событие между «Боссы и PvP» и «Ближайшие события», отдельно на сервер |
| `/config board hide-event / show-event / hidden-list` | Полностью убрать событие с доски (и его пинги) |
| `/events` | Личный снимок доски |
| `/clear` | Удалить сообщения самого бота в этом канале |

## Цели для пингов

Guild Boss, JMG, Morpheus, Rangora, Skyfin, Halcy (= Golden Plains Battle), Tokens (= Prairie или Invasion) — оповещения за 15 и 5 минут, Tokens — за 30 и 5 минут. Каждая привязывается к роли через `/config roles set`, участники подписываются сами кнопкой.

## Цели для прав (`/config permissions set target:<x>`)

preset_timers, timer, setup, roles, language, names, clear_cmd, buttons, pings, board — для каждой отдельно задаётся уровень: Everyone / Send Messages / Manage Messages / Manage Server.

По умолчанию: кнопки-пресеты = Everyone. `setup`, `language`, `board` (включает и `/config roles hide|show`) = Manage Server — эти команды меняют то, как бот выглядит для *всего сервера* (расположение, язык, текст, видимость событий или само наличие сообщения с ролями). Всё остальное = Manage Messages. Сама `/config permissions` жёстко закреплена на Manage Server.

## Заметки

- Доска обновляется каждые 5с; проверка пингов идёт в отдельном цикле раз в 1с.
- Переименование через `/config names set` никогда не ломает логику — внутренние ключи фиксированы, меняется только отображаемый текст.
- `/clear` удаляет только сообщения самого бота, чужие никогда не трогает.
- После смены кнопок/подписей/формулировок нужно переопубликовать (`/setup` или `/config roles message`), чтобы изменения появились на новом сообщении.
- Русские пинги и текст на доске («осталось {time}» / «через {time}») включены по умолчанию при `/config language set` на русский — можно переопределить отдельно через `/config pings message` / `/config board time-format`.
- Скрытие события (`/config board hide-event`) убирает его с доски И останавливает пинги, в отличие от `/config pings disable` (глушит только пинги) или `/config board category-set` (перемещает, но событие остаётся видимым).
