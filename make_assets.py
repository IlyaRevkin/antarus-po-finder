"""
Генерация icon.ico для Antarus PO Finder.

Проблема Pillow: он конвертирует мелкие ICO-записи в BMP — отсюда плохое качество.
Решение: пишем ICO вручную с PNG-сжатием для ВСЕХ размеров (Windows Vista+ формат).
Каждая запись ICO — это буквально сырой PNG внутри файла. Качество = 1:1 с исходником.

Запуск: python make_assets.py
"""

import io
import os
import struct
import sys

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

SVG_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'logo.svg')
ICO_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.ico')
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_size(renderer: QSvgRenderer, size: int) -> Image.Image:
    """Рендерит SVG через Qt в RGBA PIL Image заданного размера."""
    # Суперсэмплинг: рендерим в 4x, сжимаем LANCZOS → идеальное AA на мелких размерах
    ss = max(1, 256 // size)        # для 16px → 16x, для 64px → 4x, для 256px → 1x
    render_px = size * ss

    qimg = QImage(render_px, render_px, QImage.Format.Format_ARGB32)
    qimg.fill(Qt.GlobalColor.transparent)
    p = QPainter(qimg)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()

    # Qt → PNG bytes → PIL (через файл-буфер, без ручной конвертации байт)
    buf = io.BytesIO()
    tmp = QImage(render_px, render_px, QImage.Format.Format_ARGB32)
    qimg.save(f'/tmp/_ico_{size}.png' if os.name != 'nt' else
              os.path.join(os.environ.get('TEMP', '.'), f'_ico_{size}.png'), 'PNG')

    tmp_path = (os.path.join(os.environ.get('TEMP', '.'), f'_ico_{size}.png'))
    qimg.save(tmp_path, 'PNG')
    img = Image.open(tmp_path).convert('RGBA')
    os.remove(tmp_path)

    if ss > 1:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def write_png_ico(images: dict[int, Image.Image], out_path: str):
    """
    Записывает ICO-файл с PNG-сжатием для каждого размера.

    Структура ICO (Windows Vista+ PNG ICO):
      [ICONDIR header 6 bytes]
      [ICONDIRENTRY × N, по 16 байт каждая]
      [PNG data entry 1]
      [PNG data entry 2]
      ...

    Pillow использует BMP для мелких размеров — это даёт артефакты.
    Здесь каждая запись — сырой PNG, качество идентично исходнику.
    """
    sizes = sorted(images.keys())

    # Конвертируем каждый PIL Image → сырые PNG-байты
    png_bytes_list = []
    for s in sizes:
        buf = io.BytesIO()
        images[s].save(buf, format='PNG', optimize=False)
        png_bytes_list.append(buf.getvalue())

    # Считаем смещения данных в файле
    header_size  = 6
    dir_entry_sz = 16
    data_offset  = header_size + dir_entry_sz * len(sizes)

    offsets = []
    cur = data_offset
    for data in png_bytes_list:
        offsets.append(cur)
        cur += len(data)

    with open(out_path, 'wb') as f:
        # ICONDIR: reserved=0, type=1 (ICO), count=N
        f.write(struct.pack('<HHH', 0, 1, len(sizes)))

        # ICONDIRENTRY для каждого размера
        for i, s in enumerate(sizes):
            w = 0 if s >= 256 else s   # 256 кодируется как 0 по стандарту ICO
            h = 0 if s >= 256 else s
            f.write(struct.pack('<BBBBHHII',
                w,                       # ширина
                h,                       # высота
                0,                       # цветов в палитре (0 = не используется)
                0,                       # зарезервировано
                1,                       # planes
                32,                      # бит на пиксель
                len(png_bytes_list[i]),  # размер PNG-данных
                offsets[i],              # смещение PNG-данных от начала файла
            ))

        # Сами PNG-данные
        for data in png_bytes_list:
            f.write(data)


def main():
    os.makedirs('assets', exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    renderer = QSvgRenderer(SVG_PATH)
    if not renderer.isValid():
        print(f'ERROR: bad SVG: {SVG_PATH}')
        sys.exit(1)

    print('Rendering sizes...')
    images = {}
    for s in ICO_SIZES:
        images[s] = render_size(renderer, s)
        print(f'  {s}x{s} ok')

    print(f'Writing PNG-ICO: {ICO_PATH}')
    write_png_ico(images, ICO_PATH)
    size_kb = os.path.getsize(ICO_PATH) // 1024
    print(f'Done: {ICO_PATH} ({size_kb} KB)')


if __name__ == '__main__':
    main()
