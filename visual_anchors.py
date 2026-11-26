"""Zero-dependency Pillow visual anchor extractor for native slide reconstruction."""
from pathlib import Path
from PIL import Image


def _color_dist(c1, c2):
    return abs(c1[0] - c2[0]) + abs(c1[1] - c2[1]) + abs(c1[2] - c2[2])


def _rgb_hex(rgb):
    return "{:02X}{:02X}{:02X}".format(*rgb[:3])


def _sample_bg(im, width, height):
    px = im.load()
    margin = max(4, min(10, width // 100, height // 100))
    pts = [
        px[margin, margin],
        px[width - margin - 1, margin],
        px[margin, height - margin - 1],
        px[width - margin - 1, height - margin - 1],
    ]
    return tuple(sorted(c[i] for c in pts)[1] for i in range(3))


def _dark_text_bbox(im, x0, y0, x1, y1, dark_thresh=140):
    px = im.load()
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y][:3]
            if (r + g + b) / 3 < dark_thresh:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    x_min, y_min, x_max, y_max = min(xs), min(ys), max(xs), max(ys)
    if x_max - x_min < 20 or y_max - y_min < 12:
        return None
    return dict(x=x_min, y=y_min, w=x_max - x_min, h=y_max - y_min)


def _detect_bottom_bar(im, bg, width, height):
    px = im.load()
    y_start = int(height * 0.78)
    y_end = int(height * 0.98)
    x_pad = max(16, int(width * 0.03))
    min_span = int(width * 0.42)
    row_hits = []
    for y in range(y_start, y_end):
        xs = [x for x in range(x_pad, width - x_pad) if 8 <= _color_dist(px[x, y], bg) <= 85]
        if len(xs) >= min_span:
            row_hits.append((y, min(xs), max(xs)))
    if len(row_hits) < 18:
        return None
    y1, y2 = row_hits[0][0], row_hits[-1][0]
    h = y2 - y1
    if not (24 <= h <= int(height * 0.16)):
        return None
    x1 = sorted(r[1] for r in row_hits)[len(row_hits) // 2]
    x2 = sorted(r[2] for r in row_hits)[len(row_hits) // 2]
    samples = []
    for y in range(y1 + 5, y2 - 5, 3):
        for x in range(x1 + 10, min(x1 + 50, x2 - 10), 4):
            c = px[x, y][:3]
            if (c[0] + c[1] + c[2]) / 3 > 170:
                samples.append(c)
    if not samples:
        return None
    fill = tuple(sorted(c[i] for c in samples)[len(samples) // 2] for i in range(3))
    if _color_dist(fill, bg) < 8:
        return None
    return dict(x=x1, y=y1, w=x2 - x1, h=h, fill=_rgb_hex(fill))


def _detect_vertical_divider(im, bg, width, height):
    px = im.load()
    x_min, x_max = int(width * 0.35), int(width * 0.65)
    y_min, y_max = int(height * 0.20), int(height * 0.82)
    min_run = int(height * 0.30)
    best = None
    for x in range(x_min, x_max):
        ys = [y for y in range(y_min, y_max) if 12 <= _color_dist(px[x, y], bg) <= 165]
        if len(ys) >= min_run:
            span = ys[-1] - ys[0]
            if span > 0 and len(ys) / span >= 0.78:
                # Ensure it's a thin line, not a wide filled block
                left_diff = _color_dist(px[max(0, x - 6), ys[len(ys) // 2]], bg)
                right_diff = _color_dist(px[min(width - 1, x + 6), ys[len(ys) // 2]], bg)
                if left_diff < 12 and right_diff < 12:
                    if best is None or len(ys) > best[0]:
                        col = px[x, ys[len(ys) // 2]][:3]
                        best = (len(ys), x, ys[0], ys[-1], _rgb_hex(col))
    if not best:
        return None
    _, x, y1, y2, col = best
    return dict(x=x, y=y1, w=2, h=y2 - y1, color=col)


def extract_anchors(image_path, width=1280, height=720):
    """Extract background color and key layout anchors using only Pillow (no OCR)."""
    path = Path(image_path)
    if not path.is_file():
        return {}
    with Image.open(path) as raw:
        im = raw.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    bg = _sample_bg(im, width, height)
    anchors = dict(background=_rgb_hex(bg))
    title = _dark_text_bbox(im, int(width * 0.03), int(height * 0.02), int(width * 0.97), int(height * 0.21))
    if title:
        anchors["title_box"] = title
    bar = _detect_bottom_bar(im, bg, width, height)
    if bar:
        anchors["bottom_bar"] = bar
    divider = _detect_vertical_divider(im, bg, width, height)
    if divider:
        anchors["dividers"] = [divider]
    return anchors
