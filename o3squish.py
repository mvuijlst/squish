"""
#############################################################
##                                                         ##
##                 S Q U I S H  v2.2.5                     ##
##                                                         ##
##        (c) 2025 Michel Vuijlsteke - Codepage Edition    ##
##                                                         ##
#############################################################
"""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame, random, sys
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

# Grid size: 40×25 cells. Each cell is 32×32 pixels.
GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE  # Extra vertical space for the status line

# Sprite sheet parameters:
# Our code-page 437 sprite sheet is 8×16 glyphs, scaled by 2 => 16×32 per glyph.
CHAR_WIDTH  = 8
CHAR_HEIGHT = 16
SCALE_X = 2
SCALE_Y = 2

# The sheet has 16 cols × 16 rows = 256 glyphs total.
SHEET_COLS = 16
SHEET_ROWS = 16

# -----------------------------------------------------------
# 2) COLOR DEFINITIONS (RGB)
# -----------------------------------------------------------
PLAYER_COLOR       = (0x59, 0xe1, 0xe3)  # #59e1e3
WALL_COLOR         = (0xff, 0xea, 0x16)  # #ffea16
HUNTER_COLOR       = (0xff, 0x16, 0xb0)  # #ff16b0
BLOCK_COLOR        = (0xee, 0xee, 0xee)  # #eeeeee
TEXT_COLOR_DEFAULT = (0xee, 0xee, 0xee)  # for grid/level text
STATUS_BG_COLOR    = (0x00, 0x00, 0x00)  # black background for the status line
STATUS_FG_COLOR    = (0xee, 0xee, 0xee)  # light text color on black

# -----------------------------------------------------------
# 3) GLOBAL RESOURCES
# -----------------------------------------------------------
sprite_sheet = None
sounds = {}
lives = 3

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

def get_cell_color(cell):
    """Return the color to tint a cell's glyph(s) based on its type."""
    t = cell_type(cell)
    if t == PLAYER:
        return PLAYER_COLOR
    elif t == UNMOVEABLE_BLOCK:
        return WALL_COLOR
    elif t == ENEMY:
        return HUNTER_COLOR
    elif t == MOVEABLE_BLOCK:
        return BLOCK_COLOR
    else:
        return (0, 0, 0)

# -----------------------------------------------------------
# 5) SPRITE-SHEET TEXT RENDERING FUNCTIONS
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

    # If color == black, let's do a colorkey approach so the black text is visible on a non-black background.
    # But since our status line background is black, it's simpler to always do the multiply approach.
    # We'll just multiply the glyph by the color. If color is black, it might vanish if the sprite is also black.
    # If you do want black text on black background, you'd do a special approach. But here we do:
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
# 6) ENTITY MAPPINGS (using code-page 437 glyphs)
# -----------------------------------------------------------
WALL_CHARS    = "\xDB\xDB"  # Wall: ██
BLOCK0_CHARS  = "\xB0\xB0"  # Moveable block variant 0: ░░
BLOCK1_CHARS  = "\xB1\xB1"  # Moveable block variant 1: ▒▒
BLOCK2_CHARS  = "\xB2\xB2"  # Moveable block variant 2: ▓▓
PLAYER_CHARS  = "\x11\x10"  # Player: ◄►
HUNTER_CHARS  = "\xC3\xB4"  # Hunter: ├┤
EMPTY_CHARS   = "  "

def get_cell_string(cell):
    """Return the 2-character string representing this cell."""
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
    else:
        return "??"

# -----------------------------------------------------------
# 7) DRAWING FUNCTIONS: GRID AND STATUS LINE
# -----------------------------------------------------------
def draw_grid(screen, grid):
    """
    Draw the game grid using sprite-sheet–rendered glyphs.
    Each cell is 2 glyphs wide and 1 glyph tall (32×32 pixels).
    """
    screen.fill((0, 0, 0))  # Background is black
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            color = get_cell_color(grid[y][x])
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters):
    """
    Draw a status line at the bottom of the screen.
    Background: black (#000000)
    Text: #eeeeee
    Uses U+0xB3 (│) as the separator.
    """
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
    # Fill the status line area black
    pygame.draw.rect(screen, STATUS_BG_COLOR, (0, GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y), total_width, STATUS_HEIGHT))

    elapsed = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    enemy_count = sum(1 for row in grid for cell in row if cell_type(cell) == ENEMY)
    level_score = (initial_hunters - enemy_count) * (2 * level)
    sep = chr(0xB3)  # U+0xB3 = │
    status_text = (
        f"Enemies: {enemy_count}  {sep}  "
        f"Time: {time_str}  {sep}  "
        f"Lives: {lives}  {sep}  "
        f"Score: {level_score} ({cumulative_score})"
    )
    text_x = 5
    text_y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + (STATUS_HEIGHT - CHAR_HEIGHT * SCALE_Y) // 2
    # We'll render the text in #eeeeee on black.
    draw_text(screen, status_text, text_x, text_y, (0xee, 0xee, 0xee))

# -----------------------------------------------------------
# 8) GAME LOGIC FUNCTIONS
# -----------------------------------------------------------
def get_player_position(grid):
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PLAYER:
                return (x, y)
    return None

def respawn_player(grid):
    global lives
    # Remove existing player
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PLAYER:
                grid[y][x] = EMPTY
    # We don't do anything else here; the next code that calls respawn might place the player.
    # But in this code, we do place the player immediately. We'll see.

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
    global lives
    sounds['collision'].play()
    lives -= 1
    if lives <= 0:
        game_over_screen(screen)
        pygame.quit()
        sys.exit()
    else:
        # remove the old player
        respawn_player(grid)
        # We might want to place the player again in the best possible location, or just skip it.
        # For simplicity, let's do the same approach as the initial spawn logic:
        place_player_best_spot(grid)

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
    elif t == ENEMY:
        handle_collision(grid, screen)
    return grid

def push_blocks(grid, start_pos, direction, stats, screen):
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
    return grid

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
                if (nx, ny) != goal and cell_type(grid[ny][nx]) != EMPTY:
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
            elif t == EMPTY:
                grid[ny][nx] = ENEMY
                grid[ey][ex] = EMPTY
                moved = True
        if not moved:
            mv = random.choice([(-1, -1), (0, -1), (1, -1),
                                 (-1,  0),          (1,  0),
                                 (-1,  1), (0,  1), (1,  1)])
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

# -----------------------------------------------------------
# 9) LEVEL DIFFICULTY AND GENERATION FUNCTIONS
# -----------------------------------------------------------
def get_level_params(level):
    """
    Return (hunters, move_speed, move_accuracy) for the given level.
    """
    if level == 1:
        return (3, 1000, 50)
    elif level == 2:
        return (4, 1000, 50)
    elif level == 3:
        return (5, 1000, 50)
    elif level == 4:
        return (6, 1000, 50)
    elif level == 5:
        return (6, 900, 50)
    elif level == 6:
        return (6, 800, 50)
    elif level == 7:
        return (6, 700, 50)
    elif level == 8:
        return (6, 700, 55)
    elif level == 9:
        return (6, 700, 60)
    elif level == 10:
        return (6, 700, 65)
    elif level == 11:
        return (7, 700, 70)
    else:
        hunters = 7 + ((level - 11) // 4)
        return (hunters, 700, 70)

def generate_level(num_enemies):
    """
    Create a 40×25 grid with outer walls, random blocks,
    a set number of enemy hunters, then place them,
    but do not place the player yet. We'll do that in place_player_best_spot.
    """
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

    # Place enemies
    enemy_positions = []
    while len(enemy_positions) < num_enemies:
        rx = random.randint(1, GRID_WIDTH-2)
        ry = random.randint(1, GRID_HEIGHT-2)
        if cell_type(grid[ry][rx]) == EMPTY:
            grid[ry][rx] = ENEMY
            enemy_positions.append((rx, ry))

    return grid

def place_player_best_spot(grid):
    """
    Place the player in the cell that is:
      1) As far away as possible from all enemies (maximize min distance).
      2) Tiebreak: as far away as possible from all blocks (unmoveable or moveable).
    """
    # Gather enemy positions
    enemies = []
    # Gather block positions
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
                # Distance to enemies
                if enemies:
                    enemy_min_dist = min(abs(x-ex) + abs(y-ey) for ex,ey in enemies)
                else:
                    enemy_min_dist = 9999
                # Distance to blocks
                if blocks:
                    block_min_dist = min(abs(x-bx) + abs(y-by) for bx,by in blocks)
                else:
                    block_min_dist = 9999

                # Compare to current best
                if enemy_min_dist > best_enemy_dist:
                    best_enemy_dist = enemy_min_dist
                    best_block_dist = block_min_dist
                    best_pos = (x, y)
                elif enemy_min_dist == best_enemy_dist:
                    # Tiebreak on block distance
                    if block_min_dist > best_block_dist:
                        best_block_dist = block_min_dist
                        best_pos = (x, y)

    if best_pos:
        px, py = best_pos
        grid[py][px] = PLAYER

# -----------------------------------------------------------
# 10) LEVEL PLAY FUNCTION AND MAIN LOOP
# -----------------------------------------------------------
def play_level(level, screen, clock, cumulative_score):
    hunters, move_speed, move_accuracy = get_level_params(level)
    grid = generate_level(hunters)

    # Now place the player in the best spot after the enemies/blocks are placed.
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
                    pygame.quit()
                    sys.exit()
                if event.key in (K_UP, K_DOWN, K_LEFT, K_RIGHT):
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

        draw_grid(screen, grid)
        draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, hunters)
        pygame.display.flip()
        clock.tick(10)

        enemy_exists = any(cell_type(c) == ENEMY for row in grid for c in row)
        if not enemy_exists:
            break

    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000
    stats['enemies_eliminated'] = hunters
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
    max_len = max(len(l) for l in lines)
    line_height = CHAR_HEIGHT * SCALE_Y + 4
    total_width = GRID_WIDTH * (CHAR_WIDTH * SCALE_X * 2)
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
