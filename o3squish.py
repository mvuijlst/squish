#############################################################
##                                                         ##
##                 S Q U I S H  v2.3.0                     ##
##                                                         ##
##       (c) 2025 Michel Vuijlsteke - Codepage Edition     ##
##                                                         ##
#############################################################

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame, random, sys, datetime
from pygame.locals import *
from heapq import heappush, heappop

# -----------------------------------------------------------
# 1) BASIC CONFIGURATION
# -----------------------------------------------------------

# Grid cell types.
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4
EGG = 5  # New entity type

# Grid size: 40×25 cells; each cell is 32×32 pixels.
GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE  # Extra vertical space for the status line

# Sprite sheet parameters:
# Our code page 437 sprite sheet contains glyphs that are 8×16 pixels.
CHAR_WIDTH  = 8
CHAR_HEIGHT = 16
# We scale both dimensions by 2 so that each glyph becomes 16×32.
SCALE_X = 2
SCALE_Y = 2
# Each cell is rendered as 2 glyphs wide (2 * 16 = 32) and 1 glyph tall (32).
SHEET_COLS = 16
SHEET_ROWS = 16

# -----------------------------------------------------------
# 2) COLOR DEFINITIONS (RGB)
# -----------------------------------------------------------
PLAYER_COLOR       = (0x59, 0xe1, 0xe3)  # #59e1e3
WALL_COLOR         = (0xff, 0xea, 0x16)  # #ffea16
HUNTER_COLOR       = (0xff, 0x16, 0xb0)  # #ff16b0
BLOCK_COLOR        = (0xee, 0xee, 0xee)  # #eeeeee
TEXT_COLOR_DEFAULT = (0xee, 0xee, 0xee)  # for grid/level screens
STATUS_BG_COLOR    = (0x00, 0x00, 0x00)  # black background for status line
STATUS_FG_COLOR    = (0xee, 0xee, 0xee)  # light text for status line

EGG_COLOR_0        = (0xfa, 0xe9, 0x01)  # #fae901 (0–75% done)
EGG_COLOR_1        = (0xfa, 0x82, 0x01)  # #fa8201 (75–90% done)
EGG_COLOR_FLASH1   = (0xfa, 0x01, 0x01)  # #fa0101 (>90%, flash color 1)
EGG_COLOR_FLASH2   = (0xff, 0xff, 0xff)  # #ffffff (>90%, flash color 2)

# -----------------------------------------------------------
# 3) GLOBAL RESOURCES
# -----------------------------------------------------------
sprite_sheet = None
sounds = {}
lives = 3
current_level = 0
current_score = 0

# -----------------------------------------------------------
# 4) HELPER FUNCTIONS
# -----------------------------------------------------------
def cell_type(cell):
    """Return the type of the cell (if tuple, return its first element)."""
    if isinstance(cell, tuple):
        return cell[0]
    return cell

def tint_surface(surface, tint_color):
    """
    Returns a copy of 'surface' tinted with 'tint_color'.
    Assumes the original surface is white (or monochrome).
    """
    tinted = surface.copy()
    tinted.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)
    return tinted

def get_egg_color(cell):
    """
    Return the color of the egg based on how far along it is in hatching.
    cell is (EGG, total_hatch_time_ms, creation_tick).
    """
    # current tick
    now = pygame.time.get_ticks()
    egg_total_time = cell[1]  # total time required to hatch (ms)
    egg_start = cell[2]       # creation (start) time in ms
    elapsed = now - egg_start
    if elapsed < 0:
        elapsed = 0

    progress = elapsed / egg_total_time  # fraction from 0.0 to 1.0 (or more)

    # 0–75% => #fae901
    if progress < 0.75:
        return EGG_COLOR_0
    # 75–90% => #fa8201
    elif progress < 0.90:
        return EGG_COLOR_1
    else:
        # >90% => flashing #fa0101 and #ffffff
        # Let's flash at 2 Hz (every 250 ms)
        # If even multiple => color 1, else color 2
        flash_period = 250
        flashes = (now // flash_period) % 2
        if flashes == 0:
            return EGG_COLOR_FLASH1
        else:
            return EGG_COLOR_FLASH2

def get_cell_color(cell):
    """Return the tint color for a cell based on its type."""
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
    else:
        return (0, 0, 0)

# -----------------------------------------------------------
# 5a) HIGH SCORE HANDLING (XOR-based "encryption")
# -----------------------------------------------------------
SCORE_FILE = "highscores.dat"

def encrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return bytes(b ^ key for b in data)

def decrypt_xor(data: bytes, key: int = 0xAA) -> bytes:
    return encrypt_xor(data, key)

def load_highscores() -> list:
    """Load high scores from SCORE_FILE. Each line: date|level|score|name."""
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
    """Save the top 20 high scores to SCORE_FILE."""
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
    """
    Display the top 20 high scores as (name, date, level, score).
    Wait for a key press before returning.
    """
    scores = sorted(scores, key=lambda s: s[0], reverse=True)[:20]
    screen.fill((0, 0, 0))

    title = "=== TOP 20 HIGH SCORES ==="
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    y = 50

    # Centered title
    lw = len(title) * CHAR_WIDTH * SCALE_X
    x = (total_width - lw) // 2
    draw_text(screen, title, x, y, TEXT_COLOR_DEFAULT)
    y += 50

    # Column headers (optional)
    headers = f"{'NAME':<15} {'DATE':<19} {'LVL':<4} {'SCORE':>6}"
    lw = len(headers) * CHAR_WIDTH * SCALE_X
    x = (total_width - lw) // 2
    draw_text(screen, headers, x, y, TEXT_COLOR_DEFAULT)
    y += 30

    # Score lines
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
    """
    If total_score qualifies for the top 20, ask for name and record the score.
    Then display the top 20 high scores.
    """
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
    """Pause the game and display a pause message until resumed."""
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
    """Display a quit confirmation prompt; return True if confirmed, else False."""
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
# 6c) SPRITE-SHEET TEXT RENDERING FUNCTIONS
# -----------------------------------------------------------
def load_sprite_sheet(filename):
    """Load the code-page 437 sprite sheet from file."""
    global sprite_sheet
    sprite_sheet = pygame.image.load(filename).convert_alpha()

def draw_char(surface, ch, x, y, color):
    """
    Draw a single code-page-437 character 'ch' from the sprite sheet onto 'surface' at (x,y),
    tinted with the specified 'color'.
    """
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
    """
    Draw a string of text onto 'surface' starting at (x,y) using our sprite-sheet font tinted with 'color'.
    """
    offset_x = 0
    for ch in text:
        draw_char(surface, ch, x + offset_x, y, color)
        offset_x += CHAR_WIDTH * SCALE_X

# -----------------------------------------------------------
# 7) ENTITY MAPPINGS (Code Page 437 glyphs)
# -----------------------------------------------------------
WALL_CHARS    = "\xDB\xDB"  # ██
BLOCK0_CHARS  = "\xB0\xB0"  # ░░
BLOCK1_CHARS  = "\xB1\xB1"  # ▒▒
BLOCK2_CHARS  = "\xB2\xB2"  # ▓▓
PLAYER_CHARS  = "\x11\x10"  # ◄►
HUNTER_CHARS  = "\xC3\xB4"  # ├┤
EGG_CHARS     = "\x09\x09"  # '○○' in CP437 (approx)
EMPTY_CHARS   = "  "

def get_cell_string(cell):
    """Return the 2-character string representing the cell."""
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
# 8) DRAWING FUNCTIONS: GRID AND STATUS LINE
# -----------------------------------------------------------
def draw_grid(screen, grid):
    """Draw the game grid using sprite-sheet rendered glyphs."""
    screen.fill((0, 0, 0))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            color = get_cell_color(grid[y][x])
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters):
    """
    Draw a status line at the bottom.
    """
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    pygame.draw.rect(screen, STATUS_BG_COLOR, (0, GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y), total_width, STATUS_HEIGHT))
    elapsed = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    enemy_count = sum(1 for row in grid for cell in row if cell_type(cell) == ENEMY)
    level_score = (initial_hunters - enemy_count) * (2 * level)
    sep = chr(0xB3)  # │
    status_text = (f"Enemies: {enemy_count}  {sep}  Time: {time_str}  {sep}  "
                   f"Lives: {lives}  {sep}  Score: {level_score} ({cumulative_score})")
    text_x = 5
    text_y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + (STATUS_HEIGHT - CHAR_HEIGHT * SCALE_Y) // 2
    draw_text(screen, status_text, text_x, text_y, STATUS_FG_COLOR)

# -----------------------------------------------------------
# 9) PLAYER SPAWN FUNCTIONS
# -----------------------------------------------------------
def get_player_position(grid):
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PLAYER:
                return (x, y)
    return None

def place_player_best_spot(grid):
    """
    Place the player in the cell that is maximally far from enemies and,
    among ties, maximally far from any blocks.
    """
    enemies = []
    blocks = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            t = cell_type(grid[y][x])
            if t == ENEMY:
                enemies.append((x, y))
            elif t == UNMOVEABLE_BLOCK or t == MOVEABLE_BLOCK:
                blocks.append((x, y))
    best_enemy_dist = -1
    best_block_dist = -1
    best_pos = None
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            if cell_type(grid[y][x]) == EMPTY:
                enemy_dist = min((abs(x-ex)+abs(y-ey)) for ex,ey in enemies) if enemies else 999
                block_dist = min((abs(x-bx)+abs(y-by)) for bx,by in blocks) if blocks else 999
                if enemy_dist > best_enemy_dist or (enemy_dist == best_enemy_dist and block_dist > best_block_dist):
                    best_enemy_dist = enemy_dist
                    best_block_dist = block_dist
                    best_pos = (x, y)
    if best_pos:
        grid[best_pos[1]][best_pos[0]] = PLAYER

def respawn_player(grid):
    """Remove any existing player from grid."""
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PLAYER:
                grid[y][x] = EMPTY

# -----------------------------------------------------------
# 10) GAME OVER AND COLLISION HANDLING
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
    """
    Called when an enemy collides with the player.
    Decrement life. If lives <= 0, record highscore, game over, exit.
    Otherwise respawn the player.
    """
    global lives, current_score, current_level
    sounds['collision'].play()
    lives -= 1
    if lives <= 0:
        maybe_record_highscore(current_score, current_level, screen)
        game_over_screen(screen)
        pygame.quit()
        sys.exit()
    else:
        respawn_player(grid)
        place_player_best_spot(grid)

# -----------------------------------------------------------
# 11) PLAYER MOVEMENT FUNCTIONS
# -----------------------------------------------------------
def move_player_direction(grid, direction, stats, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid
    px, py = player_pos
    dx, dy = direction
    tx, ty = px + dx, py + dy
    t = cell_type(grid[ty][tx])
    if t == EMPTY or t == EGG:  # Player can step onto eggs? (Optional choice)
        # If we want eggs to block movement, remove 't == EGG' from this check
        grid[py][px] = EMPTY
        grid[ty][tx] = PLAYER
    elif t == MOVEABLE_BLOCK:
        grid = push_blocks(grid, (px, py), direction, stats, screen)
    elif t == ENEMY:
        handle_collision(grid, screen)
    return grid

def push_blocks(grid, start_pos, direction, stats, screen):
    x, y = start_pos
    dx, dy = direction
    chain = []
    cx, cy = x + dx, y + dy
    # Gather all consecutive moveable blocks
    while cell_type(grid[cy][cx]) == MOVEABLE_BLOCK:
        chain.append((cx, cy))
        cx += dx
        cy += dy
    t = cell_type(grid[cy][cx])
    # If final spot is EMPTY (or EGG?), push chain forward
    if t == EMPTY or t == EGG:
        for bx, by in reversed(chain):
            grid[by+dy][bx+dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y+dy][x+dx] = PLAYER
        grid[y][x] = EMPTY
    # If final spot is ENEMY, squish it if next cell is blocked
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
    return grid

# -----------------------------------------------------------
# 12) ENEMY AI: A* PATHFINDING AND RANDOM MOVEMENT
# -----------------------------------------------------------
def a_star_path(grid, start, goal):
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
                # We can move through EMPTY or EGG or directly onto the player's cell (goal)
                t = cell_type(grid[ny][nx])
                if (nx, ny) != goal and t not in [EMPTY, EGG]:
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
            elif t in [EMPTY, EGG]:
                # If an enemy walks onto an EGG, we might optionally destroy the egg
                # or just walk over it. For now, let's just overwrite it (like stepping on it).
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
                elif t in [EMPTY, EGG]:
                    grid[ny][nx] = ENEMY
                    grid[ey][ex] = EMPTY
    return grid

# -----------------------------------------------------------
# 12b) EGG UPDATE: handle incubation
# -----------------------------------------------------------
def update_eggs(grid):
    """
    Check every EGG. If the egg's incubation time is done, turn it into ENEMY.
    """
    now = pygame.time.get_ticks()
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            c = grid[y][x]
            if cell_type(c) == EGG:
                egg_total_time = c[1]
                egg_start = c[2]
                if now - egg_start >= egg_total_time:
                    # Hatch into an ENEMY
                    grid[y][x] = ENEMY
    return grid

# -----------------------------------------------------------
# 13) LEVEL DIFFICULTY AND GENERATION
# -----------------------------------------------------------
def get_level_params(level):
    """
    Return (num_hunters, move_speed, move_accuracy, num_eggs, avg_egg_hatch_ms)
    """
    # old logic for hunters, speeds
    if level == 1:
        hunters, move_speed, move_accuracy = 3, 1000, 50
    elif level == 2:
        hunters, move_speed, move_accuracy = 4, 1000, 50
    elif level == 3:
        hunters, move_speed, move_accuracy = 5, 1000, 50
    elif level == 4:
        hunters, move_speed, move_accuracy = 6, 1000, 50
    elif level == 5:
        hunters, move_speed, move_accuracy = 6, 900, 50
    elif level == 6:
        hunters, move_speed, move_accuracy = 6, 800, 50
    elif level == 7:
        hunters, move_speed, move_accuracy = 6, 700, 50
    elif level == 8:
        hunters, move_speed, move_accuracy = 6, 700, 55
    elif level == 9:
        hunters, move_speed, move_accuracy = 6, 700, 60
    elif level == 10:
        hunters, move_speed, move_accuracy = 6, 700, 65
    elif level == 11:
        hunters, move_speed, move_accuracy = 7, 700, 70
    else:
        hunters = 7 + ((level - 11) // 4)
        move_speed = 700
        move_accuracy = 70

    # For eggs: from level 3 onwards, 2 eggs, average hatch time ~ 60000 ms
    if level >= 3:
        num_eggs = 2
        avg_egg_hatch_ms = 60000
    else:
        num_eggs = 0
        avg_egg_hatch_ms = 0

    return (hunters, move_speed, move_accuracy, num_eggs, avg_egg_hatch_ms)

def generate_level(num_enemies, num_eggs, avg_egg_hatch_ms):
    """
    Create the grid, place the given number of enemies, plus the given number of eggs
    with a random hatching time in [avg*0.9, avg*1.1].
    """
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

    # Place enemies
    enemy_positions = []
    while len(enemy_positions) < num_enemies:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = ENEMY
            enemy_positions.append((rx, ry))

    # Place eggs
    egg_positions = []
    now = pygame.time.get_ticks()
    while len(egg_positions) < num_eggs:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            # random hatching time in [avg*0.9, avg*1.1]
            factor = 0.9 + 0.2 * random.random()  # range 0.9 to 1.1
            hatch_time = int(avg_egg_hatch_ms * factor)
            grid[ry][rx] = (EGG, hatch_time, now)
            egg_positions.append((rx, ry))

    return grid

# -----------------------------------------------------------
# 14) LEVEL PLAY FUNCTION AND MAIN LOOP
# -----------------------------------------------------------
def play_level(level, screen, clock, cumulative_score):
    global current_score, current_level
    hunters, move_speed, move_accuracy, egg_count, avg_egg_time = get_level_params(level)
    current_level = level
    current_score = cumulative_score
    grid = generate_level(hunters, egg_count, avg_egg_time)
    place_player_best_spot(grid)
    stats = {'moves': 0, 'enemies_eliminated': 0}

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
        # Update enemies if the interval has passed
        if current_time - last_enemy_update >= enemy_update_interval:
            grid = update_enemies(grid, move_accuracy, screen)
            last_enemy_update = current_time

        # Always update eggs each frame
        grid = update_eggs(grid)

        draw_grid(screen, grid)
        draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, hunters)
        pygame.display.flip()
        clock.tick(10)

        # Check if all enemies are gone (i.e., none left)
        enemy_exists = any(cell_type(c) == ENEMY for row in grid for c in row)
        if not enemy_exists:
            # Also check if any eggs remain that can still hatch
            egg_exists = any(cell_type(c) == EGG for row in grid for c in row)
            # If no active enemies and no eggs remain, the level is complete
            if not egg_exists:
                break

    # Level complete
    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000
    stats['enemies_eliminated'] = hunters  # we assume all were eliminated or level ended
    level_score = stats['enemies_eliminated'] * (2 * level)
    return stats['moves'], stats['enemies_eliminated'], time_taken, level_score

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    screen.fill((0, 0, 0))
    lines = [
        f"Level {level} Completed!",
        "",
        f"Enemies Eliminated: {enemies}",
        f"Moves Taken: {moves}",
        f"Time Taken: {time_taken} seconds",
        f"Score: {level_score}",
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

    # Load the sprite sheet.
    load_sprite_sheet("dos_spritesheet.png")
    # Load sounds.
    sounds['squish'] = pygame.mixer.Sound("squish.wav")
    sounds['collision'] = pygame.mixer.Sound("collision.wav")

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
