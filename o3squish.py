import pygame, random, sys
from pygame.locals import *

# Define cell types
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
ENEMY = 4

# Grid and cell size configuration
CELL_SIZE = 32
GRID_WIDTH = 40
GRID_HEIGHT = 24

# Colors for drawing (for visualization)
COLORS = {
    EMPTY: (255, 255, 255),
    PLAYER: (0, 255, 0),
    MOVEABLE_BLOCK: (0, 0, 255),
    UNMOVEABLE_BLOCK: (128, 128, 128),
    ENEMY: (255, 0, 0)
}

def generate_level():
    # Create an empty grid
    grid = [[EMPTY for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    
    # Create outer walls (unmoveable blocks)
    for x in range(GRID_WIDTH):
        grid[0][x] = UNMOVEABLE_BLOCK
        grid[GRID_HEIGHT-1][x] = UNMOVEABLE_BLOCK
    for y in range(GRID_HEIGHT):
        grid[y][0] = UNMOVEABLE_BLOCK
        grid[y][GRID_WIDTH-1] = UNMOVEABLE_BLOCK
        
    # Fill interior cells with random blocks
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            r = random.random()
            if r < 0.01:
                grid[y][x] = UNMOVEABLE_BLOCK
            elif r < 0.01 + 0.30:
                grid[y][x] = MOVEABLE_BLOCK
            # else remain empty

    # Spawn enemies: here we use a fixed number (5) per level
    num_enemies = 5
    enemy_positions = []
    while len(enemy_positions) < num_enemies:
        x = random.randint(1, GRID_WIDTH-2)
        y = random.randint(1, GRID_HEIGHT-2)
        if grid[y][x] == EMPTY:
            grid[y][x] = ENEMY
            enemy_positions.append((x, y))
            
    # Spawn the player as far away from all enemies as possible
    best_pos = None
    best_distance = -1
    for y in range(1, GRID_HEIGHT-1):
        for x in range(1, GRID_WIDTH-1):
            if grid[y][x] == EMPTY:
                # Compute the minimum Manhattan distance from all enemies
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
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, COLORS[cell], rect)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1)  # draw cell borders

def move_player(grid, direction):
    # Find the player's current position
    player_pos = None
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            if grid[y][x] == PLAYER:
                player_pos = (x, y)
                break
        if player_pos:
            break
    if not player_pos:
        return grid

    dx, dy = direction
    target_x = player_pos[0] + dx
    target_y = player_pos[1] + dy
    
    # If target cell is empty, simply move the player
    if grid[target_y][target_x] == EMPTY:
        grid[player_pos[1]][player_pos[0]] = EMPTY
        grid[target_y][target_x] = PLAYER
    # If the target cell has a moveable block, attempt to push it
    elif grid[target_y][target_x] == MOVEABLE_BLOCK:
        grid = push_blocks(grid, player_pos, direction)
    # If the target cell is an unmoveable block or enemy (which acts like one), do nothing
    return grid

def push_blocks(grid, start_pos, direction):
    x, y = start_pos
    dx, dy = direction
    chain = []
    
    # Find the chain of consecutive moveable blocks in the push direction
    cur_x = x + dx
    cur_y = y + dy
    while grid[cur_y][cur_x] == MOVEABLE_BLOCK:
        chain.append((cur_x, cur_y))
        cur_x += dx
        cur_y += dy

    # Now (cur_x, cur_y) is the first cell beyond the chain.
    # If that cell is empty, we can push the whole chain.
    if grid[cur_y][cur_x] == EMPTY:
        # Push from the farthest block backward
        for pos in reversed(chain):
            bx, by = pos
            grid[by + dy][bx + dx] = MOVEABLE_BLOCK
            grid[by][bx] = EMPTY
        # Move the player into the first block's original cell
        grid[y + dy][x + dx] = PLAYER
        grid[y][x] = EMPTY
    # If an enemy is encountered at the end of the chain...
    elif grid[cur_y][cur_x] == ENEMY:
        # Check the cell beyond the enemy
        next_x = cur_x + dx
        next_y = cur_y + dy
        if grid[next_y][next_x] in [MOVEABLE_BLOCK, UNMOVEABLE_BLOCK]:
            # With a block or wall behind the enemy, it gets squished.
            grid[cur_y][cur_x] = MOVEABLE_BLOCK  # move block into enemy’s cell (squishing the enemy)
            for pos in reversed(chain):
                bx, by = pos
                grid[by + dy][bx + dx] = MOVEABLE_BLOCK
                grid[by][bx] = EMPTY
            grid[y + dy][x + dx] = PLAYER
            grid[y][x] = EMPTY
        else:
            # No block behind: treat enemy as unmoveable and do nothing.
            pass
    # If the cell is an unmoveable block (or any other obstacle), the push cannot be performed.
    return grid

def main():
    pygame.init()
    screen = pygame.display.set_mode((GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE))
    clock = pygame.time.Clock()
    
    grid = generate_level()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_UP:
                    grid = move_player(grid, (0, -1))
                elif event.key == K_DOWN:
                    grid = move_player(grid, (0, 1))
                elif event.key == K_LEFT:
                    grid = move_player(grid, (-1, 0))
                elif event.key == K_RIGHT:
                    grid = move_player(grid, (1, 0))
                    
        screen.fill((255, 255, 255))
        draw_grid(screen, grid)
        pygame.display.flip()
        clock.tick(10)  # adjust FPS as needed
    
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
