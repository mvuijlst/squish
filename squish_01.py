#############################################################
##                                                         ##
##                  S Q U I S H  v.0.1                     ##
##                                                         ##
##              (c) 2024 Michel Vuijlsteke                 ##
##                                                         ##
##                                                         ##
#############################################################



import curses
import random
import time
from collections import deque
import logging

# Set up logging configuration
logging.basicConfig(
    filename='game_debug.log',  # File to log to
    level=logging.DEBUG,  # Log level
    format='%(asctime)s - %(levelname)s - %(message)s'  # Log format
)


# Constants
BLOCK_COVERAGE = 0.35
NUM_ENEMIES = 5
HERO_CHAR = "<>"
BORDER_CHAR = '█'
BLOCK_CHARS = ['░░', '▒▒', '▓▓']
ENEMY_CHAR = "├┤"
ENEMY_MOVE_DELAY = 10

def adjust_layout_for_width(stdscr):
    height, width = stdscr.getmaxyx()
    if width % 2 != 0:
        width -= 1
    return height, width

def draw_border(stdscr, width, height):
    """Draws a border around the playing field using full block characters."""
    for x in range(width):
        stdscr.addch(0, x, BORDER_CHAR)
        stdscr.addch(height - 2, x, BORDER_CHAR)
    
    for y in range(1, height - 2):
        stdscr.addch(y, 0, BORDER_CHAR)
        stdscr.addch(y, 1, BORDER_CHAR)
        stdscr.addch(y, width - 1, BORDER_CHAR)
        stdscr.addch(y, width - 2, BORDER_CHAR)

def place_blocks(field_width, field_height, block_coverage):
    """Places blocks on the playing field based on the coverage percentage."""
    total_positions = ((field_width - 2) // 2) * (field_height - 1)
    num_blocks = int(total_positions * block_coverage)
    block_positions = {}

    while len(block_positions) < num_blocks:
        x = random.randint(1, (field_width - 2) // 2) * 2
        y = random.randint(1, field_height - 1)

        if (y, x) not in block_positions:
            block_positions[(y, x)] = random.choice(BLOCK_CHARS)

    return block_positions

def place_enemies(field_width, field_height, num_enemies, block_positions):
    """Places enemies randomly on the field, ensuring no overlap with blocks."""
    enemies = {}
    while len(enemies) < num_enemies:
        x = random.randint(1, (field_width // 2) - 2 ) * 2
        y = random.randint(1, field_height - 1)

        if (y, x) not in block_positions and (y, x) not in enemies:
            enemies[(y, x)] = ENEMY_CHAR

    return enemies

def can_push_blocks(block_positions, enemy_positions, start_y, start_x, dy, dx, field_width, field_height):
    """Checks if a series of blocks can be pushed in the given direction."""
    y, x = start_y, start_x

    while (y, x) in block_positions:
        y += dy
        x += dx

        # Check boundaries
        if y < 1 or y >= field_height or x < 2 or x >= field_width:
            return False

        # Check if the path is blocked by enemies not followed by a block (cannot squish)
        if (y, x) in enemy_positions and (y + dy, x + dx) not in block_positions:
            return False

        # If the next position is another block, continue checking
        if (y, x) in block_positions:
            continue

        # Path is clear to move
        return True

    # If we exit the loop, it means the entire path is clear
    return True

def push_blocks(block_positions, enemy_positions, start_y, start_x, dy, dx):
    """Pushes a series of blocks in a given direction and squishes enemies."""
    blocks_to_move = []
    y, x = start_y, start_x
    squished_enemies = []

    # Collect all blocks in the chain to be moved
    while (y, x) in block_positions:
        blocks_to_move.append((y, x))
        y += dy
        x += dx

    # Move blocks from last to first to avoid overwriting positions
    for y, x in reversed(blocks_to_move):
        new_y, new_x = y + dy, x + dx

        # Check if there's an enemy to be squished
        if (new_y, new_x) in enemy_positions and (new_y + dy, new_x + dx) in block_positions:
            squished_enemies.append((new_y, new_x))

        block_positions[(new_y, new_x)] = block_positions.pop((y, x))

    # Remove squished enemies
    for enemy_pos in squished_enemies:
        del enemy_positions[enemy_pos]

def bfs_distance_from_positions(field_width, field_height, positions):
    """Calculates the minimum distance from any of the given positions using BFS."""
    distances = [[-1 for _ in range(field_width)] for _ in range(field_height)]
    queue = deque()

    # Initialize distances and queue with given positions
    for (y, x) in positions:
        queue.append((y, x))
        distances[y][x] = 0

    # Perform BFS to compute distances
    while queue:
        y, x = queue.popleft()
        current_distance = distances[y][x]

        for dy, dx in [(-1, 0), (1, 0), (0, -2), (0, 2)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < field_height and 0 <= nx < field_width and distances[ny][nx] == -1:
                distances[ny][nx] = current_distance + 1
                queue.append((ny, nx))

    return distances

def bfs_find_path(start, goal, field_width, field_height, occupied):
    directions = [(-1, 0), (1, 0), (0, -2), (0, 2)]
    queue = deque([start])
    visited = {start: None}

    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            step = goal
            while step:
                path.append(step)
                step = visited[step]
            path.reverse()
            print(f"Path found from {start} to {goal}: {path}")  # Debugging output
            return path

        for dy, dx in directions:
            ny, nx = current[0] + dy, current[1] + dx
            if 1 <= ny < field_height and 2 <= nx < field_width and (ny, nx) not in occupied:
                if (ny, nx) not in visited:
                    visited[(ny, nx)] = current
                    queue.append((ny, nx))

    print(f"No path found from {start} to {goal}")  # Debugging output
    return []

def bfs_farthest_from_enemies_and_walls(field_width, field_height, enemies, block_positions):
    """Finds the farthest position from enemies and walls using combined distances."""
    logging.debug("Start farthest from enemies and walls")

    # Calculate distances from enemies
    enemy_positions = list(enemies.keys())
    distances_from_enemies = bfs_distance_from_positions(field_width, field_height, enemy_positions)

    # Calculate distances from walls (edges of the playing field)
    wall_positions = [(0, x) for x in range(field_width)] + [(field_height - 1, x) for x in range(field_width)] + \
                     [(y, 0) for y in range(field_height)] + [(y, field_width - 1) for y in range(field_height)]
    distances_from_walls = bfs_distance_from_positions(field_width, field_height, wall_positions)

    # Find the position with the maximum combined distance, avoiding occupied positions
    max_combined_distance = -1
    farthest_position = None
    occupied_positions = set(block_positions.keys()) | set(enemies.keys())

    for y in range(1, field_height - 1):
        for x in range(2, field_width - 2, 2):
            if (y, x) not in occupied_positions:
                combined_distance = distances_from_enemies[y][x] + distances_from_walls[y][x]
                if combined_distance > max_combined_distance:
                    max_combined_distance = combined_distance
                    farthest_position = (y, x)

    logging.debug("End farthest from enemies and walls")
    return farthest_position

def move_enemies(enemies, hero_pos, field_width, field_height, block_positions, tick_count):

    if tick_count % ENEMY_MOVE_DELAY != 0:
        return enemies  # Move enemies only every specified ticks

    new_positions = {}
    occupied = set(block_positions.keys()) | set(enemies.keys())  # Include both blocks and enemies as obstacles
    directions = [(-1, 0), (1, 0), (0, -2), (0, 2)]  # Possible movement directions

    for enemy_pos, _ in enemies.items():
        path = bfs_find_path(enemy_pos, hero_pos, field_width, field_height, occupied)
        if path and len(path) > 1:
            next_pos = path[1]  # Take the first step in the path
            new_positions[next_pos] = ENEMY_CHAR
        else:
            # Move randomly if no path to hero
            random.shuffle(directions)
            for dy, dx in directions:
                next_y, next_x = enemy_pos[0] + dy, enemy_pos[1] + dx
                # Ensure the random move is within the game bounds and not into obstacles
                if 1 <= next_y < field_height and 2 <= next_x < field_width - 2 and (next_y, next_x) not in occupied:
                    new_positions[(next_y, next_x)] = ENEMY_CHAR
                    break
            else:
                # If no valid random move, stay in place
                new_positions[enemy_pos] = ENEMY_CHAR

    return new_positions



def is_squished(enemy_pos, block_positions):
    x, y = enemy_pos
    # Check for horizontal squish
    squished_horizontally = (y, x - 2) in block_positions and (y, x + 2) in block_positions
    # Check for vertical squish
    squished_vertically = (y - 1, x) in block_positions and (y + 1, x) in block_positions
    return squished_horizontally or squished_vertically



def handle_input(stdscr):
    """Handles user input and returns the corresponding movement direction."""
    key = stdscr.getch()
    dy, dx = 0, 0
    if key == curses.KEY_UP:
        dy = -1
    elif key == curses.KEY_DOWN:
        dy = 1
    elif key == curses.KEY_LEFT:
        dx = -2
    elif key == curses.KEY_RIGHT:
        dx = 2
    elif key == ord('q'):
        return None
    return dy, dx

def update_hero_position(hero_pos, dy, dx, block_positions, enemy_positions, field_width, field_height):
    """Updates the hero's position and handles block pushing and squishing."""
    pos_y, pos_x = hero_pos

    next_y = pos_y + dy
    next_x = pos_x + dx

    # Boundary check for hero's movement
    if next_x < 2 or next_x >= field_width or next_y < 1 or next_y >= field_height:
        return hero_pos  # Stay in place if moving out of bounds

    # Check if hero can push blocks
    if (next_y, next_x) in block_positions:
        if can_push_blocks(block_positions, enemy_positions, next_y, next_x, dy, dx, field_width, field_height):
            push_blocks(block_positions, enemy_positions, next_y, next_x, dy, dx)
            pos_y += dy
            pos_x += dx
    elif (next_y, next_x) not in block_positions and (next_y, next_x) not in enemy_positions:
        pos_y += dy
        pos_x += dx

    return pos_y, pos_x


def check_collision(hero_pos, enemies):
    """Checks if the hero collides with any enemy."""
    return hero_pos in enemies



def end_game(stdscr, duration):
    """Displays the end game screen and asks if the player wants to restart."""
    stdscr.nodelay(False)  # Switch to blocking mode
    stdscr.clear()
    stdscr.addstr(0, 0, f"Game Over! You lasted {int(duration)} seconds.")
    stdscr.addstr(1, 0, "Play again? (Y/N): ")
    stdscr.refresh()

    # Wait for a valid response
    while True:
        response = stdscr.getch()  # Use getch to wait for input
        if response in [ord('y'), ord('Y'), ord('n'), ord('N')]:
            break

    stdscr.nodelay(True)  # Switch back to non-blocking mode
    return response in [ord('y'), ord('Y')]

def render(stdscr, hero_pos, block_positions, enemies, width, height):
    """Renders the current state of the game."""
    stdscr.clear()
    height, width = adjust_layout_for_width(stdscr)
    draw_border(stdscr, width, height)

    for (y, x), block in block_positions.items():
        stdscr.addstr(y, x, block)

    for (y, x), icon in enemies.items():
        stdscr.addstr(y, x, icon)

    pos_y, pos_x = hero_pos
    stdscr.addstr(pos_y, pos_x, HERO_CHAR)
    stdscr.refresh()

def update_game_state(enemies, block_positions):
    enemies_to_remove = []
    for enemy_pos in list(enemies.keys()):  # Convert to list to safely modify the dictionary during iteration
        if is_squished(enemy_pos, block_positions):
            enemies_to_remove.append(enemy_pos)
    
    for enemy_pos in enemies_to_remove:
        del enemies[enemy_pos]  # Remove squished enemies


def debug_info(tick_count, stdscr, message, row=0, col=0):
    """Logs debug information to both the screen and a file. 
    # Ensure the message fits in the screen width to avoid errors
    height, width = stdscr.getmaxyx()
    if row < height and col < width:
        stdscr.addstr(row, col, message[:width - col])  # Display on screen, truncate if necessary
        stdscr.refresh()
    if tick_count % ENEMY_MOVE_DELAY != 0:
        logging.debug(message)  # Log to file"""

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    height, width = stdscr.getmaxyx()
    if height < 10 or width < 20:
        stdscr.addstr(0, 0, "Screen too small!")
        stdscr.refresh()
        stdscr.getch()
        return

    field_width = width - 2
    field_height = height - 2

    # Initial placements
    block_positions = place_blocks(field_width, field_height, BLOCK_COVERAGE)
    enemies = place_enemies(field_width, field_height, 5, block_positions)

    # Place hero at the farthest point from enemies and walls, avoiding occupied positions
    hero_pos = bfs_farthest_from_enemies_and_walls(field_width, field_height, enemies, block_positions)

    # Ensure a valid position is found
    if hero_pos is None:
        print("Error: Unable to place hero at a valid position.")

    start_time = time.time()
    tick_count = 0

    debug_info(tick_count, stdscr, f"Initial Hero Pos: {hero_pos}", 1, 0)
    debug_info(tick_count, stdscr, f"Enemies: {list(enemies.keys())}", 2, 0)

    while True:
        render(stdscr, hero_pos, block_positions, enemies, width, height)

        # Log current positions before moves
        debug_info(tick_count, stdscr, f"Hero Pos: {hero_pos}", 3, 0)
        debug_info(tick_count, stdscr, f"Enemies Pos: {list(enemies.keys())}", 4, 0)

        if check_collision(hero_pos, enemies):
            duration = time.time() - start_time
            debug_info(tick_count, stdscr, f"Collision detected. Duration: {duration} seconds", 5, 0)
            if not end_game(stdscr, duration):
                return
            break

        dy, dx = handle_input(stdscr)
        if dy is None and dx is None:
            break

        # Log movement input
        debug_info(tick_count, stdscr, f"Move: dy={dy}, dx={dx}", 6, 0)

        hero_pos = update_hero_position(hero_pos, dy, dx, block_positions, enemies, field_width, field_height)

        # Log hero's new position
        debug_info(tick_count, stdscr, f"New Hero Pos: {hero_pos}", 7, 0)

        # Move enemies and log their new positions
        previous_enemy_positions = list(enemies.keys())  # Capture before move for comparison
        enemies = move_enemies(enemies, hero_pos, field_width, field_height, block_positions, tick_count)
        debug_info(tick_count, stdscr, f"Previous Enemies Pos: {previous_enemy_positions}", 8, 0)
        debug_info(tick_count, stdscr, f"New Enemies Pos: {list(enemies.keys())}", 9, 0)

        if check_collision(hero_pos, enemies):
            duration = time.time() - start_time
            debug_info(tick_count, stdscr, f"Collision detected after move. Duration: {duration} seconds", 10, 0)
            if not end_game(stdscr, duration):
                return
            break

        update_game_state(enemies, block_positions)

        tick_count += 1
        print(f"Tick count: {tick_count}")  


    stdscr.refresh()

curses.wrapper(main)
