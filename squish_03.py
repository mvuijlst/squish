"""
#############################################################
##                                                         ##
##                  S Q U I S H  v.0.3                     ##
##                                                         ##
##              (c) 2024 Michel Vuijlsteke                 ##
##                                                         ##
#############################################################
"""

import curses
import random
import time
from collections import deque
import simpleaudio as sa

# Game constants
BLOCK_COVERAGE = 0.35
INITIAL_NUM_ENEMIES = 1
ENEMY_MOVE_DELAY = 10

# IDs for game elements
HERO_ID = 1
ENEMY_ID = 2
UNPUSHABLE_BLOCK_ID = 3
BLOCK_ID = 4  # Single ID for all movable blocks

# Character and color mapping
CHARACTER_MAP = {
    HERO_ID: "<>",
    ENEMY_ID: "├┤",
    UNPUSHABLE_BLOCK_ID: "▓▓",
}

MOVABLE_BLOCK_CHARACTERS = ['░░', '▒▒', '▓▓']  # Different characters for movable blocks

COLOR_MAP = {
    HERO_ID: curses.COLOR_CYAN,
    ENEMY_ID: curses.COLOR_RED,
    UNPUSHABLE_BLOCK_ID: curses.COLOR_YELLOW,
    BLOCK_ID: curses.COLOR_WHITE,
}

sounds = {
    'squish': sa.WaveObject.from_wave_file('squish.wav')
}

def init_colors():
    """Initialize color pairs."""
    curses.start_color()
    for color_id, color_value in COLOR_MAP.items():
        curses.init_pair(color_id, color_value, curses.COLOR_BLACK)

def play_sound(sound_name):
    """Play a preloaded sound."""
    sound = sounds.get(sound_name)
    if sound:
        sound.play()
    else:
        print(f"Error: Sound '{sound_name}' not found.")

def adjust_layout_for_width(stdscr):
    """Adjust for uneven width screen."""
    height, width = stdscr.getmaxyx()
    return height, width // 2  # Adjust width to account for double-width characters

def draw_border(stdscr, width, height, block_positions):
    """Draws a border around the playing field using unpushable block characters."""
    for x in range(width):
        stdscr.addstr(0, x * 2, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID], \
                      curses.color_pair(UNPUSHABLE_BLOCK_ID))
        stdscr.addstr(height - 1, x * 2, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID], \
                      curses.color_pair(UNPUSHABLE_BLOCK_ID))
        block_positions[(0, x)] = (UNPUSHABLE_BLOCK_ID, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID])
        block_positions[(height - 1, x)] = (UNPUSHABLE_BLOCK_ID, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID])

    for y in range(1, height - 1):
        stdscr.addstr(y, 0, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID], \
                      curses.color_pair(UNPUSHABLE_BLOCK_ID))
        stdscr.addstr(y, (width - 1) * 2, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID], \
                      curses.color_pair(UNPUSHABLE_BLOCK_ID))
        block_positions[(y, 0)] = (UNPUSHABLE_BLOCK_ID, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID])
        block_positions[(y, width - 1)] = (UNPUSHABLE_BLOCK_ID, CHARACTER_MAP[UNPUSHABLE_BLOCK_ID])


def place_blocks(field_width, field_height, block_coverage):
    """Places blocks on the playing field based on the coverage percentage."""
    total_positions = (field_width - 2) * (field_height - 2)
    num_blocks = int(total_positions * block_coverage)
    block_positions = {}

    while len(block_positions) < num_blocks:
        x = random.randint(1, field_width - 2)
        y = random.randint(1, field_height - 2)

        if (y, x) not in block_positions:
            # Assign a random character to this block
            character = random.choice(MOVABLE_BLOCK_CHARACTERS)
            block_positions[(y, x)] = (BLOCK_ID, character)

    return block_positions

def place_enemies(field_width, field_height, num_enemies, block_positions):
    """Places enemies randomly on the field, ensuring no overlap with blocks."""
    enemies = {}
    while len(enemies) < num_enemies:
        x = random.randint(1, field_width - 2)
        y = random.randint(1, field_height - 2)

        if (y, x) not in block_positions and (y, x) not in enemies:
            enemies[(y, x)] = ENEMY_ID

    return enemies

def can_push_blocks(block_positions, enemy_positions, \
                    start_y, start_x, dy, dx, field_width, field_height):
    """Checks if a series of blocks can be pushed in the given direction."""
    y, x = start_y, start_x

    while (y, x) in block_positions:
        y += dy
        x += dx

        if y < 1 or y >= field_height or x < 1 or x >= field_width:
            return False

        # Check if the block is unpushable
        block_id, _ = block_positions.get((y, x), (None, None))
        if block_id == UNPUSHABLE_BLOCK_ID:
            return False

        # Check if moving into an enemy
        if (y, x) in enemy_positions and (y + dy, x + dx) not in block_positions:
            return False

        if (y, x) in block_positions:
            continue

        return True

    return True

def push_blocks(block_positions, enemy_positions, start_y, start_x, dy, dx):
    """Pushes a series of blocks in a given direction and squishes enemies if appropriate."""
    blocks_to_move = []
    y, x = start_y, start_x
    squished_count = 0  # Counter for squished enemies

    while (y, x) in block_positions:
        next_y, next_x = y + dy, x + dx
        if (next_y, next_x) in enemy_positions and (next_y + dy, next_x + dx) in block_positions:
            squished_count += 1
            enemy_positions.pop((next_y, next_x))  # Remove the enemy from the game state
        blocks_to_move.append((y, x))
        y, x = next_y, next_x

    for y, x in reversed(blocks_to_move):
        new_y, new_x = y + dy, x + dx
        block_positions[(new_y, new_x)] = block_positions.pop((y, x))

    return squished_count


def bfs_distance_from_positions(field_width, field_height, positions):
    """Calculates the minimum distance from any of the given positions using BFS."""
    distances = [[-1 for _ in range(field_width)] for _ in range(field_height)]
    queue = deque()

    for (y, x) in positions:
        queue.append((y, x))
        distances[y][x] = 0

    while queue:
        y, x = queue.popleft()
        current_distance = distances[y][x]

        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < field_height and 0 <= nx < field_width and distances[ny][nx] == -1:
                distances[ny][nx] = current_distance + 1
                queue.append((ny, nx))

    return distances

def bfs_find_path(start, goal, field_width, field_height, occupied):
    """Find path to player."""
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
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
            return path

        for dy, dx in directions:
            ny, nx = current[0] + dy, current[1] + dx
            if 1 <= ny < field_height and 1 <= nx < field_width and (ny, nx) not in occupied:
                if (ny, nx) not in visited:
                    visited[(ny, nx)] = current
                    queue.append((ny, nx))

    return []

def bfs_farthest_from_enemies_and_walls(field_width, field_height, enemies, block_positions):
    """Finds the farthest position from enemies and walls using combined distances."""

    enemy_positions = list(enemies.keys())
    distances_from_enemies = bfs_distance_from_positions(field_width, field_height, enemy_positions)

    wall_positions = [(0, x) for x in range(field_width)] + \
                     [(field_height - 1, x) for x in range(field_width)] + \
                     [(y, 0) for y in range(field_height)] + \
                     [(y, field_width - 1) for y in range(field_height)]
    distances_from_walls = bfs_distance_from_positions(field_width, field_height, wall_positions)

    max_combined_distance = -1
    farthest_position = None
    occupied_positions = set(block_positions.keys()) | set(enemies.keys())

    for y in range(1, field_height - 1):
        for x in range(1, field_width - 1):
            if (y, x) not in occupied_positions:
                combined_distance = distances_from_enemies[y][x] + distances_from_walls[y][x]
                if combined_distance > max_combined_distance:
                    max_combined_distance = combined_distance
                    farthest_position = (y, x)

    return farthest_position

def move_enemies(enemies, hero_pos, field_width, field_height, block_positions, tick_count):
    """ Move enemies towards player """
    if tick_count % ENEMY_MOVE_DELAY != 0:
        return enemies

    new_positions = {}
    occupied = set(block_positions.keys()) | set(enemies.keys())

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for enemy_pos in list(enemies.keys()):
        path = bfs_find_path(enemy_pos, hero_pos, field_width, field_height, occupied)
        if path and len(path) > 1:
            next_pos = path[1]
            if next_pos not in occupied:
                new_positions[next_pos] = ENEMY_ID
            else:
                new_positions[enemy_pos] = ENEMY_ID  # Stay in place if path is blocked
        else:
            random.shuffle(directions)
            for dy, dx in directions:
                next_y, next_x = enemy_pos[0] + dy, enemy_pos[1] + dx
                if 1 <= next_y < field_height and 1 <= next_x < field_width and \
                        (next_y, next_x) not in occupied:
                    new_positions[(next_y, next_x)] = ENEMY_ID
                    break
            else:
                new_positions[enemy_pos] = ENEMY_ID  # Stay in place if no moves available

    return new_positions

def handle_input(stdscr):
    """Handles user input and returns the corresponding movement direction."""
    key = stdscr.getch()
    dy, dx = 0, 0
    if key == curses.KEY_UP:
        dy = -1
    elif key == curses.KEY_DOWN:
        dy = 1
    elif key == curses.KEY_LEFT:
        dx = -1
    elif key == curses.KEY_RIGHT:
        dx = 1
    elif key == ord('q'):
        return None
    return dy, dx

def update_hero_position(hero_pos, dy, dx, block_positions,
                         enemy_positions, field_width, field_height,
                         total_squished_enemies):
    """Updates the hero's position and handles block pushing and squishing."""
    pos_y, pos_x = hero_pos

    next_y = pos_y + dy
    next_x = pos_x + dx

    if next_x < 1 or next_x >= field_width or next_y < 1 or next_y >= field_height:
        return hero_pos

    if (next_y, next_x) in block_positions:
        if can_push_blocks(block_positions, enemy_positions, \
                           next_y, next_x, dy, dx, field_width, field_height):
            squished_this_turn = push_blocks(block_positions, enemy_positions,\
                                             next_y, next_x, dy, dx)
            total_squished_enemies += squished_this_turn
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
    stdscr.nodelay(False)
    stdscr.clear()
    stdscr.addstr(0, 0, f"Game Over! You lasted {int(duration)} seconds.")
    stdscr.addstr(1, 0, "Play again? (Y/N): ")
    stdscr.refresh()

    while True:
        response = stdscr.getch()
        if response in [ord('y'), ord('Y'), ord('n'), ord('N')]:
            break

    stdscr.nodelay(True)
    return response in [ord('y'), ord('Y')]

def render(stdscr, hero_pos, block_positions, enemies, width, height):
    """Renders the current state of the game."""
    stdscr.clear()
    height, width = adjust_layout_for_width(stdscr)
    draw_border(stdscr, width, height, block_positions)

    # Draw blocks
    for (y, x), (block_id, character) in block_positions.items():
        stdscr.addstr(y, x * 2, character, curses.color_pair(block_id))

    # Draw enemies
    for (y, x), enemy_id in enemies.items():
        stdscr.addstr(y, x * 2, CHARACTER_MAP[enemy_id], curses.color_pair(enemy_id))

    # Draw hero
    pos_y, pos_x = hero_pos
    stdscr.addstr(pos_y, pos_x * 2, CHARACTER_MAP[HERO_ID], curses.color_pair(HERO_ID))
    stdscr.refresh()

def update_game_state(enemies, squished_enemies):
    """Updates the game state by removing squished enemies."""
    for enemy_pos in squished_enemies:
        if enemy_pos in enemies:
            del enemies[enemy_pos]

def display_level_completion(width, height, level, squished_enemies_count, moves, time_taken):
    """Displays the level completion stats and waits for the spacebar to continue."""
    message_lines = [
        f"Level {level} Completed!",
        "",
        f"Enemies Eliminated: {squished_enemies_count}",
        f"Moves Taken: {moves}",
        f"Time Taken: {int(time_taken)} seconds",
        "",
        "Press <space> to continue"
    ]
    longest_line = max(len(line) for line in message_lines)
    message_height = len(message_lines) + 2
    message_width = longest_line + 4
    start_y = (height - message_height) // 2
    start_x = ((width * 2) - message_width) // 2  # Account for double width characters

    win = curses.newwin(message_height, message_width, start_y, start_x)
    win.border()
    for i, line in enumerate(message_lines):
        if i == 0:
            win.addstr(i + 1, (message_width - len(line)) // 2, line)
        else:
            win.addstr(i + 1, 2, line)
    win.refresh()

    while True:
        key = win.getch()
        if key == ord(' '):
            break
    win.clear()
    win.refresh()

def main(stdscr):
    """Main loop."""
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)

    init_colors()  # Initialize colors

    field_height, field_width = adjust_layout_for_width(stdscr)

    if field_height < 10 or field_width < 10:
        stdscr.addstr(0, 0, "Screen too small!")
        stdscr.refresh()
        stdscr.getch()
        return

    level = 1
    num_enemies = INITIAL_NUM_ENEMIES
    total_squished_enemies = 0

    while True:
        block_positions = place_blocks(field_width, field_height, BLOCK_COVERAGE)
        draw_border(stdscr, field_width, field_height, block_positions)

        enemies = place_enemies(field_width, field_height, num_enemies, block_positions)

        hero_pos = bfs_farthest_from_enemies_and_walls(field_width, field_height,
                                                       enemies, block_positions)

        if hero_pos is None:
            stdscr.addstr(0, 0, "Error: Unable to place hero at a valid position.")
            stdscr.refresh()
            stdscr.getch()
            return

        start_time = time.time()
        tick_count = 0
        moves = 0

        while enemies:
            render(stdscr, hero_pos, block_positions, enemies, field_width, field_height)

            if check_collision(hero_pos, enemies):
                duration = time.time() - start_time
                if not end_game(stdscr, duration):
                    return
                break

            dy, dx = handle_input(stdscr)
            if dy is None and dx is None:
                return

            new_hero_pos = update_hero_position(hero_pos, dy, dx, block_positions,
                                                enemies, field_width, field_height,
                                                total_squished_enemies)
            if new_hero_pos != hero_pos:
                moves += 1
                hero_pos = new_hero_pos

            enemies = move_enemies(enemies, hero_pos, field_width, field_height,
                                   block_positions, tick_count)

            update_game_state(enemies, block_positions)
            tick_count += 1

        # Level completed
        duration = time.time() - start_time
        render(stdscr, hero_pos, block_positions, enemies, field_width, field_height)
        display_level_completion(field_width, field_height, level,
                                 total_squished_enemies, moves, duration)

        # Increase difficulty for the next level
        level += 1
        num_enemies += 1

    stdscr.refresh()


curses.wrapper(main)
