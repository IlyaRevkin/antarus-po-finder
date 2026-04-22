# Antarus ПО Finder — Техническая документация

## 1. Что это за приложение и зачем оно нужно

**Antarus ПО Finder** — десктопная программа под Windows. Её задача:
- хранить базу прошивок для разного оборудования (ПЧ, КПЧ, НГР, ПЖ и т.д.)
- позволять наладчику быстро найти нужную прошивку по названию шкафа
- хранить сопутствующие файлы: карты IO, инструкции, параметры ПЧ/КПЧ/УПП
- синхронизироваться с папкой на сетевом диске (WebDAV или сетевая шара)

Приложение работает **полностью локально** — это не веб-сервис, не облако. Всё хранится в одном SQLite-файле и в папках на диске. Это важно: не нужен интернет, сервер или база данных на сервере.

---

## 2. Технологии и библиотеки — почему именно они

### PySide6 (GUI-фреймворк)

```
pip install PySide6
```

**Что это:** Python-обёртка над Qt6 — промышленным C++ фреймворком для создания десктопных приложений. Qt используется в Adobe, Autodesk, VLC и тысячах других продуктов.

**Почему не tkinter/PyQt5/wxPython:**
- `tkinter` — встроен в Python, но выглядит как Windows 95. Нет нормальной темизации.
- `PyQt5` — предыдущая версия, лицензия GPL (коммерческое использование платное). PySide6 — официальная обёртка от самой Qt Company, лицензия LGPL (можно использовать бесплатно).
- `wxPython` — менее популярен, меньше документации, хуже поддержка.

**Ключевые компоненты Qt которые используются:**
- `QApplication` — сам процесс приложения, главный цикл событий
- `QMainWindow` — главное окно с менюбаром, статусбаром и т.д.
- `QWidget`, `QLabel`, `QPushButton`, `QLineEdit` — стандартные виджеты
- `QVBoxLayout`, `QHBoxLayout`, `QFormLayout` — менеджеры компоновки (раскладка виджетов)
- `QStackedWidget` — стек страниц (как вкладки, но без заголовков)
- `QScrollArea` — прокручиваемая область
- `QSvgRenderer` — рендеринг SVG-файлов
- `QTimer` — таймер для фоновых задач
- `Signal` — механизм событий (паттерн Observer)
- **QSS (Qt Style Sheets)** — CSS-подобный язык стилей для виджетов

### SQLite (база данных)

Встроен в Python, никаких дополнительных установок.

**Почему SQLite, а не PostgreSQL/MySQL/файлы:**
- Приложение работает на одном компьютере — нет смысла в клиент-серверной БД
- SQLite — это один файл. Легко бекапить, копировать, переносить
- Скорость достаточная: база на 10 000 записей открывается мгновенно
- `python3` поставляется со встроенным модулем `sqlite3` — никаких дополнительных пакетов

### py7zr (работа с 7z-архивами)

```
pip install py7zr
```

**Зачем:** прошивки часто приходят в 7z-архивах. При загрузке приложение автоматически их распаковывает. ZIP поддерживается встроенным `zipfile`, а для 7z нужна отдельная библиотека.

### Pillow (обработка изображений)

```
pip install Pillow
```

**Зачем в этом проекте:** только для генерации `icon.ico` в `make_assets.py`. В самом приложении не используется. При сборке EXE нужна иконка — `make_assets.py` её генерирует.

### qrcode (QR-коды)

```
pip install qrcode[pil]
```

**Зачем:** в разделе «Поиск» есть функция загрузки фото со смартфона. Приложение поднимает HTTP-сервер и показывает QR-код с адресом — пользователь сканирует и отправляет фото прямо с телефона. Библиотека `qrcode` генерирует изображение QR-кода, `[pil]` — это extras которые добавляют поддержку Pillow для рендеринга.

### pyinstaller (сборка EXE)

```
pip install pyinstaller
```

**Зачем:** превращает Python-скрипт + все зависимости в один `.exe` файл. Пользователю не нужно устанавливать Python.

**Как работает:** PyInstaller анализирует импорты в коде, собирает все нужные `.py` и `.dll` файлы, упаковывает в архив внутри EXE. При запуске EXE распаковывает себя во временную папку и запускает Python-интерпретатор изнутри.

---

## 3. Архитектура — слои приложения

Проект разделён на 4 слоя. Это называется **Layered Architecture** (слоистая архитектура). Каждый слой знает только о слоях ниже себя — никогда не наоборот.

```
┌─────────────────────────────────────────────────────┐
│  UI (app/ui/)                                        │
│  PySide6-виджеты, страницы, стили, иконки            │
│  Знает о: Services, Domain                           │
├─────────────────────────────────────────────────────┤
│  Services (app/services/)                            │
│  Бизнес-логика: поиск, загрузка, синхронизация       │
│  Знает о: Infrastructure, Domain                     │
├─────────────────────────────────────────────────────┤
│  Infrastructure (app/infrastructure/)                │
│  База данных, файловая система, архивы               │
│  Знает о: Domain                                     │
├─────────────────────────────────────────────────────┤
│  Domain (app/domain/)                                │
│  Модели данных и исключения                          │
│  Ни о чём не знает — чистые данные                   │
└─────────────────────────────────────────────────────┘
```

**Зачем это нужно?** Если завтра понадобится сменить SQLite на другую БД — меняем только `infrastructure/database.py`. UI и сервисы не трогаем. Или если нужно добавить веб-интерфейс — берём те же `Services` и пишем новый UI.

---

## 4. Слой Domain — чистые данные

### `app/domain/models.py` — модели данных

Здесь описаны **dataclass**-структуры. Dataclass — это класс Python, который автоматически создаёт `__init__`, `__repr__` и другие методы. Никакого кода, только данные.

#### `Version` — версия прошивки

```python
@dataclass(order=True, frozen=True)
class Version:
    raw:    str   # исходная строка, например "3.42.260414"
    prefix: int   # первая цифра (3)
    major:  int   # вторая цифра (42)
    date:   int   # третья цифра (260414) или 0 если нет
```

`frozen=True` — объект нельзя изменить после создания (immutable). Это нужно чтобы версии можно было сравнивать: `v1 > v2`.

`order=True` — автоматически генерирует `__lt__`, `__gt__` и т.д. Сравнение идёт по полям в порядке их объявления: сначала `prefix`, потом `major`, потом `date`.

Пример использования:
```python
v1 = Version.parse("3.42.260414")  # prefix=3, major=42, date=260414
v2 = Version.parse("3.43")         # prefix=3, major=43, date=0
v2 > v1  # True — потому что major 43 > 42
```

#### `Rule` — правило соответствия

Правило — это главная сущность приложения. Оно отвечает на вопрос: **«Для каких шкафов нужна эта прошивка и где она лежит?»**

```python
@dataclass
class Rule:
    id:               int        # ID в БД
    name:             str        # уникальное имя правила, например "НГР КПЧ SMH5"
    equipment_type:   str        # тип оборудования: "НГР", "ПЖ", ...
    work_type:        str        # тип работы: "ПЧ", "КПЧ", "УПП", ...
    controller:       str        # контроллер: "SMH5", "KINCO", ...
    firmware_dir:     str        # путь к папке с прошивкой ОТНОСИТЕЛЬНО root_path
    firmware_type:    str        # "plc" или "plc_hmi"
    keywords:         list[str]  # слова по которым ищем, например ["НГР", "КПЧ", "SMH5"]
    exclude_keywords: list[str]  # слова-исключения (если есть — не показывать)
    kw_mode:          str        # "all" (все слова должны совпасть) или "any" (хоть одно)
    io_map_path:      str        # путь к файлу карты входов/выходов
    instructions_path:str        # путь к инструкциям
    passport_dir:     str        # путь к паспорту
    param_pch_dir:    str        # путь к папке с параметрами ПЧ/КПЧ
    param_upp_dir:    str        # путь к папке с параметрами УПП
    notes_file:       str        # путь к файлу примечаний
    disk_snapshot:    dict       # снимок состояния папки (mtime + count) для синхронизации
    local_synced:     bool       # синхронизировать ли эту папку локально
```

#### `FirmwareVersion` — конкретная версия прошивки

```python
@dataclass
class FirmwareVersion:
    rule_names:  list[str]  # к каким правилам относится
    version:     Version    # объект версии
    filename:    str        # имя файла
    local_path:  str        # путь к файлу на локальном компьютере
    disk_path:   str        # путь на сетевом диске
    controller:  str        # контроллер
    device_type: str        # тип устройства
    work_type:   str        # тип работы
    description: str        # описание версии
    changelog:   str        # список изменений
    archived:    bool       # архивная (старая) версия или нет
```

#### `Template` — шаблон параметров

```python
@dataclass
class Template:
    name:          str       # уникальное название
    template_type: str       # "pch" или "upp"
    path:          str       # путь к файлу/папке с шаблоном
    description:   str
    rule_names:    list[str] # для каких правил используется
```

#### `SearchResult` — результат поиска

```python
@dataclass
class SearchResult:
    rule:           Rule
    score:          int                      # чем выше — тем лучше совпадение
    latest_version: Optional[FirmwareVersion]  # самая новая версия
    all_versions:   list[FirmwareVersion]      # все версии
```

### `app/domain/exceptions.py` — исключения

Вместо того чтобы возвращать строки с ошибками, сервисы **бросают исключения**. Это стандартная практика Python. UI ловит их через `try/except` и показывает пользователю.

```python
class FirmwareFinderError(Exception):       # базовый класс
class VersionConflictError(FirmwareFinderError):   # версия не новее существующей
class InvalidVersionError(FirmwareFinderError):    # неверный формат версии
class DiskUnavailableError(FirmwareFinderError):   # диск недоступен
class RuleNotFoundError(FirmwareFinderError):      # правило не найдено
class FileOperationError(FirmwareFinderError):     # ошибка файловой системы
```

Почему типизированные исключения, а не просто `raise Exception("ошибка")`?
Потому что UI может их различать. Например, `VersionConflictError` содержит поля `existing` и `attempted` — UI может показать диалог "Хотите загрузить всё равно?" вместо просто текста ошибки.

---

## 5. Слой Infrastructure — работа с данными

### `app/infrastructure/database.py` — SQLite база данных

#### Как подключается

```python
self._conn = sqlite3.connect(db_path, check_same_thread=False)
self._conn.row_factory = sqlite3.Row      # результаты как словари, не кортежи
self._conn.execute('PRAGMA journal_mode=WAL')   # WAL = Write-Ahead Logging
self._conn.execute('PRAGMA foreign_keys=ON')    # соблюдение внешних ключей
```

`check_same_thread=False` — разрешает обращаться к БД из разных потоков (нужно для фоновой синхронизации).

`journal_mode=WAL` — режим при котором читатели не блокируют писателей. Без этого фоновый поток синхронизации мог бы заблокировать UI.

#### Схема таблиц

**`rules`** — правила соответствия:
```sql
id, name, equipment_type, work_type, controller,
firmware_dir, firmware_type, software_name,
keywords,           -- JSON-массив: ["НГР", "КПЧ", "SMH5"]
exclude_keywords,   -- JSON-массив: ["ПЖ"]
kw_mode,            -- "all" или "any"
local_dir,          -- имя папки в локальном кеше
local_synced,       -- 0 или 1
disk_snapshot,      -- JSON: {"mtime": 1234567.0, "file_count": 42}
param_pch_dir, param_upp_dir,
passport_dir, io_map_path, instructions_path, notes_file,
created_at, updated_at
```

**`versions`** — загруженные прошивки:
```sql
id, rule_names,     -- JSON-массив имён правил
version,            -- строка "3.42.260414"
filename, local_path, disk_path,
controller, device_type, work_type, extension,
description, changelog,
upload_date,
archived,           -- 0 или 1
io_map_path, param_pch_dir, param_upp_dir
```

**`templates`** — шаблоны параметров:
```sql
id, name, template_type, path, description,
rule_names          -- JSON-массив
```

**`sync_queue`** — очередь действий для синхронизации:
```sql
id, action,         -- "upload", "update", "delete"
payload,            -- JSON с деталями действия
created_at, synced_at,
status,             -- "pending", "synced", "failed"
error
```

**`settings`** — ключ-значение настроек:
```sql
key TEXT PRIMARY KEY,
value TEXT
```

#### Почему JSON-поля в SQLite?

Поля вроде `keywords` хранятся как JSON-строка `'["НГР", "КПЧ"]'` прямо в текстовом поле. Это называется **денормализация**. Для реляционной БД "правильно" было бы создать отдельную таблицу `rule_keywords`. Но это усложнило бы код, а выигрыша нет — мы всегда читаем правило целиком. Поэтому JSON в поле — разумный компромисс.

При чтении из БД JSON автоматически декодируется в Python-список:
```python
# В database.py при загрузке правила:
keywords = json.loads(row['keywords'] or '[]')
```

### `app/infrastructure/filesystem.py` — работа с файлами

**`parse_firmware_info(filename, path)`** — авто-определение метаданных из имени файла.

Использует регулярные выражения для поиска в строке:
```python
# Ищет контроллер:
re.search(r'\bSMH\s*5\b', "НГР_КПЧ_SMH5_v3.42.zip", re.I)  # → "SMH5"

# Ищет версию:
re.search(r'\b(\d+\.\d+(?:\.\d{6})?)\b', "firmware_3.42.260414.exe")  # → "3.42.260414"
```

`\b` в регулярном выражении — это "граница слова". Оно гарантирует что "SMH5" не совпадёт с "ASMH5test".

**`disk_snapshot(path)`** — снимок состояния папки:
```python
{'mtime': 1234567890.0, 'file_count': 42}
```
`mtime` — время последнего изменения папки (unix timestamp). Синхронизация сравнивает этот снимок с сохранённым в БД — если изменился, папка обновилась.

### `app/infrastructure/archive.py` — распаковка архивов

Поддерживает форматы:
- `.zip` — встроенный Python `zipfile`. Проверяет защиту паролем через `flag_bits & 0x1`.
- `.7z` — библиотека `py7zr`. Импортируется в `try/except` — если не установлена, программа не падает, просто не умеет распаковывать 7z.
- `.rar` — не поддерживается (требует WinRAR который не является свободным ПО).

---

## 6. Слой Services — бизнес-логика

### `app/services/config_service.py` — настройки

Все настройки хранятся в таблице `settings` в формате ключ-значение. `ConfigService` — это типизированная обёртка над этой таблицей.

**Где хранится БД:**
```python
if getattr(sys, 'frozen', False):
    # Запущен как EXE (PyInstaller устанавливает sys.frozen = True)
    _BASE = os.path.dirname(sys.executable)
else:
    # Запущен как Python-скрипт
    _BASE = корень_проекта

APP_DATA = os.path.join('%LOCALAPPDATA%', 'FirmwareFinder')
# Например: C:\Users\Ilia\AppData\Local\FirmwareFinder\
DB_PATH  = APP_DATA + '\firmware_finder.db'
```

`%LOCALAPPDATA%` — стандартная папка Windows для данных приложений. Туда можно писать без прав администратора.

**Почему настройки в SQLite, а не в INI/JSON файле:**
- Атомарность записи: SQLite никогда не оставит файл наполовину записанным
- Та же БД уже используется для прошивок — не нужен отдельный файл

**Пример геттера:**
```python
def root_path(self) -> str:
    """Путь к сетевому диску с прошивками."""
    return self._db.get_setting('root_path', '')
```

### `app/services/search_service.py` — поиск прошивок

**Алгоритм поиска:**

1. Нормализация запроса: переводим в верхний регистр, заменяем `,;-/\` на пробелы
2. Для каждого правила из БД вызываем `_score_rule(rule, query)`
3. Правила с нулевым score отбрасываем
4. Сортируем по убыванию score

**Как считается score:**

```python
# Режим "all" — ВСЕ ключевые слова должны присутствовать
for kw in rule.keywords:
    if кw_в_запросе:
        score += len(kw) * 2  # длинные слова дают больше очков
    else:
        return 0  # хоть одно слово не нашли — правило не подходит

# Режим "any" — ХОТЯ БЫ ОДНО слово
for kw in rule.keywords:
    if kw_в_запросе:
        score += len(kw) * 2
```

Длинные слова весят больше потому что "SMH5" (4 символа) даёт `4*2=8` очков, а "КПЧ" (3 символа) — `3*2=6`. Это разумно: чем специфичнее слово, тем оно обычно длиннее.

**Проверка границ слова:**
```python
_BOUNDARY = re.compile(r'(?<![А-ЯЁA-Z0-9])%s(?![А-ЯЁA-Z0-9])')
```
`(?<!...)` и `(?!...)` — "lookbehind" и "lookahead" — проверяют что слева/справа от слова нет буквы или цифры. Это нужно чтобы поиск "ПЧ" не нашёл "КПЧ".

### `app/services/upload_service.py` — загрузка прошивок

**Полный пайплайн загрузки:**

1. **Парсинг версии** — `Version.parse(version_str)`. Если формат неверный — `InvalidVersionError`.

2. **Проверка конфликта** — для каждого выбранного правила берём из БД последнюю версию и сравниваем. Нельзя загрузить версию 3.41 если уже есть 3.42.

3. **Нормализация имени файла** — имя исходного файла нормализуется перед сохранением:
   ```python
   base, ext = os.path.splitext(os.path.basename(src_path))
   filename  = base.upper().replace(' ', '_') + ext.upper()
   # "firmware ngr v3.42.exe" → "FIRMWARE_NGR_V3.42.EXE"
   ```

4. **Копирование файлов:**
   ```
   Если root_path задан и доступен:
     Копируем в: root_path / rule.firmware_dir / version_str /
     Например: Z:\firmwares\НГР_КПЧ_SMH5\3.42.260414\
   
   Если root_path недоступен (оффлайн):
     Копируем в: %LOCALAPPDATA%\FirmwareFinder\firmware\rule_name\version_str\
   ```

5. **Распаковка архивов** — если загруженный файл это `.zip` или `.7z`, автоматически распаковываем в ту же папку.

6. **CHANGELOG.md** — создаём файл с датой, описанием и списком изменений в папке версии.

7. **Запись в БД** — создаём запись `FirmwareVersion` в таблице `versions`.

### `app/services/sync_service.py` — синхронизация

**Что делает:**

```
Каждые 5 минут (QTimer в MainWindow):
  1. Проверяем доступность root_path (os.path.isdir)
  2. Для каждого правила с local_synced=True:
     a. Считаем disk_snapshot(rule.firmware_dir)
     b. Сравниваем с сохранённым снимком в БД
     c. Если изменился — копируем новые файлы в локальный кеш
     d. Обновляем снимок в БД
  3. Синхронизируем шаблоны (копируем в LOCAL_TEMPLATES)
```

**Фоновый поток:**
```python
def run_background(self, on_done, on_error):
    def _worker():
        updates = self._check_updates()
        on_done(updates)          # вызывается из фонового потока!
    threading.Thread(target=_worker, daemon=True).start()
```

⚠️ **Важно:** `on_done` вызывается из фонового потока. В PySide6 нельзя обновлять UI из не-главного потока. Поэтому в `MainWindow._on_sync_done` используется `self._status.showMessage()` — Qt автоматически ставит его в очередь главного потока через механизм событий.

`daemon=True` — поток-демон автоматически завершается когда закрывается главное приложение. Без этого программа могла бы не закрыться.

---

## 7. Слой UI — интерфейс пользователя

### Как устроен Qt-приложение

```python
app = QApplication(sys.argv)  # 1. Создаём приложение (один на всё)
window = MainWindow()          # 2. Создаём главное окно
window.show()                  # 3. Показываем
sys.exit(app.exec())           # 4. Запускаем цикл событий (блокируется здесь)
```

**Цикл событий** — бесконечный цикл внутри Qt который:
- ждёт события (клик, нажатие клавиши, таймер)
- находит нужный обработчик
- вызывает его

Пока `app.exec()` не вернул управление — программа "крутится" в этом цикле.

### `app/ui/app.py` — главное окно

`MainWindow(QMainWindow)` — главное окно приложения. Оно:
- создаёт все сервисы (Database, ConfigService, SearchService, UploadService, SyncService)
- строит сайдбар с кнопками навигации
- создаёт `QStackedWidget` — стек страниц
- добавляет четыре страницы: Search, Upload, Templates, Settings
- управляет ролями и темой

**QStackedWidget** — это контейнер, в котором одновременно видна только одна "страница" (как вкладки). При навигации мы просто вызываем `stack.setCurrentWidget(page)`.

**Сигналы и слоты (Signal/Slot):**
```python
# Определяем сигнал (в классе):
theme_changed = Signal(str)

# Соединяем с обработчиком:
self.theme_changed.connect(self._update_sidebar_icons)

# Испускаем сигнал:
self.theme_changed.emit('dark')
# → автоматически вызывается self._update_sidebar_icons('dark')
```

Это паттерн **Observer** (наблюдатель). Один объект "говорит" другим что что-то изменилось, не зная о них напрямую.

**Роли и доступ:**
```python
ROLE_ACCESS = {
    'naladchik':     {'search'},
    'programmer':    {'search', 'upload', 'templates'},
    'administrator': {'search', 'upload', 'templates', 'settings'},
}
```
При смене роли кнопки навигации скрываются/показываются через `btn.setVisible(page_id in allowed)`.

### `app/ui/theme.py` — темы оформления

**QSS (Qt Style Sheets)** — CSS для виджетов Qt. Пример:
```css
QPushButton {
    background-color: #89b4fa;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #b4d0fb;
}
QPushButton#secondary {   /* применяется к кнопкам с objectName="secondary" */
    background: transparent;
    border: 1px solid #45475a;
}
```

В приложении две палитры: `DARK` и `LIGHT`. Функция `build_qss(c)` принимает словарь цветов и возвращает строку QSS со всеми стилями. `apply_theme(app, name)` устанавливает эту строку на весь `QApplication`.

**Хитрость с SVG-стрелкой для ComboBox:**
```python
def _ensure_arrow_svg(color: str) -> str:
    # Qt не умеет рисовать стрелку ComboBox цветом из палитры
    # Поэтому создаём SVG-файл с нужным цветом в %TEMP% и указываем путь в QSS
    svg = f'<svg...><path fill="{color}" d="..."/></svg>'
    with open(path, 'w') as f: f.write(svg)
    return path
```

### `app/ui/icons.py` — SVG иконки для кнопок

Иконки хранятся как строки SVG-кода прямо в Python-файле. Функция `make_icon(name, color, size)` рендерит SVG с нужным цветом в `QIcon`:

```python
# Цвет вставляется в SVG-шаблон:
svg = ICONS['search'].format(color=color)  # подставляем цвет в placeholder
renderer = QSvgRenderer(bytes(svg, 'utf-8'))
# Рендерим в QPixmap нужного размера
# QPixmap → QIcon
```

### `app/ui/pages/` — страницы приложения

Каждая страница — это отдельный класс, наследник `QWidget`. При создании вызывает `_build()` который создаёт все виджеты и компоновки.

**Компоновки (layouts):**
- `QVBoxLayout` — виджеты сверху вниз
- `QHBoxLayout` — виджеты слева направо
- `QFormLayout` — таблица "метка: поле" (используется в формах)
- `layout.addWidget(widget, stretch)` — stretch задаёт как виджет расширяется при изменении размера окна (0 = не растягивается, 1 = растягивается)

**`search_page.py` — поиск:**
1. Поле ввода + кнопка «Найти»
2. При нажатии → `SearchService.search(query)` → список `SearchResult`
3. Для каждого результата определяем статус локального кеша:
   - `_has_local(rule)` — есть ли **актуальная** версия локально
   - `_has_any_local(rule)` — есть ли **хоть какая-то** версия локально
4. Создаём `FirmwareCard(result, has_local, has_any_local)` и добавляем в `QVBoxLayout`
5. Старые карточки удаляем через `card.deleteLater()`

История версий (`_show_history`): `QSplitter` — сверху таблица, снизу `QTextEdit`
с полным описанием и changelog при выборе строки.

**`upload_page.py` — загрузка:**
- Левая колонка: `DropZone` + кнопка авто-определения + список правил
- Правая колонка: форма метаданных в `QScrollArea` + кнопка загрузки
- `DropZone` → `path_dropped` сигнал → `_on_file_dropped()` → заполняем форму
- Кнопка загрузки → `UploadService.upload(...)` → запись в БД
- После загрузки: `io_map_path` и `instructions_path` сохраняются в правило если не заданы

Авто-создание правила (`_create_rule_for_upload`): поиск существующего правила
требует совпадения **и** типа оборудования, **и** контроллера одновременно.
Это исключает ложные совпадения когда разное оборудование использует один контроллер.

**`settings_page.py` — настройки:**
Использует `QTabWidget` (вкладки) или кастомные tab-кнопки. Настройки читаются из `ConfigService` при открытии и сохраняются при нажатии «Сохранить».

Вложенный класс `_RuleDialog(QDialog)` — диалог редактирования правила. `QDialog` — это всплывающее окно, блокирующее основное (`exec()` ждёт пока диалог не закроют).

### `app/ui/widgets/` — кастомные виджеты

**`DropZone(QLabel)`** — большая зона drag-and-drop:
```python
def dragEnterEvent(self, event):    # курсор входит в зону при перетаскивании
    if event.mimeData().hasUrls():  # проверяем что тащат файл
        event.acceptProposedAction() # разрешаем drop

def dropEvent(self, event):         # файл отпустили
    path = event.mimeData().urls()[0].toLocalFile()
    self.path_dropped.emit(path)    # испускаем сигнал с путём
```

`event.mimeData()` — данные перетаскиваемого объекта. `hasUrls()` проверяет что это файл(ы). `urls()[0].toLocalFile()` конвертирует URL вида `file:///C:/path/file.exe` в `C:\path\file.exe`.

**`MiniDropZone(QLabel)`** — маленькая зона рядом с кнопками «Файл»/«Папка»:
- `text()` возвращает путь (не отображаемый текст!) — для совместимости с кодом который вызывает `.text()`
- `setText(path)` устанавливает путь — для совместимости с кодом который вызывает `.setText()`
- Визуально показывает `os.path.basename(path)` или «Перетащите файл или папку»
- `QLabel.setText(self, ...)` используется внутри чтобы обойти наш override

**`FirmwareCard(QFrame)`** — карточка результата поиска:
Показывает название правила, актуальную версию, кнопки действий. Испускает сигналы:
```python
instructions_requested = Signal(SearchResult)
map_requested          = Signal(SearchResult)
download_requested     = Signal(SearchResult)
copy_name_requested    = Signal(SearchResult)
history_requested      = Signal(SearchResult)
# и т.д.
```

Кнопка синхронизации выбирается по состоянию кеша:
```python
if has_local:
    pass                    # актуальная версия — кнопки загрузки нет
elif has_any_local:
    btn = 'Обновить'        # есть старая версия
else:
    btn = 'Синхронизировать'  # нет локальной копии вообще
```

Кнопка «Копировать» формирует строку в формате `ПРАВИЛО_3.42.260414`
(верхний регистр, пробелы → подчёркивания).

`SearchPage` подключается к сигналам карточки и обрабатывает их.

---

## 8. Поток данных — как всё связано

### Запуск приложения

```
main.py
  → QApplication создаётся
  → MainWindow.__init__()
      → Database(DB_PATH)         # открываем/создаём SQLite
      → ConfigService(db)         # обёртка над настройками
      → SearchService(db)         # поиск
      → UploadService(db, cfg)    # загрузка
      → SyncService(db, cfg)      # синхронизация
      → _build_sidebar()          # строим сайдбар
      → SearchPage(self)          # создаём страницу поиска
      → UploadPage(self)          # ...загрузки
      → TemplatesPage(self)       # ...шаблонов
      → SettingsPage(self)        # ...настроек
      → apply_theme(app, 'light') # применяем тему
      → QTimer → _start_sync()    # через 1.5 сек запустим синхронизацию
  → window.show()
  → app.exec()  ← здесь программа "живёт"
```

### Поиск прошивки

```
Пользователь вводит "НГР КПЧ SMH5" и жмёт Enter
  → search_page._do_search()
      → SearchService.search("НГР КПЧ SMH5")
          → db.get_all_rules()  ← все правила из SQLite
          → для каждого правила: _score_rule(rule, "НГР КПЧ SMH5")
          → db.get_versions_for_rule(rule.name)  ← версии из SQLite
          → возвращает [SearchResult(rule, score=14, latest=v3.42), ...]
      → _render_results([SearchResult, ...])
          → для каждого результата: FirmwareCard(result)
          → card.instructions_requested.connect(self._open_instructions)
          → results_layout.addWidget(card)
```

### Загрузка прошивки

```
Пользователь перетащил файл firmware.exe
  → DropZone.dropEvent() → path_dropped.emit("C:\...\firmware.exe")
  → upload_page._on_file_dropped("C:\...\firmware.exe")
      → UploadService.auto_detect(path) → заполняем поля формы

Пользователь нажал "Загрузить"
  → upload_page._do_upload()
      → читаем поля формы (version, controller, ...)
      → UploadService.upload(src_path, version, rule_names, ...)
          → Version.parse(version_str)          # парсим версию
          → db.get_latest_version(rule_name)    # проверяем конфликт
          → shutil.copy2(src, dst)              # копируем файл
          → extract_all_in_dir(ver_dir)         # распаковываем архивы
          → _write_changelog(ver_dir, ...)      # создаём CHANGELOG.md
          → db.add_version(fv)                  # записываем в БД
          → return FirmwareVersion
      → show_status("Прошивка 3.42.260414 загружена")
```

---

## 9. Как добавить новую функциональность

### Добавить новое поле к правилу

1. **`app/domain/models.py`** — добавить поле в `Rule`:
   ```python
   my_new_field: str = ''
   ```

2. **`app/infrastructure/database.py`** — добавить колонку в SQL-схему:
   ```sql
   my_new_field TEXT NOT NULL DEFAULT ''
   ```
   Добавить в `upsert_rule()` в списки INSERT и UPDATE.
   Добавить в `_row_to_rule()` при чтении:
   ```python
   my_new_field = row['my_new_field']
   ```

3. **`app/ui/pages/settings_page.py`** — добавить поле в диалог редактирования правила (`_RuleDialog`).

4. **`app/ui/pages/search_page.py`** — если нужно использовать поле в карточке.

### Добавить новую страницу

1. Создать файл `app/ui/pages/my_page.py`:
   ```python
   class MyPage(QWidget):
       def __init__(self, main_win):
           super().__init__()
           self._mw = main_win
           self._build()
       def _build(self):
           layout = QVBoxLayout(self)
           # ... добавляем виджеты
   ```

2. В `app/ui/app.py` добавить в `NAV_ITEMS`:
   ```python
   ('mypage', 'Моя страница', 'programmer'),
   ```

3. Добавить в `ROLE_ACCESS` нужным ролям:
   ```python
   'programmer': {'search', 'upload', 'templates', 'mypage'},
   ```

4. Импортировать и добавить страницу:
   ```python
   from app.ui.pages.my_page import MyPage
   self._add_page('mypage', MyPage(self))
   ```

### Добавить новую настройку

1. В `app/services/config_service.py` добавить в `DEFAULTS`:
   ```python
   'my_setting': 'default_value',
   ```

2. Добавить геттер и сеттер:
   ```python
   def my_setting(self) -> str:
       return self.get('my_setting')
   
   def set_my_setting(self, value: str):
       self.set('my_setting', value)
   ```

3. В `app/ui/pages/settings_page.py` добавить виджет в нужную вкладку.

---

## 10. Частые вопросы

**Q: Почему при запуске EXE приложение долго стартует?**
A: PyInstaller при первом запуске распаковывает себя во временную папку `%TEMP%\_MEIxxxxxx`. Это занимает 2-5 секунд. При повторных запусках папка уже существует.

**Q: Куда сохраняются данные при работе как EXE?**
A: `C:\Users\{User}\AppData\Local\FirmwareFinder\` — БД, локальный кеш прошивок, шаблоны.

**Q: Почему нельзя открыть `.pdf` инструкцию?**
A: `os.startfile(path)` открывает файл программой по умолчанию. Если PDF-ридер не установлен — Windows вернёт ошибку. Приложение перехватывает её и предлагает открыть папку с файлом.

**Q: Как работает фоновая синхронизация если нет сетевого диска?**
A: `SyncService.disk_status()` проверяет `os.path.isdir(root_path)`. Если папка недоступна — синхронизация просто пропускается, никаких ошибок.

**Q: Что такое `__init__.py` в каждой папке?**
A: Пустой файл который говорит Python «это пакет» (package). Без него `from app.services.search_service import SearchService` не будет работать.

**Q: Что такое `if __name__ == '__main__':` в `main.py`?**
A: Этот блок выполняется только когда файл запускается напрямую (`python main.py`), но не когда он импортируется другим файлом. Это стандартная защита от нежелательного запуска при импорте.
