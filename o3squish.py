#############################################################
##                                                         ##
##  S Q U I S H  v3.6.0  (Enemies blocked by each other,   ##
##                        sentinels = 6×level)             ##
##                                                         ##
##  - No enemy can move onto another enemy's cell.         ##
##  - Sentinel kills = 6×level.                            ##
##  - Eggs => pushers, simpler pusher logic.               ##
##  - Everything else (hunters, scoreboard, collisions,    ##
##    etc.) is retained.                                   ##
#############################################################

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame
import random
import sys
import datetime
import json
from pygame.locals import *
from heapq import heappush, heappop
from collections import deque

# -----------------------------------------------------------
# 1) BASIC CONFIGURATION
# -----------------------------------------------------------
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4        # "Hunter"
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

# Scoring approach:
#  - Egg => 1×level
#  - Hunter => 2×level
#  - Pusher => 3×level
#  - Sentinel => 6×level

# -----------------------------------------------------------
# 2) COLOR DEFINITIONS
# -----------------------------------------------------------
PLAYER_COLOR       = (0x59, 0xe1, 0xe3)
WALL_COLOR         = (0xff, 0xea, 0x16)
HUNTER_COLOR       = (0xff, 0x16, 0xb0)
BLOCK_COLOR        = (0xee, 0xee, 0xee)
TEXT_COLOR_DEFAULT = (0xee, 0xee, 0xee)
STATUS_BG_COLOR    = (0x00, 0x00, 0x00)
STATUS_FG_COLOR    = (0xee, 0xee, 0xee)

EGG_COLOR_0        = (0xfa, 0xe9, 0x01)
EGG_COLOR_1        = (0xfa, 0x82, 0x01)
EGG_COLOR_FLASH1   = (0xfa, 0x01, 0x01)
EGG_COLOR_FLASH2   = (0xff, 0xff, 0xff)

PUSHER_COLOR       = (0x99, 0x35, 0xff)
SENTINEL_COLOR     = (0x47, 0x52, 0xcb)  # #4752cb

# -----------------------------------------------------------
# 3) GLOBAL RESOURCES
# -----------------------------------------------------------
sprite_sheet = None
sounds = {}
lives = 3
current_level = 0
current_score = 0

levels_data = []

# -----------------------------------------------------------
# 4) HELPER FUNCTIONS
# -----------------------------------------------------------
def cell_type(cell):
    if isinstance(cell, tuple):
        return cell[0]
    return cell

def tint_surface(surface, tint_color):
    tinted = surface.copy()
    tinted.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)
    return tinted

def get_egg_color(cell):
    now = pygame.time.get_ticks()
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
    elif t == ENEMY:
        return HUNTER_COLOR
    elif t == EGG:
        return get_egg_color(cell)
    elif t == PUSHER:
        return PUSHER_COLOR
    elif t == SENTINEL:
        return SENTINEL_COLOR
    return (0, 0, 0)

# -----------------------------------------------------------
# 5a) HIGH SCORE HANDLING
# -----------------------------------------------------------
SCORE_FILE = "highscores.dat"

def encrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return bytes(b ^ key for b in data)

def decrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return encrypt_xor(data, key)

def load_highscores() -> list:
    if not os.path.exists(SCORE_FILE):
        return []
    try:
        with open(SCORE_FILE, "rb") as f:
            encrypted = f.read()
        decrypted = decrypt_xor(encrypted, 0xAA).decode("utf-8", errors="ignore")
        lines = decrypted.strip().split("\n")
        scores = []
        for line in lines:
            parts = line.split("|")
            if len(parts) == 4:
                dt_str, lvl_str, scr_str, name_str = parts
                scores.append((int(scr_str), dt_str, int(lvl_str), name_str))
        scores.sort(key=lambda s: s[0], reverse=True)
        return scores
    except:
        return []

def save_highscores(scores: list):
    scores = sorted(scores, key=lambda s: s[0], reverse=True)[:20]
    lines = [f"{dt}|{lvl}|{scr}|{name}" for (scr, dt, lvl, name) in scores]
    data = "\n".join(lines)
    encrypted = encrypt_xor(data.encode("utf-8"), 0xAA)
    with open(SCORE_FILE, "wb") as f:
        f.write(encrypted)

def ask_player_name() -> str:
    name = ""
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    while True:
        for evt in pygame.event.get():
            if evt.type == QUIT:
                pygame.quit()
                sys.exit()
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

def show_highscores_screen(scores, screen):
    scores = sorted(scores, key=lambda s: s[0], reverse=True)[:20]
    screen.fill((0, 0, 0))

    title = "=== TOP 20 HIGH SCORES ==="
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    y = 50
    lw = len(title) * CHAR_WIDTH * SCALE_X
    x = (total_width - lw) // 2
    draw_text(screen, title, x, y, TEXT_COLOR_DEFAULT)
    y += 50

    headers = f"{'NAME':<15} {'DATE':<19} {'LVL':<4} {'SCORE':>6}"
    lw = len(headers) * CHAR_WIDTH * SCALE_X
    x = (total_width - lw) // 2
    draw_text(screen, headers, x, y, TEXT_COLOR_DEFAULT)
    y += 30

    for (scr, dt_str, lvl, name_str) in scores:
        line = f"{name_str:<15} {dt_str:<19} {lvl:<4} {scr:>6}"
        lw = len(line) * CHAR_WIDTH * SCALE_X
        x = (total_width - lw) // 2
        draw_text(screen, line, x, y, TEXT_COLOR_DEFAULT)
        y += 25

    pygame.display.flip()
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                waiting = False
        clock.tick(15)

def maybe_record_highscore(total_score: int, level: int, screen):
    scores = load_highscores()
    if len(scores) < 20 or total_score > scores[-1][0]:
        name = ask_player_name()
        dt_str = datetime.datetime.now().isoformat(timespec="seconds")
        scores.append((total_score, dt_str, level, name))
        save_highscores(scores)
        show_highscores_screen(scores, screen)

# -----------------------------------------------------------
# 5b) PAUSE AND QUIT CONFIRMATION
# -----------------------------------------------------------
def pause_game(screen):
    paused = True
    clock = pygame.time.Clock()
    while paused:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key in (K_q, ord('q')):
                    if quit_confirm(screen):
                        maybe_record_highscore(current_score, current_level, screen)
                        pygame.quit()
                        sys.exit()
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

def quit_confirm(screen) -> bool:
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
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

# -----------------------------------------------------------
# 6c) SPRITE-SHEET TEXT RENDERING
# -----------------------------------------------------------
def load_sprite_sheet(filename):
    global sprite_sheet
    sprite_sheet = pygame.image.load(filename).convert_alpha()

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

# -----------------------------------------------------------
# 7) ENTITY MAPPINGS
# -----------------------------------------------------------
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
    elif t == ENEMY:
        return HUNTER_CHARS
    elif t == EGG:
        return EGG_CHARS
    elif t == PUSHER:
        return PUSHER_CHARS
    elif t == SENTINEL:
        return SENTINEL_CHARS
    else:
        return "??"

# -----------------------------------------------------------
# 8) DRAWING THE GRID & STATUS
# -----------------------------------------------------------
def draw_grid(screen, grid):
    screen.fill((0, 0, 0))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            color = get_cell_color(grid[y][x])
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, total_enemies):
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    pygame.draw.rect(screen, STATUS_BG_COLOR, (0, GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y), total_width, STATUS_HEIGHT))
    elapsed = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"

    current_enemies = sum(1 for row in grid for c in row if cell_type(c) in [ENEMY, PUSHER, SENTINEL])
    approx_score = (total_enemies - current_enemies) * (2 * level)
    sep = chr(0xB3)
    status_text = (f"Enemies: {current_enemies}  {sep}  Time: {time_str}  {sep}  "
                   f"Lives: {lives}  {sep}  Score: {approx_score} ({cumulative_score})")
    text_x = 5
    text_y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + (STATUS_HEIGHT - CHAR_HEIGHT * SCALE_Y) // 2
    draw_text(screen, status_text, text_x, text_y, STATUS_FG_COLOR)

# -----------------------------------------------------------
# 9) PLAYER SPAWN LOGIC & ANIMATION
# -----------------------------------------------------------
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
            if t in [ENEMY, PUSHER, SENTINEL]:
                enemies.append((x, y))
            elif t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK):
                blocks.append((x, y))

    best_enemy_dist = -1
    best_block_dist = -1
    best_edge_dist  = -1
    best_pos = None

    for yy in range(1, GRID_HEIGHT - 1):
        for xx in range(1, GRID_WIDTH - 1):
            if cell_type(grid[yy][xx]) == EMPTY:
                if enemies:
                    enemy_dist = min(abs(xx - ex) + abs(yy - ey) for ex, ey in enemies)
                else:
                    enemy_dist = 999
                if blocks:
                    block_dist = min(abs(xx - bx) + abs(yy - by) for bx, by in blocks)
                else:
                    block_dist = 999
                dist_edge = min(xx - 1, (GRID_WIDTH - 2) - xx, yy - 1, (GRID_HEIGHT - 2) - yy)

                if (enemy_dist > best_enemy_dist
                    or (enemy_dist == best_enemy_dist and block_dist > best_block_dist)
                    or (enemy_dist == best_enemy_dist and block_dist == best_block_dist and dist_edge > best_edge_dist)):
                    best_enemy_dist = enemy_dist
                    best_block_dist = block_dist
                    best_edge_dist  = dist_edge
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
        ("--", (0xff, 0x00, 0x00)),
        ("←→", (0xff, 0x99, 0x00)),
        ("«»", (0xff, 0xff, 0x00)),
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

# -----------------------------------------------------------
# 10) GAME OVER & COLLISION
# -----------------------------------------------------------
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
    global lives, current_score, current_level
    sounds['collision'].play()
    lives -= 1
    if lives <= 0:
        maybe_record_highscore(current_score, current_level, screen)
        game_over_screen(screen)
        pygame.quit()
        sys.exit()
    else:
        respawn_player(grid, screen)

# -----------------------------------------------------------
# 11) PLAYER MOVEMENT
# -----------------------------------------------------------
def move_player_direction(grid, direction, stats, screen):
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
        push_blocks_player(grid, (px, py), direction, stats, screen)
    elif t in (ENEMY, EGG, PUSHER, SENTINEL):
        handle_collision(grid, screen)
    return grid

def push_blocks_player(grid, start_pos, direction, stats, screen):
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

    elif occupant_t == ENEMY:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['hunters_killed'] += 1
            sounds['squish'].play()

    elif occupant_t == EGG:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['eggs_destroyed'] += 1
            sounds['squish'].play()

    elif occupant_t == PUSHER:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['pushers_killed'] += 1
            sounds['squish'].play()

    elif occupant_t == SENTINEL:
        # pinned only if behind is UNMOVEABLE_BLOCK
        nx, ny = cx + dx, cy + dy
        behind_t = cell_type(grid[ny][nx])
        if behind_t == UNMOVEABLE_BLOCK:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            # We'll track sentinel kills in a new stat for scoring
            stats.setdefault('sentinels_killed', 0)
            stats['sentinels_killed'] += 1
            sounds['squish'].play()

# -----------------------------------------------------------
# 12) EGG UPDATE => hatch into pushers
# -----------------------------------------------------------
def update_eggs(grid):
    now = pygame.time.get_ticks()
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            c = grid[y][x]
            if cell_type(c) == EGG:
                egg_total_time = c[1]
                egg_start = c[2]
                if now - egg_start >= egg_total_time:
                    # Hatch => pusher
                    grid[y][x] = PUSHER
    return grid

# -----------------------------------------------------------
# 13) HUNTERS & SENTINELS (no crossing each other)
# -----------------------------------------------------------
def a_star_path_for_enemy(grid, start, goal):
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = { start: 0 }

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
            # They can't move over unmoveable or moveable blocks,
            # nor can they move over any other enemies (ENEMY, PUSHER, SENTINEL).
            # They can only move into EMPTY, EGG, or PLAYER cells.
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, ENEMY, PUSHER, SENTINEL):
                # blocked
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
    hunters_positions = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                hunters_positions.append((x, y))

    collision_occurred = False
    for (ex, ey) in hunters_positions:
        if collision_occurred:
            break
        if cell_type(grid[ey][ex]) != ENEMY:
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
            elif t in (EMPTY, EGG, PLAYER):
                grid[ny][nx] = ENEMY
                grid[ey][ex] = EMPTY
                moved = True
        if not moved:
            mv = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
            nx = ex + mv[0]
            ny = ey + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                # can't move onto ENEMY, PUSHER, or SENTINEL
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t in (EMPTY, EGG, PLAYER):
                    grid[ny][nx] = ENEMY
                    grid[ey][ex] = EMPTY

def update_sentinels(grid, sentinel_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return
    sentinel_positions = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == SENTINEL:
                sentinel_positions.append((x, y))

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
            elif t in (EMPTY, EGG, PLAYER):
                grid[ny][nx] = SENTINEL
                grid[sy][sx] = EMPTY
                moved = True
        if not moved:
            mv = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
            nx, ny = sx + mv[0], sy + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t in (EMPTY, EGG, PLAYER):
                    grid[ny][nx] = SENTINEL
                    grid[sy][sx] = EMPTY

# -----------------------------------------------------------
# 14) PUSHER LOGIC (Simpler approach, no crossing other enemies)
# -----------------------------------------------------------
def a_star_path_for_pusher(grid, start, goal):
    """
    4-dir path ignoring pushing, can't cross blocks or enemies.
    """
    def heuristic(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = { start: 0 }
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
            # cannot pass unmoveable/moveable or any enemy
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, ENEMY, PUSHER, SENTINEL):
                continue
            cost = g_score[current] + 1
            if (nx, ny) not in g_score or cost < g_score[(nx, ny)]:
                g_score[(nx, ny)] = cost
                f_val = cost + heuristic((nx, ny), (gx, gy))
                came_from[(nx, ny)] = current
                heappush(open_set, (f_val, (nx, ny)))
    return None

def pusher_push_blocks(grid, start_pos, dx, dy, screen):
    """
    Attempt to move or push occupant from pusher at start_pos in direction dx, dy.
    If occupant is the player's cell => direct collision => handle_collision.
    """
    x, y = start_pos
    nx, ny = x + dx, y + dy
    if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
        return False

    occupant_t = cell_type(grid[ny][nx])

    # If occupant is player => direct collision
    if occupant_t == PLAYER:
        handle_collision(grid, screen)
        if cell_type(grid[ny][nx]) != PUSHER:
            grid[y][x] = EMPTY
            grid[ny][nx] = PUSHER
        return True

    if occupant_t == EMPTY:
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
        elif final_t in (PLAYER, EGG, ENEMY, PUSHER, SENTINEL):
            # pinned occupant check
            bx2, by2 = cx+dx, cy+dy
            if not (0 <= bx2 < GRID_WIDTH and 0 <= by2 < GRID_HEIGHT):
                return False
            behind_t = cell_type(grid[by2][bx2])
            if behind_t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK):
                grid[cy][cx] = EMPTY
                for (bx, by) in reversed(chain):
                    grid[by+dy][bx+dx] = grid[by][bx]
                    grid[by][bx] = EMPTY
                grid[y][x] = EMPTY
                grid[ny][nx] = PUSHER
                return True
            else:
                return False
        else:
            return False
    elif occupant_t == PLAYER:
        handle_collision(grid, screen)
        if cell_type(grid[ny][nx]) != PUSHER:
            grid[y][x] = EMPTY
            grid[ny][nx] = PUSHER
        return True
    elif occupant_t in (EGG, ENEMY, PUSHER, SENTINEL):
        # pinned occupant check
        bx2, by2 = nx+dx, ny+dy
        if not (0 <= bx2 < GRID_WIDTH and 0 <= by2 < GRID_HEIGHT):
            return False
        behind_t = cell_type(grid[by2][bx2])
        if behind_t in (MOVEABLE_BLOCK, UNMOVEABLE_BLOCK):
            grid[ny][nx] = EMPTY
            grid[y][x] = EMPTY
            grid[ny][nx] = PUSHER
            return True
        else:
            return False
    else:
        return False

def update_pushers(grid, pusher_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return

    px_player, py_player = player_pos
    pushers = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PUSHER:
                pushers.append((x, y))

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

        if (dx, dy) != (0,0):
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

# -----------------------------------------------------------
# 15) LEVELS LOADING / EXTRAPOLATION
# -----------------------------------------------------------
def load_levels_json(filename="levels.json"):
    global levels_data
    if not os.path.exists(filename):
        print(f"ERROR: Cannot find {filename}. Using empty levels_data.")
        levels_data = []
        return
    with open(filename, "r", encoding="utf-8") as f:
        levels_data = json.load(f)

def get_level_def(level):
    if not levels_data:
        return {
            "hunter_count": 3, "hunter_speed_ms": 1000, "hunter_accuracy": 50,
            "pusher_count": 0, "pusher_speed_ms": 1000, "pusher_accuracy": 50,
            "sentinel_count": 0, "sentinel_speed_ms": 1000, "sentinel_accuracy": 50,
            "egg_count": 0, "egg_incubation_ms": 0
        }
    max_defined = levels_data[-1]["level"]
    if level <= max_defined:
        for entry in levels_data:
            if entry["level"] == level:
                return parse_level_entry(entry)
        return parse_level_entry(levels_data[0])
    else:
        if len(levels_data) >= 2:
            second_last = levels_data[-2]
            last = levels_data[-1]
            return extrapolate_level(level, second_last, last)
        else:
            return parse_level_entry(levels_data[-1])

def parse_level_entry(entry):
    enemies = entry.get("enemies", {})
    hunter   = enemies.get("hunter", {})
    pusher   = enemies.get("pusher", {})
    sentinel = enemies.get("sentinel", {})
    egg      = enemies.get("egg", {})

    h_count = hunter.get("count", 0)
    h_speed = hunter.get("speed_ms", 1000)
    h_acc   = hunter.get("accuracy", 50)
    h_var   = hunter.get("speed_variability", 0)

    p_count = pusher.get("count", 0)
    p_speed = pusher.get("speed_ms", 1000)
    p_acc   = pusher.get("accuracy", 50)
    p_var   = pusher.get("speed_variability", 0)

    s_count = sentinel.get("count", 0)
    s_speed = sentinel.get("speed_ms", 1000)
    s_acc   = sentinel.get("accuracy", 50)
    s_var   = sentinel.get("speed_variability", 0)

    e_count    = egg.get("count", 0)
    e_incub_s  = egg.get("incubation_s", 0)

    def clamp_speed(sp):
        return max(sp, 50)
    def clamp_accuracy(a):
        return min(a, 100)

    final_h_speed = clamp_speed(random.randint(h_speed - h_var, h_speed + h_var) if h_var > 0 else h_speed)
    final_p_speed = clamp_speed(random.randint(p_speed - p_var, p_speed + p_var) if p_var > 0 else p_speed)
    final_s_speed = clamp_speed(random.randint(s_speed - s_var, s_speed + s_var) if s_var > 0 else s_speed)

    return {
        "hunter_count": h_count,
        "hunter_speed_ms": final_h_speed,
        "hunter_accuracy": clamp_accuracy(h_acc),

        "pusher_count": p_count,
        "pusher_speed_ms": final_p_speed,
        "pusher_accuracy": clamp_accuracy(p_acc),

        "sentinel_count": s_count,
        "sentinel_speed_ms": final_s_speed,
        "sentinel_accuracy": clamp_accuracy(s_acc),

        "egg_count": e_count,
        "egg_incubation_ms": e_incub_s * 1000
    }

def extrapolate_level(level, second_last, last):
    L2 = parse_level_entry(second_last)
    L1 = parse_level_entry(last)

    def clamp_speed(sp):
        return max(sp, 50)
    def clamp_accuracy(a):
        return min(a, 100)

    diff_h_count = L1["hunter_count"] - L2["hunter_count"]
    diff_h_speed = L1["hunter_speed_ms"] - L2["hunter_speed_ms"]
    diff_h_acc   = L1["hunter_accuracy"] - L2["hunter_accuracy"]

    diff_p_count = L1["pusher_count"] - L2["pusher_count"]
    diff_p_speed = L1["pusher_speed_ms"] - L2["pusher_speed_ms"]
    diff_p_acc   = L1["pusher_accuracy"] - L2["pusher_accuracy"]

    diff_s_count = L1["sentinel_count"] - L2["sentinel_count"]
    diff_s_speed = L1["sentinel_speed_ms"] - L2["sentinel_speed_ms"]
    diff_s_acc   = L1["sentinel_accuracy"] - L2["sentinel_accuracy"]

    diff_egg_count = L1["egg_count"] - L2["egg_count"]
    diff_egg_inc   = L1["egg_incubation_ms"] - L2["egg_incubation_ms"]

    offset = level - last["level"]

    new_h_count = max(L1["hunter_count"] + diff_h_count * offset, 0)
    new_h_speed = clamp_speed(L1["hunter_speed_ms"] + diff_h_speed * offset)
    new_h_acc   = clamp_accuracy(L1["hunter_accuracy"] + diff_h_acc * offset)

    new_p_count = max(L1["pusher_count"] + diff_p_count * offset, 0)
    new_p_speed = clamp_speed(L1["pusher_speed_ms"] + diff_p_speed * offset)
    new_p_acc   = clamp_accuracy(L1["pusher_accuracy"] + diff_p_acc * offset)

    new_s_count = max(L1["sentinel_count"] + diff_s_count * offset, 0)
    new_s_speed = clamp_speed(L1["sentinel_speed_ms"] + diff_s_speed * offset)
    new_s_acc   = clamp_accuracy(L1["sentinel_accuracy"] + diff_s_acc * offset)

    new_egg_count = max(L1["egg_count"] + diff_egg_count * offset, 0)
    new_egg_inc   = max(L1["egg_incubation_ms"] + diff_egg_inc * offset, 1000)

    return {
        "hunter_count": new_h_count,
        "hunter_speed_ms": new_h_speed,
        "hunter_accuracy": new_h_acc,

        "pusher_count": new_p_count,
        "pusher_speed_ms": new_p_speed,
        "pusher_accuracy": new_p_acc,

        "sentinel_count": new_s_count,
        "sentinel_speed_ms": new_s_speed,
        "sentinel_accuracy": new_s_acc,

        "egg_count": new_egg_count,
        "egg_incubation_ms": new_egg_inc
    }

# -----------------------------------------------------------
# 19) GENERATE LEVEL & MAIN LOOP
# -----------------------------------------------------------
def generate_level(info):
    h_count   = info["hunter_count"]
    p_count   = info["pusher_count"]
    s_count   = info["sentinel_count"]
    e_count   = info["egg_count"]
    e_incub   = info["egg_incubation_ms"]

    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

    # border walls
    for x in range(GRID_WIDTH):
        grid[0][x] = UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT-1][x] = UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0] = UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH-1] = UNMOVEABLE_BLOCK

    # fill in random blocks
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            r = random.random()
            if r < 0.01:
                grid[y][x] = UNMOVEABLE_BLOCK
            elif r < 0.31:
                block_index = random.choice([0, 1, 2])
                grid[y][x] = (MOVEABLE_BLOCK, block_index)

    # place hunters
    placed_hunters = 0
    while placed_hunters < h_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = ENEMY
            placed_hunters += 1

    # place pushers
    placed_pushers = 0
    while placed_pushers < p_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = PUSHER
            placed_pushers += 1

    # place sentinels
    placed_sentinels = 0
    while placed_sentinels < s_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = SENTINEL
            placed_sentinels += 1

    # place eggs
    now = pygame.time.get_ticks()
    egg_positions = []
    while len(egg_positions) < e_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            factor = 0.9 + 0.2 * random.random()
            hatch_time = int(e_incub * factor)
            grid[ry][rx] = (EGG, hatch_time, now)
            egg_positions.append((rx, ry))

    return grid

def play_level(level, screen, clock, cumulative_score):
    global current_score, current_level
    info = get_level_def(level)

    h_count = info["hunter_count"]
    h_speed = info["hunter_speed_ms"]
    h_acc   = info["hunter_accuracy"]

    p_count = info["pusher_count"]
    p_speed = info["pusher_speed_ms"]
    p_acc   = info["pusher_accuracy"]

    s_count   = info["sentinel_count"]
    s_speed   = info["sentinel_speed_ms"]
    s_acc     = info["sentinel_accuracy"]

    e_count   = info["egg_count"]
    e_hatch_ms= info["egg_incubation_ms"]

    current_level = level
    current_score = cumulative_score

    grid = generate_level(info)
    place_player_best_spot(grid, screen)

    stats = {
        'moves': 0,
        'eggs_destroyed': 0,
        'hunters_killed': 0,
        'pushers_killed': 0,
        'sentinels_killed': 0  # We'll track sentinel kills too
    }

    level_start_time = pygame.time.get_ticks()
    last_hunter_update = pygame.time.get_ticks()
    last_pusher_update = pygame.time.get_ticks()
    last_sentinel_update = pygame.time.get_ticks()

    total_enemies = h_count + p_count + s_count

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pause_game(screen)
                elif event.key in (K_q, ord('q')):
                    if quit_confirm(screen):
                        maybe_record_highscore(current_score, current_level, screen)
                        pygame.quit()
                        sys.exit()
                elif event.key in (K_UP, K_DOWN, K_LEFT, K_RIGHT):
                    old_pos = get_player_position(grid)
                    if event.key == K_UP:
                        move_player_direction(grid, (0, -1), stats, screen)
                    elif event.key == K_DOWN:
                        move_player_direction(grid, (0, 1), stats, screen)
                    elif event.key == K_LEFT:
                        move_player_direction(grid, (-1, 0), stats, screen)
                    elif event.key == K_RIGHT:
                        move_player_direction(grid, (1, 0), stats, screen)
                    new_pos = get_player_position(grid)
                    if old_pos != new_pos:
                        stats['moves'] += 1

        current_time = pygame.time.get_ticks()

        # update hunters
        if current_time - last_hunter_update >= h_speed:
            update_hunters(grid, h_acc, screen)
            last_hunter_update = current_time

        # update pushers
        if current_time - last_pusher_update >= p_speed:
            update_pushers(grid, p_acc, screen)
            last_pusher_update = current_time

        # update sentinels
        if current_time - last_sentinel_update >= s_speed:
            update_sentinels(grid, s_acc, screen)
            last_sentinel_update = current_time

        # update eggs
        update_eggs(grid)

        draw_grid(screen, grid)
        draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, total_enemies)
        pygame.display.flip()
        clock.tick(10)

        # check if no enemies/pushers/sentinels & no eggs
        any_enemies = any(cell_type(c) in [ENEMY, PUSHER, SENTINEL] for row in grid for c in row)
        any_eggs = any(cell_type(c) == EGG for row in grid for c in row)
        if not any_enemies and not any_eggs:
            break

    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000

    # final scoring
    egg_points       = stats['eggs_destroyed']       * (1 * level)
    hunter_points    = stats['hunters_killed']       * (2 * level)
    pusher_points    = stats['pushers_killed']       * (3 * level)
    sentinel_points  = stats['sentinels_killed']     * (6 * level)  # new

    level_score    = egg_points + hunter_points + pusher_points + sentinel_points

    return stats['moves'], (stats['hunters_killed'] + stats['pushers_killed'] + stats['sentinels_killed']), time_taken, level_score

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    screen.fill((0, 0, 0))
    lines = [
        f"Level {level} Completed!",
        "",
        f"Enemies Eliminated: {enemies}",
        f"Moves Taken: {moves}",
        f"Time Taken: {time_taken} seconds",
        f"Score This Level: {level_score}",
        f"Cumulative Score: {cumulative_score}",
        "Press <space> to continue"
    ]
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    line_height = CHAR_HEIGHT * SCALE_Y + 4
    y = 100
    for line in lines:
        lw = len(line) * CHAR_WIDTH * SCALE_X
        x = (total_width - lw) // 2
        draw_text(screen, line, x, y, TEXT_COLOR_DEFAULT)
        y += line_height
    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    waiting = False
                elif event.key == K_ESCAPE:
                    pygame.quit()
                    sys.exit()

def main():
    global lives
    pygame.init()
    screen_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    screen_height = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + STATUS_HEIGHT
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()

    load_sprite_sheet("dos_spritesheet.png")
    sounds['squish'] = pygame.mixer.Sound("squish.wav")
    sounds['collision'] = pygame.mixer.Sound("collision.wav")

    load_levels_json("levels.json")

    cumulative_score = 0
    level = 1
    lives = 3

    while True:
        moves, enemies, time_taken, level_score = play_level(level, screen, clock, cumulative_score)
        cumulative_score += level_score
        show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score)
        level += 1

if __name__ == "__main__":
    main()
