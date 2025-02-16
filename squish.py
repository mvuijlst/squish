#############################################
##                                         ##
##          S Q U I S H  v3.10.12         ##
##                                         ##
##      (c) 2025 Michel Vuijlsteke         ##
##                                         ##
#############################################

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame
import random
import sys
import datetime
import json
import math
from pygame.locals import *
from heapq import heappush, heappop

# -----------------------------------------------------------
# 1) BASIC CONFIGURATION
# -----------------------------------------------------------
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4        # Hunter
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

# Enemy point values (immediately added when squished)
HUNTER_VALUE   = 2
EGG_VALUE      = 3
PUSHER_VALUE   = 5
SENTINEL_VALUE = 7

# -----------------------------------------------------------
# 2) COLOR DEFINITIONS
# -----------------------------------------------------------
TEXT_COLOR_DEFAULT = (0xa7, 0xa7, 0xa7)  # #a7a7a7
HIGHLIGHT_COLOR    = (0xfa, 0xfa, 0xfa)  # #fafafa

PLAYER_COLOR   = (0x59, 0xe1, 0xe3)
WALL_COLOR     = (0xff, 0xea, 0x16)
BLOCK_COLOR    = (0x00, 0x55, 0x00)  # #005500

HUNTER_COLOR   = (0xff, 0x16, 0xb0)
EGG_COLOR_0    = (0xfa, 0xe9, 0x01)
EGG_COLOR_1    = (0xfa, 0x82, 0x01)
EGG_COLOR_FLASH1 = (0xfa, 0x01, 0x01)
EGG_COLOR_FLASH2 = (0xff, 0xff, 0xff)
PUSHER_COLOR   = (0x99, 0x35, 0xff)
SENTINEL_COLOR = (0x47, 0x52, 0xcb)

STATUS_BG_COLOR = (0x00, 0x00, 0x00)

# -----------------------------------------------------------
# 3) GLOBAL RESOURCES
# -----------------------------------------------------------
sprite_sheet = None
sounds = {}
lives = 3
current_level = 0
running_level_score = 0
cumulative_time = 0
global_pause_offset = 0

levels_data = []

# Helper: return adjusted game time (only play time, not paused)
def get_game_time():
    return pygame.time.get_ticks() - global_pause_offset

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
    elif t == ENEMY:
        return HUNTER_COLOR
    elif t == EGG:
        return WALL_COLOR
    elif t == PUSHER:
        return PUSHER_COLOR
    elif t == SENTINEL:
        return SENTINEL_COLOR
    return (0, 0, 0)

# -----------------------------------------------------------
# 5a) HIGH SCORE HANDLING (unchanged)
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
                pygame.quit(); sys.exit()
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
# 5b) PAUSE AND QUIT CONFIRMATION (with timer pause)
# -----------------------------------------------------------
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
                        maybe_record_highscore(current_score, current_level, screen)
                        pygame.quit(); sys.exit()
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

# -----------------------------------------------------------
# 6c) SPRITE-SHEET TEXT RENDERING (unchanged)
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
# 7) ENTITY MAPPINGS (unchanged)
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

def draw_status_line(screen, grid, level_start_time, lives, level_name, running_level_score, time_offset):
    container_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    elapsed = time_offset + (get_game_time() - level_start_time) // 1000
    # Ensure elapsed is not negative.
    elapsed = max(0, elapsed)
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    current_enemy_count = sum(1 for row in grid for c in row if cell_type(c) in [ENEMY, PUSHER, SENTINEL])
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
            elif t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, EGG):
                blocks.append((x, y))
    best_enemy_dist = -1
    best_block_dist = -1
    best_edge_dist  = -1
    best_pos = None
    for yy in range(1, GRID_HEIGHT - 1):
        for xx in range(1, GRID_WIDTH - 1):
            if cell_type(grid[yy][xx]) == EMPTY:
                enemy_dist = min([abs(xx - ex) + abs(yy - ey) for ex, ey in enemies] or [999])
                block_dist = min([abs(xx - bx) + abs(yy - by) for bx, by in blocks] or [999])
                dist_edge = min(xx - 1, (GRID_WIDTH - 2) - xx, yy - 1, (GRID_HEIGHT - 2) - yy)
                if (enemy_dist > best_enemy_dist or
                    (enemy_dist == best_enemy_dist and block_dist > best_block_dist) or
                    (enemy_dist == best_enemy_dist and block_dist == best_block_dist and dist_edge > best_edge_dist)):
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
        pygame.quit(); sys.exit()
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
    elif t in (ENEMY, PUSHER, SENTINEL):
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
        nx, ny = cx + dx, cy + dy
        behind_t = cell_type(grid[ny+dy][nx+dx]) if (0 <= nx+dx < GRID_WIDTH and 0 <= ny+dy < GRID_HEIGHT) else None
        if behind_t == UNMOVEABLE_BLOCK:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats.setdefault('sentinels_killed', 0)
            stats['sentinels_killed'] += 1
            stats["score"] = stats.get("score", 0) + SENTINEL_VALUE
            sounds['squish'].play()

    elif occupant_t == EGG:
        nx, ny = cx + dx, cy + dy
        # Only destroy (squish) the egg if it's pinned by a block.
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['eggs_destroyed'] = stats.get('eggs_destroyed', 0) + 1
            stats["score"] = stats.get("score", 0) + EGG_VALUE
            sounds['squish'].play()
    else:
        # Do nothing if the occupant is not pushable.
        return


# -----------------------------------------------------------
# 12) EGG UPDATE => hatch into pushers (unchanged)
# -----------------------------------------------------------
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

# -----------------------------------------------------------
# 13) A* PATHFINDING FOR ENEMIES (eggs are blocked)
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
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, ENEMY, PUSHER, SENTINEL, EGG):
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
    hunters_positions = [(x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if cell_type(grid[y][x]) == ENEMY]
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
            elif t == EMPTY:
                grid[ny][nx] = ENEMY
                grid[ey][ex] = EMPTY
                moved = True
        if not moved:
            mv = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
            nx, ny = ex + mv[0], ey + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t == EMPTY:
                    grid[ny][nx] = ENEMY
                    grid[ey][ex] = EMPTY

def update_sentinels(grid, sentinel_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return
    sentinel_positions = [(x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if cell_type(grid[y][x]) == SENTINEL]
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
            mv = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
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

# -----------------------------------------------------------
# 14) PUSHER LOGIC (eggs are not pushable)
# -----------------------------------------------------------
def a_star_path_for_pusher(grid, start, goal):
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
            if t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK, ENEMY, PUSHER, SENTINEL, EGG):
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
        elif final_t in (PLAYER, ENEMY, PUSHER, SENTINEL):
            bx2, by2 = cx+dx, cy+dy
            if not (0 <= bx2 < GRID_WIDTH and 0 <= by2 < GRID_HEIGHT):
                return False
            behind_t = cell_type(grid[by2][bx2])
            if behind_t in (MOVEABLE_BLOCK, UNMOVEABLE_BLOCK, EGG):
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
    elif occupant_t in (ENEMY, PUSHER, SENTINEL):
        bx2, by2 = nx+dx, ny+dy
        if not (0 <= bx2 < GRID_WIDTH and 0 <= by2 < GRID_HEIGHT):
            return False
        behind_t = cell_type(grid[by2][bx2])
        if behind_t in (MOVEABLE_BLOCK, UNMOVEABLE_BLOCK, EGG):
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

# -----------------------------------------------------------
# 15) LEVELS LOADING / DEFINITION (NEW FORMAT)
# -----------------------------------------------------------
def load_levels_json(filename="levels.json"):
    global levels_data
    if not os.path.exists(filename):
        print(f"ERROR: Cannot find {filename}. Using empty levels_data.")
        levels_data = []
        return
    with open(filename, "r", encoding="utf-8") as f:
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
    return {"level": level_letter, "pull_blocks": False, "speed_up": False, "explosive_blocks": False, "winning_level": 1, "enemies": {}, "egg_incubation_ms": 0}

# -----------------------------------------------------------
# NEW: LEVEL SELECTION & DETAILS SCREENS
# -----------------------------------------------------------
def level_selection_screen(screen, clock):
    levels = sorted({ entry.get("level") for entry in levels_data })
    if not levels:
        levels = ["A"]
    selected_index = 0
    while True:
        screen.fill((0, 0, 0))
        draw_text(screen, "Select a Level:", 50, 20, TEXT_COLOR_DEFAULT)
        y = 60
        for idx, lvl in enumerate(levels):
            text = f"Level {lvl}"
            color = (255, 255, 0) if idx == selected_index else TEXT_COLOR_DEFAULT
            draw_text(screen, text, 50, y, color)
            y += CHAR_HEIGHT * SCALE_Y + 10
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_UP:
                    selected_index = (selected_index - 1) % len(levels)
                elif event.key == K_DOWN:
                    selected_index = (selected_index + 1) % len(levels)
                elif event.key == K_RETURN:
                    return levels[selected_index]
            elif event.type == MOUSEBUTTONDOWN:
                mouse_x, mouse_y = event.pos
                option_height = CHAR_HEIGHT * SCALE_Y + 10
                index_clicked = (mouse_y - 60) // option_height
                if 0 <= index_clicked < len(levels):
                    selected_index = index_clicked
                    return levels[selected_index]
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

# -----------------------------------------------------------
# NEW: PLAY A MAIN LEVEL (with sublevels; no sublevel screen)
# -----------------------------------------------------------
def play_main_level(level_def, screen, clock, cumulative_score, cumulative_time):
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
        moves, enemies_eliminated, time_taken, sublevel_score, level_name = play_sublevel(level_def, sublevel, screen, clock, running_level_score, sub_time_offset)
        running_level_score = sublevel_score
        total_moves += moves
        total_enemies += enemies_eliminated
        level_time += time_taken
        pygame.mixer.Sound("sound/sublevel.mp3").play()
    pygame.mixer.Sound("sound/level.mp3").play()
    show_level_complete_screen(screen, level_def.get("level"), total_moves, total_enemies, level_time, running_level_score)
    cumulative_time += level_time
    return total_moves, total_enemies, level_time, running_level_score, level_def.get("level"), cumulative_time

def play_sublevel(level_def, sublevel, screen, clock, initial_sublevel_score, time_offset):
    enemies_def = level_def.get("enemies", {})
    h_speed = enemies_def.get("hunter", {}).get("speed_ms", 1000)
    h_acc   = enemies_def.get("hunter", {}).get("accuracy", 50)
    p_speed = enemies_def.get("pusher", {}).get("speed_ms", 1000)
    p_acc   = enemies_def.get("pusher", {}).get("accuracy", 50)
    s_speed = enemies_def.get("sentinel", {}).get("speed_ms", 1000)
    s_acc   = enemies_def.get("sentinel", {}).get("accuracy", 50)
    global current_level
    current_level = sublevel
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
    level_start_time = get_game_time()
    last_hunter_update = get_game_time()
    last_pusher_update = get_game_time()
    last_sentinel_update = get_game_time()
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pause_duration = pause_game(screen)
                    level_start_time += pause_duration
                elif event.key in (K_q, ord('q')):
                    if quit_confirm(screen):
                        maybe_record_highscore(running_score, current_level, screen)
                        pygame.quit(); sys.exit()
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
        draw_status_line(screen, grid, level_start_time, lives, f"{level_def.get('level')}{sublevel}", stats["score"], time_offset)
        pygame.display.flip()
        clock.tick(10)
        any_enemies = any(cell_type(c) in [ENEMY, PUSHER, SENTINEL] for row in grid for c in row)
        any_eggs = any(cell_type(c) == EGG for row in grid for c in row)
        if not any_enemies and not any_eggs:
            break
    level_end_time = get_game_time()
    time_taken = max(0, (level_end_time - level_start_time) // 1000)
    total_sublevels = level_def.get("winning_level", 1)
    bonus = (4 * math.floor(total_sublevels / 3) + 5) + 4 * (sublevel - 1)
    stats["score"] += bonus
    return stats['moves'], (stats['hunters_killed'] + stats['pushers_killed'] + stats['sentinels_killed']), time_taken, stats["score"], f"{level_def.get('level')}{sublevel}"

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

# -----------------------------------------------------------
# 16) GENERATE LEVEL (modified to use sublevel for scaling enemy counts)
# -----------------------------------------------------------
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
    while placed_hunters < h_count:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = ENEMY
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

# -----------------------------------------------------------
# MAIN LOOP: LEVEL SELECTION, DETAILS, PLAY, THEN RETURN
# -----------------------------------------------------------
def main():
    global lives, cumulative_time
    pygame.init()
    screen_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    screen_height = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + STATUS_HEIGHT
    screen = pygame.display.set_mode((screen_width, screen_height))
    clock = pygame.time.Clock()
    load_sprite_sheet("dos_spritesheet.png")
    sounds['squish'] = pygame.mixer.Sound("sound/squish.mp3")
    sounds['collision'] = pygame.mixer.Sound("sound/collision.mp3")
    load_levels_json("levels.json")
    while True:
        level_score = 0
        cumulative_time = 0
        selected_level_letter = level_selection_screen(screen, clock)
        level_def = get_main_level_def(selected_level_letter)
        if show_level_details_screen(screen, clock, level_def):
            moves, enemies_eliminated, level_time, level_score, lvl, cumulative_time = play_main_level(level_def, screen, clock, 0, 0)
            
if __name__ == "__main__":
    main()
