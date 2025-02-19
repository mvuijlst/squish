#############################################
##                                         ##
##          S Q U I S H  v4.0.1            ##
##                                         ##
##      (c) 2025 Michel Vuijlsteke         ##
##                                         ##
#############################################

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import sys
import pygame
import random
import datetime
import json
import math
from pygame.locals import *
from heapq import heappush, heappop


############################################################
# 0) RESOURCE PATH HELPER
############################################################
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller --onefile.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


############################################################
# 1) BASIC CONFIGURATION
############################################################
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
HUNTER = 4        
EGG = 5
PUSHER = 6
SENTINEL = 7

GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE

CHAR_WIDTH  = 8
CHAR_HEIGHT = 16
SCALE_X = 2
SCALE_Y = 2
SHEET_COLS = 16
SHEET_ROWS = 16

HUNTER_VALUE   = 2
EGG_VALUE      = 3
PUSHER_VALUE   = 5
SENTINEL_VALUE = 7

############################################################
# 2) COLOR DEFINITIONS
############################################################
TEXT_COLOR_DEFAULT = (0xa7, 0xa7, 0xa7) 
HIGHLIGHT_COLOR    = (0xfa, 0xfa, 0xfa) 

PLAYER_COLOR   = (0x59, 0xe1, 0xe3)
WALL_COLOR     = (0xff, 0xea, 0x16)
BLOCK_COLOR    = (0x00, 0x55, 0x00) 

HUNTER_COLOR   = (0xff, 0x16, 0xb0)
EGG_COLOR_0    = (0xfa, 0xe9, 0x01)
EGG_COLOR_1    = (0xfa, 0x82, 0x01)
EGG_COLOR_FLASH1 = (0xfa, 0x01, 0x01)
EGG_COLOR_FLASH2 = (0xff, 0xff, 0xff)
PUSHER_COLOR   = (0x99, 0x35, 0xff)
SENTINEL_COLOR = (0x47, 0x52, 0xcb)

STATUS_BG_COLOR = (0x00, 0x00, 0x00)

############################################################
# 3) GLOBAL RESOURCES
############################################################
sprite_sheet = None
sounds = {}
lives = 3
current_level = 0
running_level_score = 0
cumulative_time = 0
game_over_flag = False

levels_data = []
global_pause_offset = 0

current_spritesheet = "dos_spritesheet.png"

############################################################
# 4) HELPER FUNCTIONS
############################################################
def cell_type(cell):
    if isinstance(cell, tuple):
        return cell[0]
    return cell

def tint_surface(surface, tint_color):
    tinted = surface.copy()
    tinted.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)
    return tinted

def get_egg_color(cell):
    now = get_game_time()
    egg_total_time = cell[1]
    egg_start = cell[2]
    elapsed = now - egg_start
    if elapsed < 0:
        elapsed = 0
    progress = elapsed / egg_total_time
    if progress < 0.75:
        return EGG_COLOR_0
    elif progress < 0.90:
        return EGG_COLOR_1
    else:
        flash_period = 250
        flashes = (now // flash_period) % 2
        return EGG_COLOR_FLASH1 if flashes == 0 else EGG_COLOR_FLASH2

def get_cell_color(cell):
    t = cell_type(cell)
    if t == PLAYER:
        return PLAYER_COLOR
    elif t == UNMOVEABLE_BLOCK:
        return WALL_COLOR
    elif t == MOVEABLE_BLOCK:
        return BLOCK_COLOR
    elif t == HUNTER:
        return HUNTER_COLOR
    elif t == EGG:
        return get_egg_color(cell)
    elif t == PUSHER:
        return PUSHER_COLOR
    elif t == SENTINEL:
        return SENTINEL_COLOR
    return (0, 0, 0)

def get_game_time():
    return pygame.time.get_ticks() - global_pause_offset

############################################################
# 5a) HIGH SCORE HANDLING
############################################################
SCORE_FILE = "highscores.dat"

def encrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return bytes(b ^ key for b in data)

def decrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return encrypt_xor(data, key)

def load_highscores() -> list:
    if not os.path.exists(resource_path(SCORE_FILE)):
        save_highscores([])
        return []
    try:
        with open(resource_path(SCORE_FILE), "rb") as f:
            encrypted = f.read()
        decrypted = decrypt_xor(encrypted, 0xAA).decode("utf-8", errors="ignore")
        lines = decrypted.strip().split("\n")
        scores = []
        for line in lines:
            parts = line.split("|")
            if len(parts) == 5:
                dt_str, lvl_str, scr_str, time_str, name_str = parts
                record = {
                    "date": dt_str,
                    "level": lvl_str,
                    "score": int(scr_str),
                    "time": int(time_str),
                    "name": name_str,
                    "highlight": False
                }
                if record["name"].endswith("##"):
                    record["name"] = record["name"][:-2]
                    record["highlight"] = True
                scores.append(record)
        scores.sort(key=lambda s: (-s["score"], s["time"]))
        return scores
    except Exception as e:
        print("Error loading high scores:", e)
        return []

def save_highscores(scores: list):
    scores = sorted(scores, key=lambda s: (-s["score"], s["time"]))[:20]
    lines = []
    for s in scores:
        nm = s["name"] + ("##" if s.get("highlight") else "")
        lines.append(f'{s["date"]}|{s["level"]}|{s["score"]}|{s["time"]}|{nm}')
    data = "\n".join(lines)
    encrypted = encrypt_xor(data.encode("utf-8"), 0xAA)
    with open(resource_path(SCORE_FILE), "wb") as f:
        f.write(encrypted)

def ask_player_name() -> str:
    name = ""
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    while True:
        for evt in pygame.event.get():
            if evt.type == QUIT:
                pygame.quit(); sys.exit()
            elif evt.type == KEYDOWN:
                if evt.key == K_RETURN:
                    return name.strip() or "anonymous"
                elif evt.key == K_BACKSPACE:
                    name = name[:-1]
                elif evt.key == K_ESCAPE:
                    return "anonymous"
                else:
                    ch = evt.unicode
                    if ch.isprintable():
                        name += ch
        screen.fill((0, 0, 0))
        draw_text(screen, "High score! Enter your name:", 50, 100, TEXT_COLOR_DEFAULT)
        draw_text(screen, name, 50, 140, TEXT_COLOR_DEFAULT)
        pygame.display.flip()
        clock.tick(15)

def format_time(seconds: int) -> str:
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes:02}:{sec:02}"

def wait_for_key():
    waiting = True
    clock = pygame.time.Clock()
    while waiting:
        for event in pygame.event.get():
            if event.type == KEYDOWN:
                waiting = False
        clock.tick(15)

############################################################
# 5b) HIGH SCORE SCREENS (SCROLLABLE)
############################################################
def show_highscores_overall_scroll(surface, clock, scores):
    line_spacing = 32
    x_margin = 10
    y_start = 10

    lines = []
    lines.append(("header", "    Name                     Date      Score  Time   Rank"))
    for idx, s in enumerate(scores, 1):
        color = HIGHLIGHT_COLOR if s.get("highlight") else TEXT_COLOR_DEFAULT
        name_full = s["name"]
        if len(name_full) > 32:
            name_full = name_full[:29] + "..."
        date_display = s["date"][:10]
        rank_char = "\x13"
        lvl = s["level"]
        if lvl and lvl[-1].isdigit():
            rank = lvl
        else:
            rank = lvl + rank_char

        line_text = f"{idx:2d}. {name_full}"
        filler_len = max(0, 28 - len(line_text))
        filler = "." * filler_len
        remainder = f" {date_display:<10}  {s['score']:>3d}  {format_time(s['time'])}  {rank}"
        full_line = line_text + filler + remainder
        lines.append(("line", full_line, color))

    # Footer
    lines.append(("footer", "Press TAB to toggle view, ESC to exit"))

    total_height = y_start + len(lines) * line_spacing + 20
    max_scroll = max(0, total_height - surface.get_height())
    scroll_offset = 0

    while True:
        surface.fill((0, 0, 0))
        y = y_start - scroll_offset
        for entry in lines:
            etype = entry[0]
            if etype == "header":
                text = entry[1]
                draw_text(surface, text, x_margin, y, TEXT_COLOR_DEFAULT)
                y += line_spacing
            elif etype == "line":
                text = entry[1]
                color = entry[2]
                draw_text(surface, text, x_margin, y, color)
                y += line_spacing
            elif etype == "footer":
                text = entry[1]
                draw_text(surface, text, x_margin, surface.get_height() - 30, TEXT_COLOR_DEFAULT)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    return "exit"
                elif event.key == K_TAB:
                    return "tab"
                elif event.key == K_UP:
                    scroll_offset = max(0, scroll_offset - line_spacing)
                elif event.key == K_DOWN:
                    scroll_offset = min(max_scroll, scroll_offset + line_spacing)
        clock.tick(15)

def show_highscores_by_level_scroll(surface, clock, scores):
    line_spacing = 32
    x_margin = 10
    y_start = 10

    lines = []
    groups = {}
    for s in scores:
        lvl_letter = s["level"][0] if s["level"] else ""
        groups.setdefault(lvl_letter, []).append(s)
    for lvl in sorted(groups.keys()):
        # Group header: "Level A", "Level B", etc.
        lines.append(("group", f"Level {lvl}", HIGHLIGHT_COLOR))
        # Only show top 3
        group = sorted(groups[lvl], key=lambda x: (-x["score"], x["time"]))[:3]
        for idx, rec in enumerate(group, 1):
            color = HIGHLIGHT_COLOR if rec.get("highlight") else TEXT_COLOR_DEFAULT
            name_full = rec["name"]
            if len(name_full) > 21:
                name_full = name_full[:18] + "..."
            date_display = rec["date"][:10]
            rank_char = "\x13"
            if rec["level"] and rec["level"][-1].isdigit():
                rec_rank = rec["level"]
            else:
                rec_rank = rec["level"] + rank_char
            line_text = f"{idx}. {name_full}"
            filler_len = max(0, 28 - len(line_text))
            filler = "." * filler_len
            remainder = f" {date_display:<10}  {rec['score']:>3d}  {format_time(rec['time'])}  {rec_rank}"
            full_line = line_text + filler + remainder
            lines.append(("line", full_line, color))
        lines.append(("blank",))

    lines.append(("footer", "Press TAB to toggle view, ESC to exit"))

    # Compute total height for scrolling
    total_height = 0
    for entry in lines:
        if entry[0] in ("group", "line", "footer"):
            total_height += line_spacing
        elif entry[0] == "blank":
            total_height += line_spacing

    total_height += y_start + 20
    max_scroll = max(0, total_height - surface.get_height())
    scroll_offset = 0

    while True:
        surface.fill((0, 0, 0))
        y = y_start - scroll_offset
        for entry in lines:
            etype = entry[0]
            if etype in ("group", "line"):
                text = entry[1]
                color = entry[2]
                draw_text(surface, text, x_margin, y, color)
                y += line_spacing
            elif etype == "blank":
                y += line_spacing
            elif etype == "footer":
                draw_text(surface, entry[1], x_margin, surface.get_height() - 30, TEXT_COLOR_DEFAULT)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    return "exit"
                elif event.key == K_TAB:
                    return "tab"
                elif event.key == K_UP:
                    scroll_offset = max(0, scroll_offset - line_spacing)
                elif event.key == K_DOWN:
                    scroll_offset = min(max_scroll, scroll_offset + line_spacing)
        clock.tick(15)


def high_score_screen(surface, clock):
    scores = load_highscores()
    view = 0  # 0 => overall, 1 => per-level
    while True:
        if view == 0:
            result = show_highscores_overall_scroll(surface, clock, scores)
        else:
            result = show_highscores_by_level_scroll(surface, clock, scores)
        if result == "tab":
            view = 1 - view
        elif result == "exit":
            return

def maybe_record_highscore(total_score: int, level: str, screen, time_played: int):
    scores = load_highscores()
    for s in scores:
        s["highlight"] = False

    qualifies = False
    if len(scores) < 20:
        qualifies = True
    else:
        worst = scores[-1]
        if total_score > worst['score'] or (total_score == worst['score'] and time_played < worst['time']):
            qualifies = True

    # Check top 5 per letter
    level_key = level[0] if level else ""
    level_scores = [s for s in scores if s["level"] and s["level"][0] == level_key]
    level_scores = sorted(level_scores, key=lambda s: (-s["score"], s["time"]))[:5]
    if level_scores:
        worst_level = level_scores[-1]
        if total_score > worst_level["score"] or (total_score == worst_level["score"] and time_played < worst_level["time"]):
            qualifies = True
    else:
        qualifies = True

    if qualifies:
        name = ask_player_name()
        highlight = True
    else:
        name = "anonymous"
        highlight = False

    dt_str = datetime.datetime.now().isoformat(timespec="seconds")
    new_record = {
        "date": dt_str,
        "level": level,
        "score": total_score,
        "time": time_played,
        "name": name,
        "highlight": highlight
    }
    scores.append(new_record)
    save_highscores(scores)
    high_score_screen(screen, pygame.time.Clock())

############################################################
# 5b) PAUSE AND QUIT CONFIRMATION
############################################################
def pause_game(screen):
    global global_pause_offset
    pause_start = pygame.time.get_ticks()
    paused = True
    clock = pygame.time.Clock()
    while paused:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key in (K_q, ord('q')):
                    if quit_confirm(screen):
                        return -1  # means user wants to quit to level select
                elif event.key == K_SPACE:
                    paused = False
        screen.fill((0, 0, 0))
        lines = ["Paused", "", "<q> to quit   <space> to continue"]
        total_w = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
        y = 100
        for line in lines:
            lw = len(line) * CHAR_WIDTH * SCALE_X
            x = (total_w - lw) // 2
            draw_text(screen, line, x, y, TEXT_COLOR_DEFAULT)
            y += 40
        pygame.display.flip()
        clock.tick(10)
    pause_duration = pygame.time.get_ticks() - pause_start
    global_pause_offset += pause_duration
    return pause_duration

def quit_confirm(screen) -> bool:
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key in (K_y, ord('y')):
                    return True
                elif event.key in (K_n, ord('n')):
                    return False
                else:
                    return False
        screen.fill((0, 0, 0))
        msg = "Do you really want to quit? (y/n)"
        total_w = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
        lw = len(msg) * CHAR_WIDTH * SCALE_X
        x = (total_w - lw) // 2
        y = 120
        draw_text(screen, msg, x, y, TEXT_COLOR_DEFAULT)
        pygame.display.flip()
        clock.tick(10)

############################################################
# 6c) SPRITE-SHEET TEXT RENDERING
############################################################
def load_sprite_sheet(filename):
    global sprite_sheet
    actual_path = resource_path(filename)
    sprite_sheet = pygame.image.load(actual_path).convert_alpha()

def draw_char(surface, ch, x, y, color):
    code = ord(ch)
    if code < 0 or code > 255:
        code = 127
    col = code % SHEET_COLS
    row = code // SHEET_COLS
    sx = col * CHAR_WIDTH
    sy = row * CHAR_HEIGHT
    char_rect = pygame.Rect(sx, sy, CHAR_WIDTH, CHAR_HEIGHT)
    char_surf = pygame.Surface((CHAR_WIDTH, CHAR_HEIGHT), pygame.SRCALPHA)
    char_surf.blit(sprite_sheet, (0, 0), char_rect)
    scaled_w = CHAR_WIDTH * SCALE_X
    scaled_h = CHAR_HEIGHT * SCALE_Y
    char_surf = pygame.transform.scale(char_surf, (scaled_w, scaled_h))
    char_surf = tint_surface(char_surf, color)
    surface.blit(char_surf, (x, y))

def draw_text(surface, text, x, y, color):
    offset_x = 0
    for ch in text:
        draw_char(surface, ch, x + offset_x, y, color)
        offset_x += CHAR_WIDTH * SCALE_X

############################################################
# 7) ENTITY MAPPINGS
############################################################
WALL_CHARS     = "\xDB\xDB"
BLOCK0_CHARS   = "\xB0\xB0"
BLOCK1_CHARS   = "\xB1\xB1"
BLOCK2_CHARS   = "\xB2\xB2"
PLAYER_CHARS   = "\x11\x10"
HUNTER_CHARS   = "\xC3\xB4"
EGG_CHARS      = "\x09\x09"
EMPTY_CHARS    = "  "
PUSHER_CHARS   = "\xCE\xCE"
SENTINEL_CHARS = "\xC7\xB6"

def get_cell_string(cell):
    t = cell_type(cell)
    if t == EMPTY:
        return EMPTY_CHARS
    elif t == PLAYER:
        return PLAYER_CHARS
    elif t == MOVEABLE_BLOCK:
        block_index = cell[1]
        if block_index == 0:
            return BLOCK0_CHARS
        elif block_index == 1:
            return BLOCK1_CHARS
        else:
            return BLOCK2_CHARS
    elif t == UNMOVEABLE_BLOCK:
        return WALL_CHARS
    elif t == HUNTER:
        return HUNTER_CHARS
    elif t == EGG:
        return EGG_CHARS
    elif t == PUSHER:
        return PUSHER_CHARS
    elif t == SENTINEL:
        return SENTINEL_CHARS
    else:
        return "??"

############################################################
# 8) DRAWING THE GRID & STATUS
############################################################
def draw_grid(screen, grid):
    screen.fill((0, 0, 0))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            color = get_cell_color(grid[y][x])
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

def draw_status_line(screen, grid, level_start_time, lives, level_name, running_level_score, time_offset):
    container_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    elapsed = time_offset + (get_game_time() - level_start_time) // 1000
    elapsed = max(0, elapsed)
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    current_enemy_count = sum(1 for row in grid for c in row if cell_type(c) in [HUNTER, PUSHER, SENTINEL, EGG])
    initial_egg_count = getattr(draw_status_line, "initial_egg_count", 0)
    segments = []
    segments.append(("Enemies: ", TEXT_COLOR_DEFAULT))
    segments.append((f"{current_enemy_count}", HIGHLIGHT_COLOR))
    if initial_egg_count > 0:
        current_egg_count = sum(1 for row in grid for c in row if cell_type(c) == EGG)
        segments.append(("  Eggs: ", TEXT_COLOR_DEFAULT))
        segments.append((f"{current_egg_count}", HIGHLIGHT_COLOR))
    segments.append(("  Level: ", TEXT_COLOR_DEFAULT))
    segments.append((f"{level_name}", HIGHLIGHT_COLOR))
    segments.append(("  Time: ", TEXT_COLOR_DEFAULT))
    segments.append((f"{time_str}", HIGHLIGHT_COLOR))
    segments.append(("  Lives: ", TEXT_COLOR_DEFAULT))
    segments.append((f"{lives}", HIGHLIGHT_COLOR))
    segments.append(("  Score: ", TEXT_COLOR_DEFAULT))
    segments.append((f"{running_level_score}", HIGHLIGHT_COLOR))
    total_seg_width = sum(len(text) * CHAR_WIDTH * SCALE_X for text, col in segments)
    x = container_width - total_seg_width - 5
    y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y)
    for text, col in segments:
        draw_text(screen, text, x, y, col)
        x += len(text) * CHAR_WIDTH * SCALE_X

############################################################
# 9) PLAYER SPAWN LOGIC & ANIMATION
############################################################
def get_player_position(grid):
    for yy in range(GRID_HEIGHT):
        for xx in range(GRID_WIDTH):
            if cell_type(grid[yy][xx]) == PLAYER:
                return (xx, yy)
    return None

def place_player_best_spot(grid, screen):
    enemies = []
    blocks = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            t = cell_type(grid[y][x])
            if t in [HUNTER, PUSHER, SENTINEL]:
                enemies.append((x, y))
            elif t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, EGG):
                blocks.append((x, y))
    best_pos = None
    best_edge = -1
    best_enemy = -1
    best_block = -1
    for yy in range(1, GRID_HEIGHT - 1):
        for xx in range(1, GRID_WIDTH - 1):
            if cell_type(grid[yy][xx]) == EMPTY:
                edge_dist = min(xx - 1, (GRID_WIDTH - 2) - xx, yy - 1, (GRID_HEIGHT - 2) - yy)
                enemy_dist = min([abs(xx - ex) + abs(yy - ey) for ex, ey in enemies] or [999])
                block_dist = min([abs(xx - bx) + abs(yy - by) for bx, by in blocks] or [999])
                if (edge_dist > best_edge or
                    (edge_dist == best_edge and enemy_dist > best_enemy) or
                    (edge_dist == best_edge and enemy_dist == best_enemy and block_dist > best_block)):
                    best_edge = edge_dist
                    best_enemy = enemy_dist
                    best_block = block_dist
                    best_pos = (xx, yy)
    if best_pos:
        x, y = best_pos
        show_spawn_animation(grid, screen, x, y)
        grid[y][x] = PLAYER

def respawn_player(grid, screen):
    for yy in range(GRID_HEIGHT):
        for xx in range(GRID_WIDTH):
            if cell_type(grid[yy][xx]) == PLAYER:
                grid[yy][xx] = EMPTY
    place_player_best_spot(grid, screen)

def show_spawn_animation(grid, screen, x, y):
    steps = [
        ("\xFA\xFA", (0xff, 0xff, 0xff)),
        ("--", (0xff, 0x00, 0x00)),
        ("\x1B\x1A", (0xff, 0x99, 0x00)),
        ("\xAE\xAF", (0xff, 0xff, 0x00)),
        ("<>", (0xff, 0xff, 0xff))
    ]
    clock = pygame.time.Clock()
    for glyphs, color in steps:
        draw_grid(screen, grid)
        px = x * (CHAR_WIDTH * SCALE_X * 2)
        py = y * (CHAR_HEIGHT * SCALE_Y)
        draw_text(screen, glyphs, px, py, color)
        pygame.display.flip()
        clock.tick(5)

############################################################
# 10) GAME OVER & COLLISION
############################################################
def game_over_screen(screen):
    screen.fill((0, 0, 0))
    msg = "Game Over"
    w = len(msg) * CHAR_WIDTH * SCALE_X
    h = CHAR_HEIGHT * SCALE_Y
    total_w = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    total_h = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + STATUS_HEIGHT
    x = (total_w - w) // 2
    y = (total_h - h) // 2
    draw_text(screen, msg, x, y, TEXT_COLOR_DEFAULT)
    pygame.display.flip()
    pygame.time.wait(3000)

def handle_collision(grid, screen):
    global lives, running_level_score, game_over_flag
    sounds['collision'].play()
    lives -= 1
    if lives <= 0:
        game_over_screen(screen)
        partial_time = (get_game_time() - last_sublevel_start_time)//1000 + last_sublevel_time_offset
        maybe_record_highscore(running_level_score, last_sublevel_name, screen, partial_time)
        game_over_flag = True
    else:
        respawn_player(grid, screen)

############################################################
# 11) PLAYER MOVEMENT
############################################################
def move_player_direction(grid, direction, stats, screen, explosive_enabled=False):
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid
    px, py = player_pos
    dx, dy = direction
    tx, ty = px + dx, py + dy
    t = cell_type(grid[ty][tx])
    if t == EMPTY:
        grid[py][px] = EMPTY
        grid[ty][tx] = PLAYER
    elif t == MOVEABLE_BLOCK:
        push_blocks_player(grid, (px, py), direction, stats, screen, explosive_enabled)
    elif t == UNMOVEABLE_BLOCK:
        if explosive_enabled:
            handle_collision(grid, screen)
    elif t in (HUNTER, PUSHER, SENTINEL):
        handle_collision(grid, screen)
    return grid

def push_blocks_player(grid, start_pos, direction, stats, screen, explosive_enabled=False):
    x, y = start_pos
    dx, dy = direction
    chain = []
    cx, cy = x + dx, y + dy
    while cell_type(grid[cy][cx]) == MOVEABLE_BLOCK:
        chain.append((cx, cy))
        cx += dx
        cy += dy

    occupant_t = cell_type(grid[cy][cx])
    if occupant_t == EMPTY:
        for bx, by in reversed(chain):
            grid[by+dy][bx+dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y+dy][x+dx] = PLAYER
        grid[y][x] = EMPTY

    elif occupant_t == UNMOVEABLE_BLOCK:
        if explosive_enabled:
            if chain:
                last_x, last_y = chain[-1]
                grid[last_y][last_x] = EMPTY
                for i in range(len(chain) - 2, -1, -1):
                    bx, by = chain[i]
                    grid[by+dy][bx+dx] = grid[by][bx]
                    grid[by][bx] = EMPTY
                grid[y+dy][x+dx] = PLAYER
                grid[y][x] = EMPTY
                if 'explosion' in sounds:
                    sounds['explosion'].play()
            else:
                handle_collision(grid, screen)
        else:
            return

    elif occupant_t == HUNTER:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK, EGG]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['hunters_killed'] = stats.get('hunters_killed', 0) + 1
            stats["score"] = stats.get("score", 0) + HUNTER_VALUE
            sounds['squish'].play()

    elif occupant_t == PUSHER:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['pushers_killed'] = stats.get('pushers_killed', 0) + 1
            stats["score"] = stats.get("score", 0) + PUSHER_VALUE
            sounds['squish'].play()

    elif occupant_t == SENTINEL:
        if chain:
            behind_x, behind_y = cx + dx, cy + dy
            if (0 <= behind_x < GRID_WIDTH and 0 <= behind_y < GRID_HEIGHT):
                if cell_type(grid[behind_y][behind_x]) == UNMOVEABLE_BLOCK:
                    for bx, by in reversed(chain):
                        grid[by+dy][bx+dx] = grid[by][bx]
                        grid[by][bx] = EMPTY
                    grid[y+dy][x+dx] = PLAYER
                    grid[y][x] = EMPTY
                    stats['sentinels_killed'] = stats.get('sentinels_killed', 0) + 1
                    stats["score"] = stats.get("score", 0) + SENTINEL_VALUE
                    sounds['squish'].play()
                else:
                    return
            else:
                return
        else:
            return

    elif occupant_t == EGG:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['eggs_destroyed'] = stats.get('eggs_destroyed', 0) + 1
            stats["score"] = stats.get("score", 0) + EGG_VALUE
            sounds['squish'].play()

############################################################
# 12) UPDATE EGGS, ENEMIES, AND PATHFINDING
############################################################
def update_eggs(grid):
    now = get_game_time()
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            c = grid[y][x]
            if cell_type(c) == EGG:
                egg_total_time = c[1]
                egg_start = c[2]
                if now - egg_start >= egg_total_time:
                    grid[y][x] = PUSHER
    return grid

def a_star_path_for_enemy(grid, start, goal):
    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    directions = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    while open_set:
        _, current = heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        cx, cy = current
        for (dx, dy) in directions:
            nx, ny = cx+dx, cy+dy
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                continue
            t = cell_type(grid[ny][nx])
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, HUNTER, PUSHER, SENTINEL, EGG):
                continue
            cost = g_score[current] + 1
            if (nx, ny) not in g_score or cost < g_score[(nx, ny)]:
                g_score[(nx, ny)] = cost
                f_val = cost + heuristic((nx, ny), goal)
                came_from[(nx, ny)] = current
                heappush(open_set, (f_val, (nx, ny)))
    return None

def update_hunters(grid, hunter_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return
    hunters_positions = [
        (x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
        if cell_type(grid[y][x]) == HUNTER
    ]
    collision_occurred = False
    for (ex, ey) in hunters_positions:
        if collision_occurred:
            break
        if cell_type(grid[ey][ex]) != HUNTER:
            continue
        path = a_star_path_for_enemy(grid, (ex, ey), player_pos)
        moved = False
        if path and len(path) > 1 and random.random() < (hunter_accuracy / 100.0):
            nx, ny = path[1]
            t = cell_type(grid[ny][nx])
            if t == PLAYER:
                handle_collision(grid, screen)
                collision_occurred = True
                continue
            elif t == EMPTY:
                grid[ny][nx] = HUNTER
                grid[ey][ex] = EMPTY
                moved = True
        if not moved:
            possible_moves = [
                (0,1),(0,-1),(1,0),(-1,0),
                (1,1),(1,-1),(-1,1),(-1,-1)
            ]
            mv = random.choice(possible_moves)
            nx, ny = ex + mv[0], ey + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t == EMPTY:
                    grid[ny][nx] = HUNTER
                    grid[ey][ex] = EMPTY

def update_sentinels(grid, sentinel_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return
    sentinel_positions = [
        (x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
        if cell_type(grid[y][x]) == SENTINEL
    ]
    collision_occurred = False
    for (sx, sy) in sentinel_positions:
        if collision_occurred:
            break
        if cell_type(grid[sy][sx]) != SENTINEL:
            continue
        path = a_star_path_for_enemy(grid, (sx, sy), player_pos)
        moved = False
        if path and len(path) > 1 and random.random() < (sentinel_accuracy / 100.0):
            nx, ny = path[1]
            t = cell_type(grid[ny][nx])
            if t == PLAYER:
                handle_collision(grid, screen)
                collision_occurred = True
                continue
            elif t == EMPTY:
                grid[ny][nx] = SENTINEL
                grid[sy][sx] = EMPTY
                moved = True
        if not moved:
            possible_moves = [
                (0,1),(0,-1),(1,0),(-1,0),
                (1,1),(1,-1),(-1,1),(-1,-1)
            ]
            mv = random.choice(possible_moves)
            nx, ny = sx + mv[0], sy + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t == EMPTY:
                    grid[ny][nx] = SENTINEL
                    grid[sy][sx] = EMPTY

def a_star_path_for_pusher(grid, start, goal):
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    gx, gy = goal
    while open_set:
        _, current = heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        cx, cy = current
        for (dx, dy) in [(0,1),(0,-1),(1,0),(-1,0)]:
            nx, ny = cx+dx, cy+dy
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                continue
            t = cell_type(grid[ny][nx])
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, HUNTER, PUSHER, SENTINEL, EGG):
                continue
            cost = g_score[current] + 1
            if (nx, ny) not in g_score or cost < g_score[(nx, ny)]:
                g_score[(nx, ny)] = cost
                f_val = cost + heuristic((nx, ny), (gx, gy))
                came_from[(nx, ny)] = current
                heappush(open_set, (f_val, (nx, ny)))
    return None

def pusher_push_blocks(grid, start_pos, dx, dy, screen):
    x, y = start_pos
    nx, ny = x + dx, y + dy
    if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
        return False
    occupant_t = cell_type(grid[ny][nx])
    if occupant_t == PLAYER:
        handle_collision(grid, screen)
        return True
    elif occupant_t == EMPTY:
        grid[ny][nx] = PUSHER
        grid[y][x] = EMPTY
        return True
    elif occupant_t == MOVEABLE_BLOCK:
        chain = []
        cx, cy = nx, ny
        while cell_type(grid[cy][cx]) == MOVEABLE_BLOCK:
            chain.append((cx, cy))
            cx += dx
            cy += dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                return False
        final_t = cell_type(grid[cy][cx])
        if final_t == EMPTY:
            for (bx, by) in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y][x] = EMPTY
            grid[ny][nx] = PUSHER
            return True
        else:
            return False
    else:
        # occupant is an enemy or unmoveable => do not overwrite
        return False

def update_pushers(grid, pusher_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return
    px_player, py_player = player_pos
    pushers = [(x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if cell_type(grid[y][x]) == PUSHER]
    for (px, py) in pushers:
        if cell_type(grid[py][px]) != PUSHER:
            continue
        if random.random() > (pusher_accuracy / 100.0):
            do_pusher_random(grid, (px, py), screen)
            continue
        dx, dy = 0, 0
        if abs(px_player - px) > abs(py_player - py):
            dx = -1 if px_player < px else (1 if px_player > px else 0)
        else:
            dy = -1 if py_player < py else (1 if py_player > py else 0)
        if (dx, dy) != (0, 0):
            if pusher_push_blocks(grid, (px, py), dx, dy, screen):
                continue
            else:
                path = a_star_path_for_pusher(grid, (px, py), (px_player, py_player))
                if path and len(path) > 1:
                    nx, ny = path[1]
                    ddx, ddy = nx - px, ny - py
                    if not pusher_push_blocks(grid, (px, py), ddx, ddy, screen):
                        do_pusher_random(grid, (px, py), screen)
                else:
                    do_pusher_random(grid, (px, py), screen)
        else:
            do_pusher_random(grid, (px, py), screen)

def do_pusher_random(grid, pos, screen):
    px, py = pos
    directions = [(0,1),(0,-1),(1,0),(-1,0)]
    random.shuffle(directions)
    for (dx, dy) in directions:
        if pusher_push_blocks(grid, (px, py), dx, dy, screen):
            break

############################################################
# 15) LEVELS LOADING / DEFINITION
############################################################
def load_levels_json(filename="levels.json"):
    global levels_data
    path = resource_path(filename)
    if not os.path.exists(path):
        print(f"ERROR: Cannot find {filename}. Using empty levels_data.")
        levels_data = []
        return
    with open(path, "r", encoding="utf-8") as f:
        levels_data = json.load(f)

def get_main_level_def(level_letter):
    for entry in levels_data:
        if entry.get("level") == level_letter:
            default = {
                "pull_blocks": False,
                "speed_up": False,
                "explosive_blocks": False,
                "winning_level": 1,
                "enemies": {}
            }
            default.update(entry)
            if "egg_incubation_ms" not in default or default["egg_incubation_ms"] == 0:
                egg_def = default.get("enemies", {}).get("egg", {})
                incubation_s = egg_def.get("incubation_s", 0)
                default["egg_incubation_ms"] = incubation_s * 1000
            return default
    return {
        "level": level_letter,
        "pull_blocks": False,
        "speed_up": False,
        "explosive_blocks": False,
        "winning_level": 1,
        "enemies": {},
        "egg_incubation_ms": 0
    }

############################################################
# LEVEL SELECTION & DETAILS SCREENS
############################################################
def level_selection_screen(screen, clock):
    global current_spritesheet
    levels = sorted({ entry.get("level") for entry in levels_data })
    if not levels:
        levels = ["A"]
    selected_index = 0

    while True:
        screen.fill((0, 0, 0))
        
        draw_text(screen, "\xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDB\xDB   \xDB\xDB \xDE\xDB\xDB\xDD \xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDB\xDB   \xDB\xDB", 19*16, 2*32, PLAYER_COLOR)
        draw_text(screen, "\xDB\xDB\xDC\xDC\xDC\xDC  \xDB\xDB   \xDB\xDB \xDB\xDB   \xDB\xDB  \xDB\xDB  \xDB\xDB\xDC\xDC\xDC\xDC  \xDB\xDB\xDC\xDC\xDC\xDB\xDB", 19*16, 3*32, HIGHLIGHT_COLOR)
        draw_text(screen, " \xDF\xDF\xDF\xDF\xDB\xDB \xDB\xDB \xDF\xDC\xDB\xDB \xDB\xDB   \xDB\xDB  \xDB\xDB   \xDF\xDF\xDF\xDF\xDB\xDB \xDB\xDB\xDF\xDF\xDF\xDB\xDB", 19*16, 4*32, EGG_COLOR_0)
        draw_text(screen, "\xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDF\xDB\xDB\xDB\xDB\xDF\xDC \xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDE\xDB\xDB\xDD \xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDB\xDB   \xDB\xDB", 19*16, 5*32, EGG_COLOR_1)
        
        level_y = 256 
        x = 128
        for idx, lvl in enumerate(levels):
            color = HIGHLIGHT_COLOR if idx == selected_index else TEXT_COLOR_DEFAULT
            draw_text(screen, lvl, x, level_y, color)
            x += 40

        prompt = "Arrow keys: select  \xB3  ENTER: start  \xB3  H: high scores  \xB3  ESC: quit"
        draw_text(screen, prompt, 6*16, screen.get_height() - 32, TEXT_COLOR_DEFAULT)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == K_h:
                    high_score_screen(screen, clock)
                elif event.key == K_LEFT:
                    selected_index = (selected_index - 1) % len(levels)
                elif event.key == K_RIGHT:
                    selected_index = (selected_index + 1) % len(levels)
                elif event.key == K_RETURN:
                    return levels[selected_index]
                elif event.key == K_a:
                    # Toggle spritesheet
                    if current_spritesheet == "dos_spritesheet.png":
                        current_spritesheet = "st_spritesheet.png"
                    else:
                        current_spritesheet = "dos_spritesheet.png"
                    load_sprite_sheet(current_spritesheet)
        clock.tick(15)

def show_level_details_screen(screen, clock, level_def):
    lvl = level_def.get("level")
    winning_level = level_def.get("winning_level", 1)
    pull_blocks = level_def.get("pull_blocks", False)
    speed_up = level_def.get("speed_up", False)
    explosive_blocks = level_def.get("explosive_blocks", False)
    enemies = level_def.get("enemies", {})
    enemy_lines = []
    for enemy_type, data in enemies.items():
        count = data.get("count", 0)
        if enemy_type.lower() == "hunter":
            mutation_ratio = data.get("mutation_ratio", 0)
            mutates_into = data.get("mutates_into")
            if mutation_ratio > 0 and mutates_into:
                mut_count = int(round(count * mutation_ratio))
                enemy_lines.append(f"- {count} hunters ({mut_count}/{count} will mutate into {mutates_into.capitalize()}s)")
            else:
                enemy_lines.append(f"- {count} hunters")
        elif enemy_type.lower() == "egg":
            hatches_into = data.get("hatches_into")
            if hatches_into:
                enemy_lines.append(f"- {count} eggs (will hatch into {hatches_into.capitalize()}s)")
            else:
                enemy_lines.append(f"- {count} eggs")
        else:
            enemy_lines.append(f"- {count} {enemy_type}s")

    details = [
        f"Level {lvl}",
        "",
        f"Winning level:      {winning_level}",
        f"Pull blocks:        {'Yes' if pull_blocks else 'No'}",
        f"Game speed up:      {'Yes' if speed_up else 'No'}",
        f"Explosive blocks:   {'Yes' if explosive_blocks else 'No'}",
        "",
        "Enemies:"
    ] + enemy_lines + [
        "",
        "Press SPACE to start, or ESC to go back"
    ]
    while True:
        screen.fill((0, 0, 0))
        y = 50
        for line in details:
            draw_text(screen, line, 50, y, TEXT_COLOR_DEFAULT)
            y += CHAR_HEIGHT * SCALE_Y + 10
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    return True
                elif event.key == K_ESCAPE:
                    return False
        clock.tick(15)

############################################################
# NEW: PLAY A MAIN LEVEL (with sublevels)
############################################################
def play_main_level(level_def, screen, clock, cumulative_score, cumulative_time):
    global lives, game_over_flag
    running_level_score = 0
    total_moves = 0
    total_enemies = 0
    level_time = 0
    total_sublevels = level_def.get("winning_level", 1)
    for sublevel in range(1, total_sublevels + 1):
        if sublevel > 1:
            if level_def.get("enemies", {}).get("hunter", {}).get("count", 0) > 0:
                running_level_score += 2 * HUNTER_VALUE
            if level_def.get("enemies", {}).get("egg", {}).get("count", 0) > 0:
                running_level_score += 1 * EGG_VALUE
        sub_time_offset = cumulative_time + level_time
        result = play_sublevel(level_def, sublevel, screen, clock, running_level_score, sub_time_offset)
        if result is None:
            # means user quit mid-level
            lives = 3
            game_over_flag = False
            return None
        moves, enemies_eliminated, time_taken, sublevel_score, level_name = result
        running_level_score = sublevel_score
        total_moves += moves
        total_enemies += enemies_eliminated
        level_time += time_taken
        pygame.mixer.Sound(resource_path("sound/sublevel.mp3")).play()

    pygame.mixer.Sound(resource_path("sound/level.mp3")).play()
    show_level_complete_screen(screen, level_def.get("level"), total_moves, total_enemies, level_time, running_level_score)
    cumulative_time += level_time
    return total_moves, total_enemies, level_time, running_level_score, level_def.get("level"), cumulative_time

def play_sublevel(level_def, sublevel, screen, clock, initial_sublevel_score, time_offset):
    global current_level, running_level_score
    global last_sublevel_name, last_sublevel_start_time, last_sublevel_time_offset

    enemies_def = level_def.get("enemies", {})
    h_speed = enemies_def.get("hunter", {}).get("speed_ms", 1000)
    h_acc   = enemies_def.get("hunter", {}).get("accuracy", 50)
    p_speed = enemies_def.get("pusher", {}).get("speed_ms", 1000)
    p_acc   = enemies_def.get("pusher", {}).get("accuracy", 50)
    s_speed = enemies_def.get("sentinel", {}).get("speed_ms", 1000)
    s_acc   = enemies_def.get("sentinel", {}).get("accuracy", 50)

    current_level = sublevel
    level_name = f"{level_def.get('level')}{sublevel}"
    last_sublevel_name = level_name
    last_sublevel_start_time = get_game_time()
    last_sublevel_time_offset = time_offset

    running_score = initial_sublevel_score
    grid = generate_level(level_def, sublevel)
    place_player_best_spot(grid, screen)
    draw_status_line.initial_egg_count = sum(1 for row in grid for c in row if cell_type(c) == EGG)
    stats = {
        'moves': 0,
        'eggs_destroyed': 0,
        'hunters_killed': 0,
        'pushers_killed': 0,
        'sentinels_killed': 0,
        'score': running_score
    }

    explosive_enabled = level_def.get("explosive_blocks", False)

    level_start_time = get_game_time()
    last_hunter_update = level_start_time
    last_pusher_update = level_start_time
    last_sentinel_update = level_start_time

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pause_duration = pause_game(screen)
                    if pause_duration == -1:
                        return None
                    level_start_time += max(0, pause_duration)
                elif event.key in (K_q, ord('q')):
                    if quit_confirm(screen):
                        return None
                elif event.key in (K_UP, K_DOWN, K_LEFT, K_RIGHT):
                    old_pos = get_player_position(grid)
                    if event.key == K_UP:
                        move_player_direction(grid, (0, -1), stats, screen, explosive_enabled)
                    elif event.key == K_DOWN:
                        move_player_direction(grid, (0, 1), stats, screen, explosive_enabled)
                    elif event.key == K_LEFT:
                        move_player_direction(grid, (-1, 0), stats, screen, explosive_enabled)
                    elif event.key == K_RIGHT:
                        move_player_direction(grid, (1, 0), stats, screen, explosive_enabled)
                    new_pos = get_player_position(grid)
                    if old_pos != new_pos:
                        stats['moves'] += 1
                        running_score = stats["score"]

        if game_over_flag:
            return None

        current_time = get_game_time()
        if current_time - last_hunter_update >= h_speed:
            update_hunters(grid, h_acc, screen)
            last_hunter_update = current_time
        if current_time - last_pusher_update >= p_speed:
            update_pushers(grid, p_acc, screen)
            last_pusher_update = current_time
        if current_time - last_sentinel_update >= s_speed:
            update_sentinels(grid, s_acc, screen)
            last_sentinel_update = current_time

        update_eggs(grid)
        draw_grid(screen, grid)
        draw_status_line(screen, grid, level_start_time, lives, level_name, stats["score"], time_offset)
        pygame.display.flip()
        clock.tick(10)

        any_enemies = any(cell_type(c) in [HUNTER, PUSHER, SENTINEL, EGG] for row in grid for c in row)
        if not any_enemies:
            break

    level_end_time = get_game_time()
    time_taken = max(0, (level_end_time - level_start_time)//1000)
    total_sublevels = level_def.get("winning_level", 1)
    bonus = (4 * math.floor(total_sublevels / 3) + 5) + 4 * (sublevel - 1)
    stats["score"] += bonus
    running_score = stats["score"]

    return stats['moves'], (stats['hunters_killed'] + stats['pushers_killed'] + stats['sentinels_killed']), time_taken, stats["score"], level_name

def show_level_complete_screen(screen, level_letter, moves, enemies_eliminated, time_taken, level_score):
    screen.fill((0, 0, 0))
    lines = [
        f"Level {level_letter} Completed!",
        "",
        f"Total Enemies Eliminated: {enemies_eliminated}",
        f"Total Moves Taken: {moves}",
        f"Total Time: {time_taken} seconds",
        f"Score: {level_score}",
        "Press <space> to return to level selection"
    ]
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    y = 100
    for line in lines:
        lw = len(line) * CHAR_WIDTH * SCALE_X
        x = (total_width - lw) // 2
        draw_text(screen, line, x, y, TEXT_COLOR_DEFAULT)
        y += CHAR_HEIGHT * SCALE_Y + 10
    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    waiting = False
                elif event.key == K_ESCAPE:
                    pygame.quit(); sys.exit()
        pygame.time.Clock().tick(15)

############################################################
# 16) GENERATE LEVEL
############################################################
def generate_level(info, sublevel):
    enemies = info.get("enemies", {})
    base_h_count = enemies.get("hunter", {}).get("count", 0)
    base_e_count = enemies.get("egg", {}).get("count", 0)
    if base_h_count > 0:
        h_count = base_h_count + 2 * (sublevel - 1)
    else:
        h_count = 0
    if base_e_count > 0:
        e_count = base_e_count + (sublevel - 1)
    else:
        e_count = 0
    p_count = enemies.get("pusher", {}).get("count", 0)
    s_count = enemies.get("sentinel", {}).get("count", 0)
    
    # Hunter mutation
    hunter_def = enemies.get("hunter", {})
    mutation_ratio = hunter_def.get("mutation_ratio", 0)
    mutated = int(h_count * mutation_ratio)
    actual_h_count = h_count - mutated
    s_count += mutated

    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    for x in range(GRID_WIDTH):
        grid[0][x] = UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT-1][x] = UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0] = UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH-1] = UNMOVEABLE_BLOCK
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            r = random.random()
            if r < 0.01:
                grid[y][x] = UNMOVEABLE_BLOCK
            elif r < 0.31:
                block_index = random.choice([0, 1, 2])
                grid[y][x] = (MOVEABLE_BLOCK, block_index)

    placed_hunters = 0
    while placed_hunters < actual_h_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = HUNTER
            placed_hunters += 1

    placed_pushers = 0
    while placed_pushers < p_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = PUSHER
            placed_pushers += 1

    placed_sentinels = 0
    while placed_sentinels < s_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = SENTINEL
            placed_sentinels += 1

    now = get_game_time()
    egg_positions = []
    while len(egg_positions) < e_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            factor = 0.9 + 0.2 * random.random()
            hatch_time = int(info.get("egg_incubation_ms", 0) * factor)
            grid[ry][rx] = (EGG, hatch_time, now)
            egg_positions.append((rx, ry))
    return grid

############################################################
# MAIN LOOP
############################################################
def main():
    global lives, cumulative_time, global_pause_offset, current_spritesheet
    pygame.init()
    screen_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    screen_height = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + STATUS_HEIGHT
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()

    load_sprite_sheet(current_spritesheet)

    sounds['squish'] = pygame.mixer.Sound(resource_path("sound/squish.mp3"))
    sounds['collision'] = pygame.mixer.Sound(resource_path("sound/collision.mp3"))

    load_levels_json("levels.json")

    while True:
        level_score = 0
        cumulative_time = 0
        lives = 3
        selected_level_letter = level_selection_screen(screen, clock)
        level_def = get_main_level_def(selected_level_letter)
        if show_level_details_screen(screen, clock, level_def):
            result = play_main_level(level_def, screen, clock, 0, 0)
            if result is not None:
                moves, enemies_eliminated, level_time, level_score, lvl, cumulative_time = result
                maybe_record_highscore(level_score, lvl, screen, cumulative_time)

if __name__ == "__main__":
    main()
