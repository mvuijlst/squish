#############################################################
##                                                         ##
##        S Q U I S H  v2.3.3  (Improved Player Spawn)     ##
##                                                         ##
##    JSON-based levels, eggs, collisions, A* pathfinding  ##
##    Player spawn is far from enemies -> blocks -> edges  ##
##    Spawn animation to highlight player's new position   ##
##                                                         ##
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

# -----------------------------------------------------------
# 1) BASIC CONFIGURATION
# -----------------------------------------------------------

# Grid cell types
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4
EGG = 5

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

# -----------------------------------------------------------
# 2) COLOR DEFINITIONS
# -----------------------------------------------------------
PLAYER_COLOR       = (0x59, 0xe1, 0xe3)  # #59e1e3
WALL_COLOR         = (0xff, 0xea, 0x16)  # #ffea16
HUNTER_COLOR       = (0xff, 0x16, 0xb0)  # #ff16b0
BLOCK_COLOR        = (0xee, 0xee, 0xee)  # #eeeeee
TEXT_COLOR_DEFAULT = (0xee, 0xee, 0xee)
STATUS_BG_COLOR    = (0x00, 0x00, 0x00)
STATUS_FG_COLOR    = (0xee, 0xee, 0xee)

# Egg color transitions
EGG_COLOR_0        = (0xfa, 0xe9, 0x01)  # #fae901
EGG_COLOR_1        = (0xfa, 0x82, 0x01)  # #fa8201
EGG_COLOR_FLASH1   = (0xfa, 0x01, 0x01)  # #fa0101
EGG_COLOR_FLASH2   = (0xff, 0xff, 0xff)  # #ffffff

# -----------------------------------------------------------
# 3) GLOBAL RESOURCES
# -----------------------------------------------------------
sprite_sheet = None
sounds = {}
lives = 3
current_level = 0
current_score = 0

# We’ll store level definitions from JSON in this global variable
levels_data = []

# -----------------------------------------------------------
# 4) HELPER FUNCTIONS
# -----------------------------------------------------------
def cell_type(cell):
    """Return the type of the cell (EGG, ENEMY, etc.) or the raw int if not a tuple."""
    if isinstance(cell, tuple):
        return cell[0]
    return cell

def tint_surface(surface, tint_color):
    tinted = surface.copy()
    tinted.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)
    return tinted

def get_egg_color(cell):
    """Compute egg color as it incubates."""
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
    """Decide what color tint to apply for each cell type."""
    t = cell_type(cell)
    if t == PLAYER:
        return PLAYER_COLOR
    elif t == UNMOVEABLE_BLOCK:
        return WALL_COLOR
    elif t == ENEMY:
        return HUNTER_COLOR
    elif t == MOVEABLE_BLOCK:
        return BLOCK_COLOR
    elif t == EGG:
        return get_egg_color(cell)
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
    """Prompt the player for their name and return it."""
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
    """Display top 20 high scores. Wait for a key press before returning."""
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
    """Pause the game until the user presses space or quits."""
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
    """Prompt the user to confirm quitting. Return True if yes."""
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
WALL_CHARS    = "\xDB\xDB"  
BLOCK0_CHARS  = "\xB0\xB0"  
BLOCK1_CHARS  = "\xB1\xB1"  
BLOCK2_CHARS  = "\xB2\xB2"  
PLAYER_CHARS  = "\x11\x10"  # ◄►
HUNTER_CHARS  = "\xC3\xB4"  
EGG_CHARS     = "\x09\x09"  
EMPTY_CHARS   = "  "

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
    else:
        return "??"

# -----------------------------------------------------------
# 8) DRAWING THE GRID & STATUS
# -----------------------------------------------------------
def draw_grid(screen, grid):
    """Refresh the entire game grid."""
    screen.fill((0, 0, 0))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            color = get_cell_color(grid[y][x])
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters):
    """Show bottom status bar with enemies, time, lives, and partial score."""
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    pygame.draw.rect(screen, STATUS_BG_COLOR, (0, GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y), total_width, STATUS_HEIGHT))
    elapsed = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    enemy_count = sum(1 for row in grid for cell in row if cell_type(cell) == ENEMY)
    level_score = (initial_hunters - enemy_count) * (2 * level)
    sep = chr(0xB3)
    status_text = (f"Enemies: {enemy_count}  {sep}  Time: {time_str}  {sep}  "
                   f"Lives: {lives}  {sep}  Score: {level_score} ({cumulative_score})")
    text_x = 5
    text_y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + (STATUS_HEIGHT - CHAR_HEIGHT * SCALE_Y) // 2
    draw_text(screen, status_text, text_x, text_y, STATUS_FG_COLOR)

# -----------------------------------------------------------
# 9) PLAYER SPAWN LOGIC & ANIMATION
# -----------------------------------------------------------
def get_player_position(grid):
    """
    Return (x,y) if there's a cell with type=PLAYER, else None.
    Used in movement, collisions, AI references, etc.
    """
    for yy in range(GRID_HEIGHT):
        for xx in range(GRID_WIDTH):
            if cell_type(grid[yy][xx]) == PLAYER:
                return (xx, yy)
    return None

def place_player_best_spot(grid, screen):
    """
    Place the player in the cell that is:
      1) Max distance from any enemy,
      2) Ties broken by max distance from any block,
      3) Then by max distance from the outer wall.
    Then show a short spawn animation in that cell.
    """

    # Gather enemy & block coordinates
    enemies = []
    blocks = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            t = cell_type(grid[y][x])
            if t == ENEMY:
                enemies.append((x, y))
            elif t in (UNMOVEABLE_BLOCK, MOVEABLE_BLOCK):
                blocks.append((x, y))

    best_enemy_dist = -1
    best_block_dist = -1
    best_edge_dist  = -1
    best_pos = None

    # We only consider the range(1..GRID_WIDTH-2) and (1..GRID_HEIGHT-2)
    # because the border is typically walls.
    for yy in range(1, GRID_HEIGHT - 1):
        for xx in range(1, GRID_WIDTH - 1):
            if cell_type(grid[yy][xx]) == EMPTY:
                # Distance to closest enemy
                if enemies:
                    enemy_dist = min(abs(xx - ex) + abs(yy - ey) for ex, ey in enemies)
                else:
                    enemy_dist = 999

                # Distance to closest block
                if blocks:
                    block_dist = min(abs(xx - bx) + abs(yy - by) for bx, by in blocks)
                else:
                    block_dist = 999

                # Distance from outer wall
                dist_edge = min(xx - 1, (GRID_WIDTH - 2) - xx, yy - 1, (GRID_HEIGHT - 2) - yy)

                # Compare triple
                if (enemy_dist > best_enemy_dist
                    or (enemy_dist == best_enemy_dist and block_dist > best_block_dist)
                    or (enemy_dist == best_enemy_dist and block_dist == best_block_dist and dist_edge > best_edge_dist)):
                    best_enemy_dist = enemy_dist
                    best_block_dist = block_dist
                    best_edge_dist  = dist_edge
                    best_pos = (xx, yy)

    if best_pos:
        x, y = best_pos
        # Show the spawn animation
        show_spawn_animation(grid, screen, x, y)
        # Then actually place the player
        grid[y][x] = PLAYER

def respawn_player(grid, screen):
    """Remove any existing player, then call place_player_best_spot."""
    for yy in range(GRID_HEIGHT):
        for xx in range(GRID_WIDTH):
            if cell_type(grid[yy][xx]) == PLAYER:
                grid[yy][xx] = EMPTY
    place_player_best_spot(grid, screen)

def show_spawn_animation(grid, screen, x, y):
    """
    4-step animation in cell (x,y):
      1) "--" (#ff0000)
      2) "←→" (#ff9900)
      3) "«»" (#ffff00)
      4) "<>" (#ffffff)
    Each step ~200 ms, then revert (we do not store them in the grid).
    """
    steps = [
        ("--", (0xff, 0x00, 0x00)),
        ("←→", (0xff, 0x99, 0x00)),
        ("«»", (0xff, 0xff, 0x00)),
        ("<>", (0xff, 0xff, 0xff))
    ]
    clock = pygame.time.Clock()
    for glyphs, color in steps:
        # Draw the current grid
        draw_grid(screen, grid)
        # Overlay our temporary glyph at (x, y)
        px = x * (CHAR_WIDTH * SCALE_X * 2)
        py = y * (CHAR_HEIGHT * SCALE_Y)
        draw_text(screen, glyphs, px, py, color)
        pygame.display.flip()
        clock.tick(5)  # ~ 200 ms per step

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
    """When the player steps onto an enemy or egg."""
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
        grid = push_blocks(grid, (px, py), direction, stats, screen)
    elif t in (ENEMY, EGG):
        handle_collision(grid, screen)
    return grid

def push_blocks(grid, start_pos, direction, stats, screen):
    """
    Attempt to push moveable blocks.
    If final cell is ENEMY or EGG pinned, squish it.
    """
    x, y = start_pos
    dx, dy = direction
    chain = []
    cx, cy = x + dx, y + dy
    while cell_type(grid[cy][cx]) == MOVEABLE_BLOCK:
        chain.append((cx, cy))
        cx += dx
        cy += dy

    t = cell_type(grid[cy][cx])
    if t == EMPTY:
        for bx, by in reversed(chain):
            grid[by+dy][bx+dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y+dy][x+dx] = PLAYER
        grid[y][x] = EMPTY

    elif t == ENEMY:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['enemies_eliminated'] += 1
            sounds['squish'].play()

    elif t == EGG:
        nx, ny = cx + dx, cy + dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['eggs_destroyed'] += 1
            sounds['squish'].play()

    return grid

# -----------------------------------------------------------
# 12) ENEMY AI (A* + random fallback)
# -----------------------------------------------------------
def a_star_path(grid, start, goal):
    """
    8-direction A* pathfinding. EGG/ENEMY/blocks block the path.
    """
    def heuristic(a, b):
        return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
    
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    
    while open_set:
        _, current = heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        for ddx in [-1, 0, 1]:
            for ddy in [-1, 0, 1]:
                if ddx == 0 and ddy == 0:
                    continue
                nx = current[0] + ddx
                ny = current[1] + ddy
                if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                    continue
                t = cell_type(grid[ny][nx])
                if (nx, ny) != goal and t != EMPTY:
                    continue
                tentative = g_score[current] + 1
                if (nx, ny) in g_score and tentative >= g_score[(nx, ny)]:
                    continue
                came_from[(nx, ny)] = current
                g_score[(nx, ny)] = tentative
                f_score[(nx, ny)] = tentative + heuristic((nx, ny), goal)
                heappush(open_set, (f_score[(nx, ny)], (nx, ny)))
    return []

def update_enemies(grid, move_accuracy, screen):
    """
    Move each enemy. They call get_player_position to chase or do random steps.
    """
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid
    
    enemies = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                enemies.append((x, y))
                
    collision_occurred = False
    for ex, ey in enemies:
        if collision_occurred:
            break
        
        path = a_star_path(grid, (ex, ey), player_pos)
        moved = False
        
        if len(path) >= 2 and random.random() < (move_accuracy / 100.0):
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
            mv = random.choice([
                (-1, -1), (0, -1), (1, -1),
                (-1,  0),          (1,  0),
                (-1,  1), (0,  1), (1,  1)
            ])
            nx = ex + mv[0]
            ny = ey + mv[1]
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                t = cell_type(grid[ny][nx])
                if t == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif t == EMPTY:
                    grid[ny][nx] = ENEMY
                    grid[ey][ex] = EMPTY
    return grid

def update_eggs(grid):
    """Check if any eggs have passed their incubation time. If so, hatch them."""
    now = pygame.time.get_ticks()
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            c = grid[y][x]
            if cell_type(c) == EGG:
                egg_total_time = c[1]
                egg_start = c[2]
                if now - egg_start >= egg_total_time:
                    grid[y][x] = ENEMY
    return grid

# -----------------------------------------------------------
# 13) LOADING & EXTRAPOLATION FOR LEVELS
# -----------------------------------------------------------
def load_levels_json(filename="levels.json"):
    """Load the external levels.json into levels_data."""
    global levels_data
    if not os.path.exists(filename):
        print(f"ERROR: Cannot find {filename}. Using empty levels_data.")
        levels_data = []
        return
    with open(filename, "r", encoding="utf-8") as f:
        levels_data = json.load(f)

def get_level_def(level):
    """Return a dictionary with hunter_count, speed_ms, accuracy, egg_count, egg_incubation_ms."""
    if not levels_data:
        # fallback if no file or empty
        return {
            "hunter_count": 3,
            "hunter_speed_ms": 1000,
            "hunter_accuracy": 50,
            "egg_count": 0,
            "egg_incubation_ms": 0
        }
    max_defined = levels_data[-1]["level"]
    if level <= max_defined:
        # Find that entry in the JSON
        for entry in levels_data:
            if entry["level"] == level:
                return parse_level_entry(entry)
        # fallback if not found
        return parse_level_entry(levels_data[0])
    # If we exceed the final level in JSON, extrapolate
    if len(levels_data) >= 2:
        second_last = levels_data[-2]
        last = levels_data[-1]
        return extrapolate_level(level, second_last, last)
    else:
        # If only one level in the file, can't do differences
        return parse_level_entry(levels_data[-1])

def parse_level_entry(entry):
    enemies = entry.get("enemies", {})
    hunter = enemies.get("hunter", {})
    egg = enemies.get("egg", {})

    h_count = hunter.get("count", 0)
    h_speed_ms = hunter.get("speed_ms", 1000)
    h_accuracy = hunter.get("accuracy", 50)

    e_count = egg.get("count", 0)
    e_incub_s = egg.get("incubation_s", 0)

    return {
        "hunter_count": h_count,
        "hunter_speed_ms": h_speed_ms,
        "hunter_accuracy": h_accuracy,
        "egg_count": e_count,
        "egg_incubation_ms": e_incub_s * 1000
    }

def extrapolate_level(level, second_last, last):
    """Simple difference-based extrapolation from the final two entries."""
    L2 = parse_level_entry(second_last)
    L1 = parse_level_entry(last)

    def clamp_speed(sp):
        return max(sp, 100)

    def clamp_accuracy(a):
        return min(a, 100)

    diff_h_count = L1["hunter_count"] - L2["hunter_count"]
    diff_h_speed = L1["hunter_speed_ms"] - L2["hunter_speed_ms"]
    diff_h_acc   = L1["hunter_accuracy"] - L2["hunter_accuracy"]
    diff_egg_count = L1["egg_count"] - L2["egg_count"]
    diff_egg_inc   = L1["egg_incubation_ms"] - L2["egg_incubation_ms"]

    offset = level - last["level"]

    new_h_count = L1["hunter_count"] + diff_h_count * offset
    new_h_speed = L1["hunter_speed_ms"] + diff_h_speed * offset
    new_h_acc   = L1["hunter_accuracy"] + diff_h_acc * offset
    new_egg_count = L1["egg_count"] + diff_egg_count * offset
    new_egg_inc   = L1["egg_incubation_ms"] + diff_egg_inc * offset

    new_h_count = max(new_h_count, 0)
    new_h_speed = clamp_speed(new_h_speed)
    new_h_acc   = clamp_accuracy(new_h_acc)
    new_egg_count = max(new_egg_count, 0)
    new_egg_inc   = max(new_egg_inc, 1000)

    return {
        "hunter_count": new_h_count,
        "hunter_speed_ms": new_h_speed,
        "hunter_accuracy": new_h_acc,
        "egg_count": new_egg_count,
        "egg_incubation_ms": new_egg_inc
    }

# -----------------------------------------------------------
# 14) LEVEL GENERATION & MAIN LOOP
# -----------------------------------------------------------
def generate_level(num_enemies, num_eggs, avg_egg_hatch_ms):
    """Generate the grid with walls, blocks, enemies, eggs."""
    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    # Border walls
    for x in range(GRID_WIDTH):
        grid[0][x] = UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT-1][x] = UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0] = UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH-1] = UNMOVEABLE_BLOCK

    # Random blocks
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            r = random.random()
            if r < 0.01:
                grid[y][x] = UNMOVEABLE_BLOCK
            elif r < 0.31:
                block_index = random.choice([0, 1, 2])
                grid[y][x] = (MOVEABLE_BLOCK, block_index)

    # Enemies
    enemy_positions = []
    while len(enemy_positions) < num_enemies:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = ENEMY
            enemy_positions.append((rx, ry))

    # Eggs
    egg_positions = []
    now = pygame.time.get_ticks()
    while len(egg_positions) < num_eggs:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            factor = 0.9 + 0.2 * random.random()
            hatch_time = int(avg_egg_hatch_ms * factor)
            grid[ry][rx] = (EGG, hatch_time, now)
            egg_positions.append((rx, ry))

    return grid

def play_level(level, screen, clock, cumulative_score):
    """
    1) Retrieve definitions from JSON or extrapolation
    2) Generate grid
    3) Place player with 'place_player_best_spot'
    4) Run the game loop until no enemies & eggs remain
    5) Return stats
    """
    global current_score, current_level
    info = get_level_def(level)
    hunters = info["hunter_count"]
    move_speed = info["hunter_speed_ms"]
    move_accuracy = info["hunter_accuracy"]
    egg_count = info["egg_count"]
    egg_time_ms = info["egg_incubation_ms"]

    current_level = level
    current_score = cumulative_score

    grid = generate_level(hunters, egg_count, egg_time_ms)
    place_player_best_spot(grid, screen)

    stats = {
        'moves': 0,
        'enemies_eliminated': 0,
        'eggs_destroyed': 0
    }

    level_start_time = pygame.time.get_ticks()
    enemy_update_interval = move_speed
    last_enemy_update = pygame.time.get_ticks()

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
                        direction = (0, -1)
                    elif event.key == K_DOWN:
                        direction = (0, 1)
                    elif event.key == K_LEFT:
                        direction = (-1, 0)
                    elif event.key == K_RIGHT:
                        direction = (1, 0)
                    grid = move_player_direction(grid, direction, stats, screen)
                    new_pos = get_player_position(grid)
                    if old_pos != new_pos:
                        stats['moves'] += 1

        current_time = pygame.time.get_ticks()
        if current_time - last_enemy_update >= enemy_update_interval:
            grid = update_enemies(grid, move_accuracy, screen)
            last_enemy_update = current_time

        grid = update_eggs(grid)

        draw_grid(screen, grid)
        draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, hunters)
        pygame.display.flip()
        clock.tick(10)

        # Win condition: no enemies & no eggs
        enemy_exists = any(cell_type(c) == ENEMY for row in grid for c in row)
        egg_exists = any(cell_type(c) == EGG for row in grid for c in row)
        if not enemy_exists and not egg_exists:
            break

    # Level done
    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000
    # Score formula: 2 * level * (enemies) + 1 * level * (eggs)
    level_score = stats['enemies_eliminated'] * (2 * level) + stats['eggs_destroyed'] * (1 * level)
    return stats['moves'], stats['enemies_eliminated'], time_taken, level_score

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    """Display an interstitial at level completion."""
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

    # Load sprite sheet & sounds
    load_sprite_sheet("dos_spritesheet.png")
    sounds['squish'] = pygame.mixer.Sound("squish.wav")
    sounds['collision'] = pygame.mixer.Sound("collision.wav")

    # Load level definitions
    load_levels_json("levels.json")

    cumulative_score = 0
    level = 1
    lives = 3

    while True:
        # Play the level
        moves, enemies, time_taken, level_score = play_level(level, screen, clock, cumulative_score)
        cumulative_score += level_score
        show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score)
        level += 1

if __name__ == "__main__":
    main()
