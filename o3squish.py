"""
#############################################################
##                                                         ##
##                 S Q U I S H  v2.0.6                     ##
##                                                         ##
##              (c) 2025 Michel Vuijlsteke                 ##
##                                                         ##
#############################################################
"""

import pygame, random, sys
from pygame.locals import *

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

def cell_type(cell):
    """Return the type of the cell (ignoring extra data)."""
    if isinstance(cell, tuple):
        return cell[0]
    return cell

# Global dictionary to hold our images.
images = {}

def generate_level():
    """Generates and returns a new grid for the level."""
    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    
    # Create outer walls (unmoveable blocks) using wall.png.
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
                # For a moveable block, randomly choose one of three block images.
                block_index = random.choice([0, 1, 2])
                grid[y][x] = (MOVEABLE_BLOCK, block_index)
            # Otherwise, cell remains EMPTY.
    
    # Spawn enemies (5 per level) in random empty cells.
    num_enemies = 5
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
                # Use Manhattan distance.
                min_dist = min(abs(x - ex) + abs(y - ey) for ex, ey in enemy_positions)
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
    """Draws the grid onto the screen using scaled images."""
    screen.fill((0, 0, 0))
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            typ = cell_type(cell)
            pos = (x * CELL_SIZE, y * CELL_SIZE)
            if typ == PLAYER:
                screen.blit(images['player'], pos)
            elif typ == MOVEABLE_BLOCK:
                # cell is a tuple: (MOVEABLE_BLOCK, block_index)
                block_index = cell[1]
                screen.blit(images['block'][block_index], pos)
            elif typ == UNMOVEABLE_BLOCK:
                screen.blit(images['wall'], pos)
            elif typ == ENEMY:
                screen.blit(images['enemy'], pos)
    # (No grid lines are drawn; the background remains black.)

def get_player_position(grid):
    """Returns the (x,y) position of the player in the grid."""
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            if cell_type(grid[y][x]) == PLAYER:
                return (x, y)
    return None

def move_player(grid, direction, stats):
    """Attempts to move the player in the given direction."""
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid

    dx, dy = direction
    target_x = player_pos[0] + dx
    target_y = player_pos[1] + dy

    # If the target cell is empty, move the player.
    if cell_type(grid[target_y][target_x]) == EMPTY:
        grid[player_pos[1]][player_pos[0]] = EMPTY
        grid[target_y][target_x] = PLAYER
    # If the target cell has a moveable block, attempt to push it.
    elif cell_type(grid[target_y][target_x]) == MOVEABLE_BLOCK:
        grid = push_blocks(grid, player_pos, direction, stats)
    # If the target cell is a wall or enemy, do nothing.
    return grid

def push_blocks(grid, start_pos, direction, stats):
    """
    Attempts to push a chain of moveable blocks.
    If a block is pushed into an enemy and there is a block/wall beyond,
    the enemy is squished (and the stat is updated).
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

    # Case 1: The cell beyond the chain is EMPTY.
    if cell_type(grid[cur_y][cur_x]) == EMPTY:
        for bx, by in reversed(chain):
            grid[by + dy][bx + dx] = grid[by][bx]
            grid[by][bx] = EMPTY
        grid[y + dy][x + dx] = PLAYER
        grid[y][x] = EMPTY
    # Case 2: The cell beyond the chain contains an enemy.
    elif cell_type(grid[cur_y][cur_x]) == ENEMY:
        next_x = cur_x + dx
        next_y = cur_y + dy
        # Only squish the enemy if the cell beyond it is occupied by a block or wall.
        if cell_type(grid[next_y][next_x]) in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            for bx, by in reversed(chain):
                grid[by + dy][bx + dx] = grid[by][bx]
                grid[by][bx] = EMPTY
            grid[y + dy][x + dx] = PLAYER
            grid[y][x] = EMPTY
            stats['enemies_eliminated'] += 1
        else:
            # Enemy acts as an unmoveable block.
            pass
    return grid

def update_enemies(grid):
    """
    Moves each enemy toward the player with some randomness.
    Enemies now can move diagonally. Each enemy computes an optimal
    move (diagonal when appropriate) and with 70% probability takes that move;
    otherwise, it picks a random move from the 8 possible directions.
    Enemies move only into EMPTY cells.
    """
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid

    player_x, player_y = player_pos
    enemy_positions = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if cell_type(grid[y][x]) == ENEMY:
                enemy_positions.append((x, y))
    
    for ex, ey in enemy_positions:
        # Calculate optimal move using sign differences (allowing diagonal).
        dx = 1 if player_x > ex else -1 if player_x < ex else 0
        dy = 1 if player_y > ey else -1 if player_y < ey else 0
        optimal_move = (dx, dy)
        # With 70% probability, choose the optimal move.
        if random.random() < 0.7:
            move = optimal_move
        else:
            # Otherwise choose randomly among all eight possible directions.
            move = random.choice([
                (-1, -1), (0, -1), (1, -1),
                (-1,  0),          (1,  0),
                (-1,  1), (0,  1), (1,  1)
            ])
        new_x = ex + move[0]
        new_y = ey + move[1]
        if cell_type(grid[new_y][new_x]) == EMPTY:
            grid[new_y][new_x] = ENEMY
            grid[ey][ex] = EMPTY
    return grid

def show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score):
    """
    Clears the screen and displays the level completion summary.
    Waits until the player presses the spacebar to continue.
    """
    font = pygame.font.SysFont(None, 36)
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

def play_level(level, screen, clock):
    """
    Plays a single level. Returns the moves taken, number of enemies
    eliminated, time taken (in seconds), and the level score.
    """
    grid = generate_level()
    stats = {'moves': 0, 'enemies_eliminated': 0}
    level_start_time = pygame.time.get_ticks()
    
    # Ramp up enemy movement speed: level 1 = 1000ms; decrease by 100ms per level,
    # but never less than 250ms.
    enemy_update_interval = max(250, 1000 - (level - 1) * 100)
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
                # The arrow keys now repeat due to key repeat being enabled.
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
                    grid = move_player(grid, direction, stats)
                    new_pos = get_player_position(grid)
                    if old_pos != new_pos:
                        stats['moves'] += 1
        
        current_time = pygame.time.get_ticks()
        if current_time - last_enemy_update >= enemy_update_interval:
            grid = update_enemies(grid)
            last_enemy_update = current_time
        
        draw_grid(screen, grid)
        pygame.display.flip()
        clock.tick(10)
        
        # Check if the level is complete (no enemies left).
        enemy_exists = any(cell_type(cell) == ENEMY for row in grid for cell in row)
        if not enemy_exists:
            break

    level_end_time = pygame.time.get_ticks()
    time_taken = (level_end_time - level_start_time) // 1000  # in seconds

    # For now, we know 5 enemies were spawned per level.
    stats['enemies_eliminated'] = 5  
    level_score = stats['enemies_eliminated'] * (2 * level)
    
    return stats['moves'], stats['enemies_eliminated'], time_taken, level_score

def main():
    pygame.init()
    # Enable key repeat: delay 200ms, then every 50ms.
    pygame.key.set_repeat(200, 50)
    screen = pygame.display.set_mode((GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE))
    clock = pygame.time.Clock()
    
    global images
    # Load images.
    images['player'] = pygame.image.load("player.png").convert_alpha()
    images['wall']   = pygame.image.load("wall.png").convert_alpha()
    images['enemy']  = pygame.image.load("hunter.png").convert_alpha()
    images['block']  = [
        pygame.image.load("block1.png").convert_alpha(),
        pygame.image.load("block2.png").convert_alpha(),
        pygame.image.load("block3.png").convert_alpha()
    ]
    # Scale images from 16x16 to 32x32 pixels.
    images['player'] = pygame.transform.scale(images['player'], (CELL_SIZE, CELL_SIZE))
    images['wall']   = pygame.transform.scale(images['wall'], (CELL_SIZE, CELL_SIZE))
    images['enemy']  = pygame.transform.scale(images['enemy'], (CELL_SIZE, CELL_SIZE))
    for i in range(len(images['block'])):
        images['block'][i] = pygame.transform.scale(images['block'][i], (CELL_SIZE, CELL_SIZE))
    
    cumulative_score = 0
    level = 1
    while True:
        moves, enemies, time_taken, level_score = play_level(level, screen, clock)
        cumulative_score += level_score
        show_level_complete_screen(screen, level, moves, enemies, time_taken, level_score, cumulative_score)
        level += 1

if __name__ == '__main__':
    main()
