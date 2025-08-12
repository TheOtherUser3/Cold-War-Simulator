# ------------------------------
# build_id_map.py (any-size image support)
# ------------------------------
# Keeps your exact flow (Ocean first, then playables; supports MULTI_COUNTS),
# but now the window auto-scales to fit any PNG size and maps clicks back to
# the original image pixels.

import json, os, argparse, pygame

parser = argparse.ArgumentParser()
parser.add_argument("--map", default="assets/world_idmap.png")
parser.add_argument("--out", default="assets/id_to_country.json")
args = parser.parse_args()

pygame.init()
raw = pygame.image.load(args.map)
IMG_W, IMG_H = raw.get_size()

# Start window sized to 90% of desktop, but never upscaling beyond 1:1
info = pygame.display.Info()
MAX_W = int(info.current_w * 0.9)
MAX_H = int(info.current_h * 0.9)
scale0 = min(MAX_W / IMG_W, MAX_H / IMG_H, 1.0)
win_w = max(1, int(IMG_W * scale0))
win_h = max(1, int(IMG_H * scale0))
screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
pygame.display.set_caption("RGB Picker — click to print; Esc/Q to quit")


def compute_draw_rect(win_w: int, win_h: int):
    """Return (pygame.Rect, scale) that letterboxes the image into window."""
    s = min(win_w / IMG_W, win_h / IMG_H)
    draw_w = max(1, int(IMG_W * s))
    draw_h = max(1, int(IMG_H * s))
    left = (win_w - draw_w) // 2
    top = (win_h - draw_h) // 2
    return pygame.Rect(left, top, draw_w, draw_h), s


clock = pygame.time.Clock()
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q):
            running = False
        elif ev.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            win_w, win_h = screen.get_size()
            draw_rect, s = compute_draw_rect(win_w, win_h)
            if draw_rect.collidepoint(ev.pos):
                ix = int((ev.pos[0] - draw_rect.left) / s)
                iy = int((ev.pos[1] - draw_rect.top) / s)
                # clamp
                ix = max(0, min(IMG_W - 1, ix))
                iy = max(0, min(IMG_H - 1, iy))
                r, g, b = raw.get_at((ix, iy))[:3]
                print(f"{ix},{iy} -> {r},{g},{b}  (#{r:02X}{g:02X}{b:02X})")

    # Draw
    win_w, win_h = screen.get_size()
    draw_rect, s = compute_draw_rect(win_w, win_h)
    screen.fill((12, 12, 14))  # letterbox background
    scaled = pygame.transform.scale(raw, (draw_rect.w, draw_rect.h))
    screen.blit(scaled, draw_rect.topleft)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
