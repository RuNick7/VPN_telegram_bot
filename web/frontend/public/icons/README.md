# PWA-иконки

Фронт ожидает в этой папке файлы:

| Файл | Размер | Назначение |
|---|---|---|
| `icon-192.png` | 192×192 | Android home screen, fallback для большинства браузеров |
| `icon-512.png` | 512×512 | Splash screen, install dialog |
| `icon-maskable-512.png` | 512×512 | «Maskable» иконка для Android (контент в центральных 80%, фон сплошной) |
| `badge-72.png` | 72×72 | Монохромный белый значок для шторки уведомлений (используется в push) |

И на уровень выше, в `web/frontend/public/`:

| Файл | Размер | Назначение |
|---|---|---|
| `apple-touch-icon.png` | 180×180 | iOS «На экран „Домой"» |
| `favicon.ico` | 32×32 multi-res | Вкладка браузера |

## Как нарезать всё из одного исходника

Положи исходный логотип (PNG ≥ 1024×1024, лучше с прозрачным фоном) рядом, например в
`web/frontend/public/icons/source.png`. Потом:

```bash
cd web/frontend/public/icons

# обычные иконки (с прозрачностью)
magick source.png -resize 192x192 icon-192.png
magick source.png -resize 512x512 icon-512.png

# maskable: контент в 80% safe-area + сплошной фон theme_color
magick source.png -resize 410x410 -gravity center \
       -background "#0b0b13" -extent 512x512 icon-maskable-512.png

# badge (монохромный белый, прозрачный фон)
magick source.png -resize 72x72 -alpha extract \
       -background none -fill "#ffffff" -colorize 100 \
       badge-72.png

# apple-touch-icon
magick source.png -resize 180x180 ../apple-touch-icon.png

# favicon (несколько размеров в одном .ico)
magick source.png -define icon:auto-resize=64,48,32,16 ../favicon.ico
```

Если у тебя на macOS нет `magick`:

```bash
brew install imagemagick
```

После замены иконок можно проверить корректность через Lighthouse → PWA audit.
