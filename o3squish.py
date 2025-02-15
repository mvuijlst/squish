"""
#############################################################
##                                                         ##
##                 S Q U I S H  v2.1.2                     ##
##                                                         ##
##              (c) 2025 Michel Vuijlsteke                 ##
##                                                         ##
#############################################################
"""

import os
# Hide the Pygame support prompt.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame, random, sys
from pygame.locals import *
from heapq import heappush, heappop

# Define cell types.
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4

# Grid configuration: 40x25 cells; each cell is 32x32 pixels.
CELL_SIZE = 32
GRID_WIDTH = 40
GRID_HEIGHT = 25
# Additional status line height (one cell tall)
STATUS_HEIGHT = CELL_SIZE

def cell_type(cell):
    """Return the type of the cell (ignoring extra data)."""
    if isinstance(cell, tuple):
        return cell[0]
    return cell

# Global dictionaries for images and sounds.
images = {}
sounds = {}

# Global lives counter (player starts with 3 lives).
lives = 3

def get_level_params(level):
    """
    Returns (hunters, move_speed, move_accuracy) for the given level.
    - hunters: number of enemy hunters.
    - move_speed: enemy update interval in milliseconds.
    - move_accuracy: percentage chance an enemy will follow the A* path.
    """
    if level == 1:
        return 3, 1000, 50
    elif level == 2:
        return 4, 1000, 50
    elif level == 3:
        return 5, 1000, 50
    elif level == 4:
        return 6, 1000, 50
    elif level == 5:
        return 6, 900, 50
    elif level == 6:
        return 6, 800, 50
    elif level == 7:
        return 6, 700, 50
    elif level == 8:
        return 6, 700, 55
    elif level == 9:
        return 6, 700, 60
    elif level == 10:
        return 6, 700, 65
    elif level == 11:
        return 7, 700, 70
    else:
        hunters = 7 + ((level - 11) // 4)
        return hunters, 700, 70

def generate_level(num_enemies):
    """Generates and returns a new grid for the level, spawning num_enemies hunters."""
    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    
    # Create outer walls using wall.png.
    for x in range(GRID_WIDTH):
        grid[0][x] = UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT - 1][x] = UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0] = UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH - 1] = UNMOVEABLE_BLOCK
        
    # Fill interior cells with random blocks:
    # 1% chance for an unmoveable block, 30% chance for a moveable block.
    for y in range(1, GRID_HEIGHT - 1):
        for x in range(1, GRID_WIDTH - 1):
            r = random.random()
            if r < 0.01:
                grid[y][x] = UNMOVEABLE_BLOCK
            elif r < 0.01 + 0.30:
                block_index = random.choice([0, 1, 2])
                grid[y][x] = (MOVEABLE_BLOCK, block_index)
    
    # Spawn enemy hunters in random empty cells.
    enemy_positions = []
    while len(enemy_positions) < num_enemies:
        x = random.randint(1, GRID_WIDTH - 2)
        y = random.randint(1, GRID_HEIGHT - 2)
        if cell_type(grid[y][x]) == EMPTY:
            grid[y][x] = ENEMY
            enemy_positions.append((x, y))
    
    # Spawn the player as far away from all enemies as possible.
    best_pos = None
    best_distance = -1
    for y in range(1, GRID_HEIGHT - 1):
        for x in range(1, GRID_WIDTH - 1):
            if cell_type(grid[y][x]) == EMPTY:
                min_dist = min(abs(x - ex) + abs(y - ey) for ex, ey in enemy_positions) if enemy_positions else 1000
                if min_dist > best_distance:
                    best_distance = min_dist
                    best_pos = (x, y)
    if best_pos:
        px, py = best_pos
        grid[py][px] = PLAYER
    else:
        print("No valid position for player!")
    
    return grid

def draw_grid(screen, grid):
    """Draws the game grid (the top part) onto the screen."""
    screen.fill((0, 0, 0))
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            typ = cell_type(cell)
            pos = (x * CELL_SIZE, y * CELL_SIZE)
            if typ == PLAYER:
                screen.blit(images['player'], pos)
            elif typ == MOVEABLE_BLOCK:
                block_index = cell[1]
                screen.blit(images['block'][block_index], pos)
            elif typ == UNMOVEABLE_BLOCK:
                screen.blit(images['wall'], pos)
            elif typ == ENEMY:
                screen.blit(images['enemy'], pos)

def draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters):
    """
    Draws a status line at the bottom of the screen showing:
    Enemies: <current enemy count>  |  Time: <mm:ss>  |  Lives: <lives>  |  Score: <level score> (<cumulative score>)
    Uses the traditional IBM PC DOS font ("Terminal") at 24px.
    """
    elapsed_seconds = (pygame.time.get_ticks() - level_start_time) // 1000
    minutes, seconds = divmod(elapsed_seconds, 60)
    time_str = f"{minutes:02}:{seconds:02}"
    
    # Count current enemies.
    enemy_count = sum(1 for row in grid for cell in row if cell_type(cell) == ENEMY)
    # Compute level score as (initial enemies - current enemies) * (2 * level).
    level_score = (initial_hunters - enemy_count) * (2 * level)
    
    status_text = (
        f"Enemies: {enemy_count}  |  "
        f"Time: {time_str}  |  "
        f"Lives: {lives}  |  "
        f"Score: {level_score} ({cumulative_score})"
    )
    
    # Increase font size to 24 for better legibility.
    status_font = pygame.font.SysFont("Terminal", 24)
    text_surface = status_font.render(status_text, True, (255, 255, 255))
    
    # Position the status line in the bottom STATUS_HEIGHT pixels.
    text_y = GRID_HEIGHT * CELL_SIZE + (STATUS_HEIGHT - text_surface.get_height()) // 2
    screen.blit(text_surface, (5, text_y))

def get_player_position(grid):
    """Returns the (x,y) position of the player in the grid."""
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            if cell_type(grid[y][x]) == PLAYER:
                return (x, y)
    return None

def respawn_player(grid):
    """
    Removes any existing player marker from the grid and places the player
    as far away as possible from all enemies.
    """
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == PLAYER:
                grid[y][x] = EMPTY
    enemy_positions = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                enemy_positions.append((x, y))
    best_pos = None
    best_distance = -1
    for y in range(1, GRID_HEIGHT - 1):
        for x in range(1, GRID_WIDTH - 1):
            if cell_type(grid[y][x]) == EMPTY:
                min_dist = min(abs(x - ex) + abs(y - ey) for ex, ey in enemy_positions) if enemy_positions else 1000
                if min_dist > best_distance:
                    best_distance = min_dist
                    best_pos = (x, y)
    if best_pos:
        grid[best_pos[1]][best_pos[0]] = PLAYER
    return grid

def game_over_screen(screen):
    """Displays a Game Over screen and waits before quitting."""
    font = pygame.font.SysFont("Terminal", 48)
    screen.fill((0, 0, 0))
    text_surface = font.render("Game Over", True, (255, 0, 0))
    text_rect = text_surface.get_rect(
        center=(GRID_WIDTH * CELL_SIZE // 2, (GRID_HEIGHT * CELL_SIZE + STATUS_HEIGHT) // 2)
    )
    screen.blit(text_surface, text_rect)
    pygame.display.flip()
    pygame.time.wait(3000)

def handle_collision(grid, screen):
    """
    Called when the player collides with an enemy.
    Plays collision.wav, decrements lives, respawns the player,
    and if lives hit zero, shows Game Over.
    """
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
    """
    Attempts to move the player in the given direction.
    If the target cell is an enemy, a collision is triggered.
    """
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid

    dx, dy = direction
    target_x = player_pos[0] + dx
    target_y = player_pos[1] + dy

    target_cell = cell_type(grid[target_y][target_x])
    if target_cell == EMPTY:
        grid[player_pos[1]][player_pos[0]] = EMPTY
        grid[target_y][target_x] = PLAYER
    elif target_cell == MOVEABLE_BLOCK:
        grid = push_blocks(grid, player_pos, direction, stats, screen)
    elif target_cell == ENEMY:
        handle_collision(grid, screen)
    return grid

def push_blocks(grid, start_pos, direction, stats, screen):
    """
    Attempts to push a chain of moveable blocks.
    If a block is pushed into an enemy (with a block/wall behind), the enemy is squished,
    the squish sound is played, and stats are updated.
    """
    x, y = start_pos
    dx, dy = direction
    chain = []
    cur_x = x + dx
    cur_y = y + dy
    while cell_type(grid[cur_y][cur_x]) == MOVEABLE_BLOCK:
        chain.append((cur_x, cur_y))
        cur_x += dx
        cur_y += dy

    if cell_type(grid[cur_y][cur_x]) == EMPTY:
        for bx, by in reversed(chain):
            grid[by + dy][bx + dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y + dy][x + dx] = PLAYER
        grid[y][x] = EMPTY
    elif cell_type(grid[cur_y][cur_x]) == ENEMY:
        next_x = cur_x + dx
        next_y = cur_y + dy
        if cell_type(grid[next_y][next_x]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by + dy][bx + dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y + dy][x + dx] = PLAYER
            grid[y][x] = EMPTY
            stats['enemies_eliminated'] += 1
            sounds['squish'].play()
    return grid

def a_star_path(grid, start, goal):
    """
    Computes a path from start to goal using the A* algorithm.
    Returns a list of (x, y) positions (including start and goal)
    or an empty list if no path is found.
    A cell is considered passable if it is EMPTY or if it is the goal.
    """
    def heuristic(a, b):
        return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
    
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    
    while open_set:
        current_f, current = heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                neighbor = (current[0] + dx, current[1] + dy)
                if not (0 <= neighbor[0] < GRID_WIDTH and 0 <= neighbor[1] < GRID_HEIGHT):
                    continue
                if neighbor != goal and cell_type(grid[neighbor[1]][neighbor[0]]) != EMPTY:
                    continue
                tentative_g = g_score[current] + 1
                if neighbor in g_score and tentative_g >= g_score[neighbor]:
                    continue
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heappush(open_set, (f_score[neighbor], neighbor))
    return []

def update_enemies(grid, move_accuracy, screen):
    """
    Moves each enemy toward the player using A* pathfinding.
    With probability equal to move_accuracy, an enemy follows its computed path;
    otherwise, it picks a random move from the 8 directions.
    If an enemy attempts to move into the player's cell, a collision is triggered.
    """
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid

    enemy_positions = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                enemy_positions.append((x, y))
    
    collision_occurred = False
    for ex, ey in enemy_positions:
        if collision_occurred:
            break
        path = a_star_path(grid, (ex, ey), player_pos)
        moved = False
        if len(path) >= 2 and random.random() < (move_accuracy / 100.0):
            next_step = path[1]
            target = cell_type(grid[next_step[1]][next_step[0]])
            if target == PLAYER:
                handle_collision(grid, screen)
                collision_occurred = True
                continue
            elif target == EMPTY:
                grid[next_step[1]][next_step[0]] = ENEMY
                grid[ey][ex] = EMPTY
                moved = True
        if not moved:
            move = random.choice([
                (-1, -1), (0, -1), (1, -1),
                (-1,  0),          (1,  0),
                (-1,  1), (0,  1), (1,  1)
            ])
            new_x = ex + move[0]
            new_y = ey + move[1]
            if 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT:
                target = cell_type(grid[new_y][new_x])
                if target == PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif target == EMPTY:
                    grid[new_y][new_x] = ENEMY
                    grid[ey][ex] = EMPTY
    return grid

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    """
    Clears the screen and displays the level completion summary.
    Waits until the player presses the spacebar to continue.
    """
    font = pygame.font.SysFont("Terminal", 36)
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
    screen.fill((0, 0, 0))
    y = 100
    for line in lines:
        text_surface = font.render(line, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(GRID_WIDTH * CELL_SIZE // 2, y))
        screen.blit(text_surface, text_rect)
        y += 40
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

def play_level(level, screen, clock, cumulative_score):
    """
    Plays a single level.
    Returns the moves taken, number of enemies eliminated, time taken (seconds), and the level score.
    """
    hunters, move_speed, move_accuracy = get_level_params(level)
    initial_hunters = hunters  # Save initial enemy count.
    grid = generate_level(hunters)
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
                # We no longer call pygame.key.set_repeat(), so arrow keys won't auto-repeat.
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
        draw_status_line(screen, grid, level_start_time, lives, level, cumulative_score, initial_hunters)
        pygame.display.flip()
        clock.tick(10)
        
        enemy_exists = any(cell_type(cell) == ENEMY for row in grid for cell in row)
        if not enemy_exists:
            break

    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000  # in seconds
    stats['enemies_eliminated'] = hunters  
    level_score = stats['enemies_eliminated'] * (2 * level)
    return stats['moves'], stats['enemies_eliminated'], time_taken, level_score

def main():
    global lives
    pygame.init()
    # Removed the line: pygame.key.set_repeat(200, 50)
    
    screen = pygame.display.set_mode((GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE + STATUS_HEIGHT))
    clock = pygame.time.Clock()
    
    # Load images.
    images['player'] = pygame.image.load("player.png").convert_alpha()
    images['wall']   = pygame.image.load("wall.png").convert_alpha()
    images['enemy']  = pygame.image.load("hunter.png").convert_alpha()
    images['block']  = [
        pygame.image.load("block1.png").convert_alpha(),
        pygame.image.load("block2.png").convert_alpha(),
        pygame.image.load("block3.png").convert_alpha()
    ]
    images['player'] = pygame.transform.scale(images['player'], (CELL_SIZE, CELL_SIZE))
    images['wall']   = pygame.transform.scale(images['wall'], (CELL_SIZE, CELL_SIZE))
    images['enemy']  = pygame.transform.scale(images['enemy'], (CELL_SIZE, CELL_SIZE))
    for i in range(len(images['block'])):
        images['block'][i] = pygame.transform.scale(images['block'][i], (CELL_SIZE, CELL_SIZE))
    
    # Load sounds.
    sounds['squish'] = pygame.mixer.Sound("squish.wav")
    sounds['collision'] = pygame.mixer.Sound("collision.wav")
    
    cumulative_score = 0
    level = 1
    lives = 3  # Reset lives at game start.
    while True:
        moves, enemies, time_taken, level_score = play_level(level, screen, clock, cumulative_score)
        cumulative_score += level_score
        show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score)
        level += 1

if __name__ == '__main__':
    main()
