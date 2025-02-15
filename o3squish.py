"""
#############################################################
##                                                         ##
##                 S Q U I S H  v2.2.0                     ##
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
# 1) BASIC CONFIG
# -----------------------------------------------------------

# Grid cell definitions.
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4

# Grid size: 40×25 cells, each cell is effectively 32×32 on screen.
GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE  # extra space for the status line

# Each code-page-437 glyph in the sprite sheet is 8×16 pixels.
# We scale them so that each glyph becomes 16×32 (2×2 scaling).
# Because each cell is 2 glyphs wide → 2×16=32 wide, and 1 glyph tall → 32 tall.
CHAR_WIDTH  = 8
CHAR_HEIGHT = 16
SCALE_X     = 2  # horizontal scale
SCALE_Y     = 2  # vertical scale

# The sprite sheet is assumed to have 16 columns × 16 rows = 256 glyphs (0–255).
SHEET_COLS  = 16
SHEET_ROWS  = 16

# We'll store references to our sprite sheet and sounds globally.
sprite_sheet = None
sounds = {}

# Lives for the player.
lives = 3

def cell_type(cell):
    """
    Return the numeric 'type' if cell is an integer or the first item
    if cell is a tuple. For example, (MOVEABLE_BLOCK, 2) => MOVEABLE_BLOCK.
    """
    if isinstance(cell, tuple):
        return cell[0]
    return cell

# -----------------------------------------------------------
# 2) CODE PAGE 437 GLYPHS for walls, blocks, player, enemies
# -----------------------------------------------------------

# We represent each cell with exactly two glyphs side by side:
# For example, a wall is "\xDB\xDB" = "██".
WALL_CHARS    = "\xDB\xDB"  # 0xDB = █
BLOCK0_CHARS  = "\xB0\xB0"  # 0xB0 = ░
BLOCK1_CHARS  = "\xB1\xB1"  # 0xB1 = ▒
BLOCK2_CHARS  = "\xB2\xB2"  # 0xB2 = ▓
PLAYER_CHARS  = "\x11\x10"  # 0x11 = ◄, 0x10 = ►
HUNTER_CHARS  = "\xC3\xB4"  # 0xC3 = ├, 0xB4 = ┤
EMPTY_CHARS   = "  "

def get_cell_string(cell):
    """
    Return the 2-glyph code-page-437 string for the given cell content.
    If it's a moveable block, check which block index (0,1,2).
    """
    t = cell_type(cell)
    if t == EMPTY:
        return EMPTY_CHARS
    elif t == PLAYER:
        return PLAYER_CHARS
    elif t == MOVEABLE_BLOCK:
        # cell might be (MOVEABLE_BLOCK, block_index).
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
# 3) SPRITE-SHEET TEXT RENDERING
# -----------------------------------------------------------

def load_sprite_sheet(filename):
    """Load the code-page-437 sprite sheet into sprite_sheet."""
    global sprite_sheet
    sprite_sheet = pygame.image.load(filename).convert_alpha()

def draw_char(surface, ch, x, y):
    """
    Draw a single code-page-437 character from the sprite sheet at (x,y).
    We'll compute which 8×16 sub-rectangle to copy, then scale it by 2×2.
    """
    code = ord(ch)
    if code < 0 or code > 255:
        code = 127  # fallback

    col = code % SHEET_COLS
    row = code // SHEET_COLS
    sx = col * CHAR_WIDTH
    sy = row * CHAR_HEIGHT
    char_rect = pygame.Rect(sx, sy, CHAR_WIDTH, CHAR_HEIGHT)

    # Copy that sub-rectangle into a small surface, then scale it.
    char_surf = pygame.Surface((CHAR_WIDTH, CHAR_HEIGHT), pygame.SRCALPHA)
    char_surf.blit(sprite_sheet, (0, 0), char_rect)

    scaled_w = CHAR_WIDTH  * SCALE_X
    scaled_h = CHAR_HEIGHT * SCALE_Y
    char_surf = pygame.transform.scale(char_surf, (scaled_w, scaled_h))

    surface.blit(char_surf, (x, y))

def draw_text(surface, text, x, y):
    """
    Draw a string of code-page-437 glyphs at (x,y), left to right,
    using draw_char for each glyph.
    """
    offset_x = 0
    for ch in text:
        draw_char(surface, ch, x + offset_x, y)
        offset_x += CHAR_WIDTH * SCALE_X

# -----------------------------------------------------------
# 4) DRAWING THE GRID
# -----------------------------------------------------------

def draw_grid(screen, grid):
    """
    Each cell is 2 glyphs wide, each glyph scaled to 16×32 => 32×32 cell.
    So for cell (x,y), we place the 2-glyph string at (x*32, y*32).
    """
    screen.fill((0,0,0))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            cell_str = get_cell_string(grid[y][x])
            # 2 glyphs wide => each glyph 16 wide => total 32
            px = x * (CHAR_WIDTH * SCALE_X * 2)
            py = y * (CHAR_HEIGHT * SCALE_Y)
            draw_text(screen, cell_str, px, py)

# -----------------------------------------------------------
# 5) STATUS LINE
# -----------------------------------------------------------

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters):
    """
    Draw a line of text at the bottom using 0xB3 (│) as the separator.
    Example: "Enemies: 3  │  Time: 00:16  │  Lives: 3  │  Score: 2 (0)"
    """
    elapsed_seconds = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed_seconds, 60)
    time_str = f"{minutes:02}:{seconds:02}"

    enemy_count = sum(1 for row in grid for cell in row if cell_type(cell) == ENEMY)
    level_score = (initial_hunters - enemy_count) * (2 * level)

    sep = chr(0xB3)  # 0xB3 = │
    status_text = (
        f"Enemies: {enemy_count}  {sep}  "
        f"Time: {time_str}  {sep}  "
        f"Lives: {lives}  {sep}  "
        f"Score: {level_score} ({cumulative_score})"
    )

    text_x = 5
    text_y = GRID_HEIGHT * (CHAR_HEIGHT * SCALE_Y) + (STATUS_HEIGHT - CHAR_HEIGHT * SCALE_Y)//2
    draw_text(screen, status_text, text_x, text_y)

# -----------------------------------------------------------
# 6) GAME LOGIC
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
    # Find enemies
    enemies = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                enemies.append((x,y))
    best_pos = None
    best_dist = -1
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            if cell_type(grid[y][x]) == EMPTY:
                dist = min(abs(x-ex)+abs(y-ey) for ex,ey in enemies) if enemies else 999
                if dist > best_dist:
                    best_dist = dist
                    best_pos = (x,y)
    if best_pos:
        grid[best_pos[1]][best_pos[0]] = PLAYER

def game_over_screen(screen):
    screen.fill((0,0,0))
    msg = "Game Over"
    w = len(msg)*CHAR_WIDTH*SCALE_X
    h = CHAR_HEIGHT*SCALE_Y
    # The total grid width is 2 glyphs per cell => 2*(CHAR_WIDTH*SCALE_X)*GRID_WIDTH
    total_w = GRID_WIDTH*(CHAR_WIDTH*SCALE_X)*2
    total_h = GRID_HEIGHT*(CHAR_HEIGHT*SCALE_Y)+STATUS_HEIGHT
    x = (total_w - w)//2
    y = (total_h - h)//2
    draw_text(screen, msg, x, y)
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
        respawn_player(grid)

def move_player_direction(grid, direction, stats, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid
    px, py = player_pos
    dx, dy = direction
    tx, ty = px+dx, py+dy
    t = cell_type(grid[ty][tx])
    if t == EMPTY:
        grid[py][px] = EMPTY
        grid[ty][tx] = PLAYER
    elif t == MOVEABLE_BLOCK:
        grid = push_blocks(grid, (px,py), direction, stats, screen)
    elif t == ENEMY:
        handle_collision(grid, screen)
    return grid

def push_blocks(grid, start_pos, direction, stats, screen):
    x, y = start_pos
    dx, dy = direction
    chain = []
    cx, cy = x+dx, y+dy
    while cell_type(grid[cy][cx]) == MOVEABLE_BLOCK:
        chain.append((cx,cy))
        cx += dx
        cy += dy
    t = cell_type(grid[cy][cx])
    if t == EMPTY:
        for bx,by in reversed(chain):
            grid[by+dy][bx+dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y+dy][x+dx] = PLAYER
        grid[y][x] = EMPTY
    elif t == ENEMY:
        nx, ny = cx+dx, cy+dy
        if cell_type(grid[ny][nx]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx,by in reversed(chain):
                grid[by+dy][bx+dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y+dy][x+dx] = PLAYER
            grid[y][x] = EMPTY
            stats['enemies_eliminated'] += 1
            sounds['squish'].play()
    return grid

def a_star_path(grid, start, goal):
    def heuristic(a,b):
        return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
    open_set = []
    heappush(open_set,(0,start))
    came_from={}
    g_score={start:0}
    f_score={start:heuristic(start,goal)}
    while open_set:
        _, current = heappop(open_set)
        if current==goal:
            path=[current]
            while current in came_from:
                current=came_from[current]
                path.append(current)
            path.reverse()
            return path
        for ddx in [-1,0,1]:
            for ddy in [-1,0,1]:
                if ddx==0 and ddy==0:
                    continue
                nx=current[0]+ddx
                ny=current[1]+ddy
                if not(0<=nx<GRID_WIDTH and 0<=ny<GRID_HEIGHT):
                    continue
                if (nx,ny)!=goal and cell_type(grid[ny][nx])!=EMPTY:
                    continue
                tg=g_score[current]+1
                if (nx,ny) in g_score and tg>=g_score[(nx,ny)]:
                    continue
                came_from[(nx,ny)]=current
                g_score[(nx,ny)]=tg
                f_score[(nx,ny)]=tg+heuristic((nx,ny),goal)
                heappush(open_set,(f_score[(nx,ny)],(nx,ny)))
    return []

def update_enemies(grid, move_accuracy, screen):
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid
    enemies=[]
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x])==ENEMY:
                enemies.append((x,y))
    collision_occurred=False
    for ex,ey in enemies:
        if collision_occurred:
            break
        path=a_star_path(grid,(ex,ey),player_pos)
        moved=False
        if len(path)>=2 and random.random()<(move_accuracy/100.0):
            nx,ny=path[1]
            t=cell_type(grid[ny][nx])
            if t==PLAYER:
                handle_collision(grid,screen)
                collision_occurred=True
                continue
            elif t==EMPTY:
                grid[ny][nx]=ENEMY
                grid[ey][ex]=EMPTY
                moved=True
        if not moved:
            mv = random.choice([(-1,-1),(0,-1),(1,-1),
                                (-1,0),        (1,0),
                                (-1,1),(0,1),(1,1)])
            nx=ex+mv[0]
            ny=ey+mv[1]
            if 0<=nx<GRID_WIDTH and 0<=ny<GRID_HEIGHT:
                t=cell_type(grid[ny][nx])
                if t==PLAYER:
                    handle_collision(grid,screen)
                    collision_occurred=True
                    continue
                elif t==EMPTY:
                    grid[ny][nx]=ENEMY
                    grid[ey][ex]=EMPTY
    return grid

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    """
    Clears the screen, shows summary lines, and waits for <space>.
    We'll just use sprite-based text for each line.
    """
    screen.fill((0,0,0))
    lines=[
        f"Level {level} Completed!",
        "",
        f"Enemies Eliminated: {enemies}",
        f"Moves Taken: {moves}",
        f"Time Taken: {time_taken} seconds",
        f"Score: {level_score}",
        f"Cumulative Score: {cumulative_score}",
        "Press <space> to continue"
    ]
    max_len=max(len(l) for l in lines)
    line_height=CHAR_HEIGHT*SCALE_Y+4
    total_w=GRID_WIDTH*(CHAR_WIDTH*SCALE_X)*2
    y=100
    for line in lines:
        lw=len(line)*CHAR_WIDTH*SCALE_X
        x=(total_w - lw)//2
        draw_text(screen,line,x,y)
        y+=line_height
    pygame.display.flip()
    waiting=True
    while waiting:
        for event in pygame.event.get():
            if event.type==QUIT:
                pygame.quit()
                sys.exit()
            elif event.type==KEYDOWN:
                if event.key==K_SPACE:
                    waiting=False
                elif event.key==K_ESCAPE:
                    pygame.quit()
                    sys.exit()

def get_level_params(level):
    """
    Return (hunters, move_speed, move_accuracy) for each level.
    This is your difficulty ramp.
    """
    if level==1:
        return (3,1000,50)
    elif level==2:
        return (4,1000,50)
    elif level==3:
        return (5,1000,50)
    elif level==4:
        return (6,1000,50)
    elif level==5:
        return (6,900,50)
    elif level==6:
        return (6,800,50)
    elif level==7:
        return (6,700,50)
    elif level==8:
        return (6,700,55)
    elif level==9:
        return (6,700,60)
    elif level==10:
        return (6,700,65)
    elif level==11:
        return (7,700,70)
    else:
        hunters=7+((level-11)//4)
        return (hunters,700,70)

def generate_level(num_enemies):
    """
    Create a 40×25 grid with random blocks,
    plus outer walls, plus a random set of enemies,
    plus the player far from the enemies.
    """
    grid=[[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    for x in range(GRID_WIDTH):
        grid[0][x]=UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT-1][x]=UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0]=UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH-1]=UNMOVEABLE_BLOCK
    for y in range(1,GRID_HEIGHT-1):
        for x in range(1,GRID_WIDTH-1):
            r=random.random()
            if r<0.01:
                grid[y][x]=UNMOVEABLE_BLOCK
            elif r<0.31:
                block_index=random.choice([0,1,2])
                grid[y][x]=(MOVEABLE_BLOCK,block_index)
    enemy_positions=[]
    while len(enemy_positions)<num_enemies:
        rx=random.randint(1,GRID_WIDTH-2)
        ry=random.randint(1,GRID_HEIGHT-2)
        if cell_type(grid[ry][rx])==EMPTY:
            grid[ry][rx]=ENEMY
            enemy_positions.append((rx,ry))
    best_pos=None
    best_dist=-1
    for yy in range(1,GRID_HEIGHT-1):
        for xx in range(1,GRID_WIDTH-1):
            if cell_type(grid[yy][xx])==EMPTY:
                dist=min(abs(xx-ex)+abs(yy-ey) for ex,ey in enemy_positions) if enemy_positions else 999
                if dist>best_dist:
                    best_dist=dist
                    best_pos=(xx,yy)
    if best_pos:
        grid[best_pos[1]][best_pos[0]]=PLAYER
    return grid

def play_level(level,screen,clock,cumulative_score):
    global lives
    hunters,move_speed,move_accuracy=get_level_params(level)
    initial_hunters=hunters
    grid=generate_level(hunters)
    stats={'moves':0,'enemies_eliminated':0}
    level_start_time=pygame.time.get_ticks()
    enemy_update_interval=move_speed
    last_enemy_update=pygame.time.get_ticks()

    while True:
        for event in pygame.event.get():
            if event.type==QUIT:
                pygame.quit()
                sys.exit()
            elif event.type==KEYDOWN:
                if event.key==K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key in (K_UP,K_DOWN,K_LEFT,K_RIGHT):
                    old_pos=get_player_position(grid)
                    if event.key==K_UP:
                        dir=(0,-1)
                    elif event.key==K_DOWN:
                        dir=(0,1)
                    elif event.key==K_LEFT:
                        dir=(-1,0)
                    elif event.key==K_RIGHT:
                        dir=(1,0)
                    grid=move_player_direction(grid,dir,stats,screen)
                    new_pos=get_player_position(grid)
                    if old_pos!=new_pos:
                        stats['moves']+=1

        current_time=pygame.time.get_ticks()
        if current_time-last_enemy_update>=enemy_update_interval:
            grid=update_enemies(grid,move_accuracy,screen)
            last_enemy_update=current_time

        draw_grid(screen,grid)
        draw_status_line(screen,grid,level_start_time,lives,level,cumulative_score,initial_hunters)
        pygame.display.flip()
        clock.tick(10)

        # Check if level is complete (no enemies).
        enemy_exists = any(cell_type(c)==ENEMY for row in grid for c in row)
        if not enemy_exists:
            break

    level_end_time=pygame.time.get_ticks()
    time_taken=(level_end_time-level_start_time)//1000
    stats['enemies_eliminated']=hunters
    level_score=stats['enemies_eliminated']*(2*level)
    return stats['moves'],stats['enemies_eliminated'],time_taken,level_score

def main():
    global lives
    pygame.init()
    # The window is 2 glyphs wide × 8 px each × scale_x=2 => 32 px per cell horizontally,
    # and 1 glyph tall × 16 px × scale_y=2 => 32 px per cell vertically.
    screen_w = GRID_WIDTH * (CHAR_WIDTH*SCALE_X) * 2
    screen_h = GRID_HEIGHT * (CHAR_HEIGHT*SCALE_Y) + STATUS_HEIGHT
    screen=pygame.display.set_mode((screen_w, screen_h))
    clock=pygame.time.Clock()

    # Load sprite sheet for code-page-437 glyphs.
    load_sprite_sheet("dos_spritesheet.png")

    # Load sounds.
    sounds['squish']    = pygame.mixer.Sound("squish.wav")
    sounds['collision'] = pygame.mixer.Sound("collision.wav")

    # Initialize game.
    cumulative_score=0
    level=1
    lives=3

    # Main loop
    while True:
        moves,enemies,time_taken,level_score=play_level(level,screen,clock,cumulative_score)
        cumulative_score+=level_score
        show_level_complete_screen(screen,level,moves,enemies,time_taken,level_score,cumulative_score)
        level+=1

if __name__=="__main__":
    main()
