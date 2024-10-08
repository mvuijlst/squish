"""
#############################################################
##                                                         ##
##                 S Q U I S H  v.1.2.0                    ##
##                                                         ##
##              (c) 2024 Michel Vuijlsteke                 ##
##                                                         ##
#############################################################
"""

import curses
import random
import time
import hashlib
import datetime
import base64
from collections import deque
import sys

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'True'
import pygame


def get_resource_path(relative_path):
    """ Get the absolute path to the resource, works for both development and PyInstaller packaging. """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def debug(msg):
    """General-purpose debuging"""
    with open("debug.log", "a", encoding="cp437") as log_file:
        log_file.write(msg)

class Game:
    """
    A class representing the game.
    """
    BLOCK_COVERAGE = 0.30
    UNMOVABLE_BLOCKS = 0.01
    INITIAL_NUM_ENEMIES = 1
    NUM_EGGS = 3
    HUNTER_MOVE_DELAY = 1000

    HATCHING_TIME = 30  # Time after which eggs begin to hatch
    CRUSHER_RADIUS = 10  # CRUSHERs activate when within this radius of the hero

    HERO = 1
    HUNTER = 2
    WALL = 3
    BLOCK = 4
    EGG = 5
    CRUSHER = 6
    SENTINEL = 7

    CHARACTER_MAP = {
        HERO: "◄►",
        HUNTER: "├┤",
        WALL: "██",
        EGG: "○○",
        CRUSHER: "╬╬",
        SENTINEL: "╟╢"
    }

    MOVABLE_BLOCK_CHARACTERS = ['░░', '▒▒' ]  # Different characters for movable blocks

    """
    CHARACTER_MAP = {
        HERO: "<>",
        HUNTER: "HH",
        WALL: "WW",
        EGG: "ee",
        CRUSHER: "CC",
        SENTINEL: "SS"
    }

    MOVABLE_BLOCK_CHARACTERS = ['bB', 'Bb' ]  
    """

    COLOR_MAP = {
        HERO: curses.COLOR_CYAN,
        HUNTER: curses.COLOR_RED,
        WALL: curses.COLOR_YELLOW,
        BLOCK: curses.COLOR_WHITE,
        EGG: curses.COLOR_MAGENTA,
        CRUSHER: curses.COLOR_RED,
        SENTINEL: curses.COLOR_GREEN,
    }

    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.height, self.width = stdscr.getmaxyx()
        self.width //= 2
        self.hero_pos = (self.height // 2, self.width // 4)
        self.block_positions = {}
        self.enemy_positions = {}
        self.egg_positions = {}
        self.hatching_times = {}
        self.level = 1
        self.lives = 2  # hero lives
        self.total_squished_enemies = 0
        self.moves = 0
        self.score = 0
        self.rank = 0
        self.start_time = time.time()
        self.paused = False
        self.paused_time = 0  # Time spent in paused state
        self.last_pause_time = None  # Time when the game was paused
        self.last_move_time = 0
        self.move_cooldown = 0 # minimum time between hero moves (set to 0.1 for controller)
        self.init_game()


    def init_game(self):
        """Initialise game"""
        self.init_pygame()
        self.init_colors()
        self.place_walls()
        self.place_blocks()
        self.place_enemies()
        self.check_positions()
        self.hero_pos = self.find_farthest_position()
        self.render()
        self.respawn_animation()

    # Debugging code to verify placements
    def check_positions(self):
        """Verify that no enemies or eggs are placed in walls."""
        for pos in self.egg_positions.keys():
            if pos in self.block_positions:
                debug(f"Error: Egg generated in a wall at {pos}!")
        for pos in self.enemy_positions.keys():
            if pos in self.block_positions:
                debug(f"Error: Enemy generated in a wall at {pos}!")


    def init_pygame(self):
        """Initialise pygame stuff"""
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
        else:
            self.joystick = None

        pygame.mixer.init()
        self.sounds = {
            "squish": pygame.mixer.Sound(get_resource_path("squish.wav")),
            "collision": pygame.mixer.Sound(get_resource_path("collision.wav")),
        }

    def init_colors(self):
        """Initialise color pairs dynamically based on the COLOR_MAP."""
        curses.start_color()
        for color_id, color in self.COLOR_MAP.items():
            curses.init_pair(color_id, color, curses.COLOR_BLACK)

    def place_walls(self):
        """Place unmovable border blocks"""
        for x in range(self.width):  
            self.block_positions[(0, x)] = self.CHARACTER_MAP[self.WALL]  
            self.block_positions[(self.height-1, x)] = self.CHARACTER_MAP[self.WALL]
        for y in range(self.height):  # Include the last row
            self.block_positions[(y, 0)] = self.CHARACTER_MAP[self.WALL]
            self.block_positions[(y, self.width-1)] = self.CHARACTER_MAP[self.WALL]  # Use self.width-1 for correct indexing

        debug(f"Block positions: {sorted(self.block_positions.keys())}\n")


    def place_blocks(self):
        """Randomly places movable and unmovable blocks on the grid with a border of unmovable blocks."""
        max_x = self.width - 2  # -2 to exclude the rightmost border
        max_y = self.height - 2  # -2 to exclude the bottom border

        # Calculate the total number of internal cells
        total_internal_cells = max_x * max_y

        # Calculate number of movable and unmovable blocks to place
        num_movable_blocks = int(total_internal_cells * self.BLOCK_COVERAGE)
        num_unmovable_blocks = int(total_internal_cells * self.UNMOVABLE_BLOCKS)

        # Generate all internal positions (excluding borders)
        internal_positions = [(y, x) for y in range(1, max_y + 1) for x in range(1, max_x + 1)]

        # Randomly select positions for movable blocks
        movable_block_positions = random.sample(internal_positions, num_movable_blocks)
        for pos in movable_block_positions:
            self.block_positions[pos] = random.choice(self.MOVABLE_BLOCK_CHARACTERS)

        # Remove the chosen positions from internal positions
        remaining_positions = set(internal_positions) - set(movable_block_positions)

        # Convert remaining positions set to a list for random.sample
        unmovable_block_positions = random.sample(list(remaining_positions), num_unmovable_blocks)
        for pos in unmovable_block_positions:
            self.block_positions[pos] = self.CHARACTER_MAP[self.WALL]


    def place_enemies(self):
        """Randomly places enemies and eggs within the bounds of the playing field, ensuring they are not in walls or block positions."""
        self.enemy_positions = {}
        self.egg_positions = {}
        self.hatching_times = {}

        # Define the playable area excluding borders
        max_x = self.width - 2  # Exclude right border
        max_y = self.height - 2  # Exclude bottom border

        # Generate a set of all internal positions (excluding borders)
        all_positions = {(y, x) for y in range(1, max_y + 1) for x in range(1, max_x + 1)}

        # Create a set of blocked positions (walls, unmovable blocks, etc.)
        blocked_positions = set(self.block_positions.keys())

        # Double-check blocked positions for correct setup
        debug(f"Total blocked positions: {len(blocked_positions)}")
        debug(f"Blocked positions: {sorted(blocked_positions)}")

        # Available positions are all internal positions minus any blocked positions
        free_positions = all_positions - blocked_positions

        # If there are not enough free positions, return early
        if len(free_positions) < (self.NUM_EGGS + self.level + self.INITIAL_NUM_ENEMIES):
            debug("Warning: Not enough free positions to place all enemies and eggs.")
            return

        # Randomly place eggs in the available free positions
        egg_positions = random.sample(list(free_positions), self.NUM_EGGS)  # Convert set to list
        for pos in egg_positions:
            self.egg_positions[pos] = self.CHARACTER_MAP[self.EGG]
            self.hatching_times[pos] = time.time() + self.HATCHING_TIME
            self.enemy_positions[pos] = self.CHARACTER_MAP[self.EGG]  # Track as an "egg enemy"
        
        # Remove egg positions from free positions
        free_positions -= set(egg_positions)

        # Calculate the number of remaining enemies to place
        num_enemies = self.level + self.INITIAL_NUM_ENEMIES

        # Randomly place remaining enemies in the updated free positions
        enemy_positions = random.sample(list(free_positions), num_enemies)  # Convert set to list
        for pos in enemy_positions:
            self.enemy_positions[pos] = self.CHARACTER_MAP[self.HUNTER]

        # Run consistency check to validate placements
        self.check_positions()  # Call the new diagnostic function



    def find_hero_start_position(self):
        """Find a suitable starting position for the hero."""
        return (self.height // 2, self.width // 4)

    def calculate_distances(self, start_positions):
        """Calculate the distance from all start positions using BFS."""
        distances = [[-1 for _ in range(self.width)] for _ in range(self.height)]
        queue = deque()

        for pos in start_positions:
            queue.append(pos)
            distances[pos[0]][pos[1]] = 0

        while queue:
            y, x = queue.popleft()
            current_distance = distances[y][x]

            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.height and 0 <= nx < self.width and distances[ny][nx] == -1:
                    distances[ny][nx] = current_distance + 1
                    queue.append((ny, nx))

        return distances

    def find_farthest_position(self):
        """Find the position farthest from any HUNTER or block, with enemies weighted more heavily."""
        # Occupied positions include both enemies and blocks
        occupied_positions = list(self.enemy_positions.keys()) + list(self.block_positions.keys())
        distances = self.calculate_weighted_distances(occupied_positions)
        
        max_distance = -1
        farthest_position = None

        for y in range(self.height):
            for x in range(self.width):
                if distances[y][x] > max_distance and (y, x) not in self.block_positions and (y, x) not in self.enemy_positions:
                    max_distance = distances[y][x]
                    farthest_position = (y, x)

        return farthest_position

    def calculate_weighted_distances(self, occupied_positions):
        """Calculate a weighted distance from all occupied positions using BFS, giving more weight to enemies."""
        # Initialise distances
        distances = [[float('inf') for _ in range(self.width+1)] for _ in range(self.height+1)]
       
        queue = deque()

        # Start BFS from all occupied positions
        for pos in occupied_positions:
            if pos in self.enemy_positions:
                weight = 100  # Give higher weight to enemies
            else:
                weight = 1  # Standard weight for blocks
            queue.append((pos[0], pos[1], 0, weight))  # (y, x, distance, weight)
            distances[pos[0]][pos[1]] = 0

        while queue:
            y, x, current_distance, current_weight = queue.popleft()

            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.height and 0 <= nx < self.width:
                    new_distance = current_distance + current_weight
                    if new_distance < distances[ny][nx]:
                        distances[ny][nx] = new_distance
                        queue.append((ny, nx, new_distance, current_weight))

        return distances


    def main_loop(self):
        """Main game loop with strict HUNTER movement delay."""
        try:
            last_hunter_move_time = time.time()
            last_hatch_check_time = time.time()  # Add this to check egg hatching

            self.stdscr.nodelay(True)  # Non-blocking getch()

            while True:
                current_time = time.time()

                # Render the current state (without options line)
                self.render()

                # Handle input without blocking the loop
                if self.handle_input():
                    break

                # Strictly check if it's time to move the enemies
                time_since_last_move = current_time - last_hunter_move_time
                if time_since_last_move >= self.HUNTER_MOVE_DELAY / 1000.0:
                    self.move_enemies()
                    last_hunter_move_time = current_time  # Reset the timer

                # Check if it's time to check egg hatching
                time_since_last_hatch_check = current_time - last_hatch_check_time
                if time_since_last_hatch_check >= 1.0:  # Check hatching every second
                    self.hatch_eggs()
                    last_hatch_check_time = current_time

                # Update game state (e.g., collisions, etc.)
                self.update_game_state()

                # Check if the level is completed (no more enemies or eggs)
                if not self.enemy_positions: # and not self.egg_positions:
                    duration = time.time() - self.start_time
                    if not self.display_level_completion(duration):
                        break  # Player chose to exit
                    self.level += 1
                    self.init_game()  # Start a new level

                # Short sleep to avoid maxing out CPU
                time.sleep(0.01)

        except Exception as e:
            debug(f"Exception in main loop: {e}\n")

    def hatch_eggs(self):
        """Handle the hatching process for all eggs."""
        current_time = time.time()
        new_crushers = {}

        for pos, hatch_time in list(self.hatching_times.items()):
            if current_time >= hatch_time:
                random_hatch_time = random.uniform(0, self.HATCHING_TIME)
                if current_time >= hatch_time + random_hatch_time:
                    # Check if the egg is still present before attempting to hatch it
                    if pos in self.egg_positions:
                        # Transform the egg into a CRUSHER
                        new_crushers[pos] = self.CHARACTER_MAP[self.CRUSHER]

        # Update the positions
        for pos, crusher in new_crushers.items():
            if pos in self.egg_positions:  # Double check that the egg is still there
                self.egg_positions.pop(pos)
                self.enemy_positions[pos] = crusher

        # Remove hatched eggs from the hatching_times dictionary
        self.hatching_times = {pos: hatch_time for pos, hatch_time in self.hatching_times.items() if pos not in new_crushers}

    def remove_position(self, pos):
        """Remove a position from both HUNTER and egg lists safely."""
        if pos in self.enemy_positions:
            self.enemy_positions.pop(pos)
        if pos in self.egg_positions:
            self.egg_positions.pop(pos)
    
    def any_enemies_left(self):
        """Check if there are any enemies left on the field, including eggs and CRUSHERs."""
        for char in self.enemy_positions.items():
            if char in (self.CHARACTER_MAP[self.HUNTER], self.CHARACTER_MAP[self.EGG], self.CHARACTER_MAP[self.CRUSHER]):
                return True
        return False

    def render(self, show_options=False):
        """Renders the game state to the screen using characters from CHARACTER_MAP."""

        self.stdscr.clear()

        # Display blocks
        for pos, char in self.block_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.WALL if char == self.CHARACTER_MAP[self.WALL] else self.BLOCK))

        # Display enemies, including eggs and CRUSHERs
        for pos, char in self.enemy_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                if char == self.CHARACTER_MAP[self.CRUSHER]:
                    self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.CRUSHER], curses.color_pair(self.CRUSHER))
                elif char == self.CHARACTER_MAP[self.EGG]:
                    self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.EGG], curses.color_pair(self.EGG))
                else:
                    self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.HUNTER], curses.color_pair(self.HUNTER))

        # Display hero
        if 0 <= self.hero_pos[0] < self.height - 2 and 0 <= self.hero_pos[1] < self.width:
            self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO], curses.color_pair(self.HERO))

        # Draw the unbreakable block line above the status line
        for x in range(self.width):
            self.stdscr.addstr(self.height - 3, x * 2, self.CHARACTER_MAP[self.WALL], curses.color_pair(self.WALL))

        # Calculate if there's room for the status line
        elapsed_time = int(self.paused_time + (time.time() - self.start_time) if not self.paused else self.paused_time)
        minutes = elapsed_time // 60
        seconds = elapsed_time % 60
        hunter_count = len(self.enemy_positions)
        status_line = f"Enemies: {hunter_count}  |  Time: {minutes:02}:{seconds:02}  |  Lives: {self.lives}  |  Score: {self.score} ({self.rank})"

        # Print status line in the last line of the available screen space
        self.stdscr.addstr(self.height - 2, 0, status_line.ljust(self.width * 2))

        # Calculate if there's room for the options line and print it
        if show_options:
            options_line = "<space> = continue | s = Scores | q = Exit"
            self.stdscr.addstr(self.height - 1, 0, options_line.ljust(self.width * 2))

        self.stdscr.refresh()


    def handle_input(self):
        """Processes player input."""
        key = self.stdscr.getch()
        move_y, move_x = 0, 0
        current_time = time.time()


        keys = set()
        
        # Add a delay to allow time for pressing multiple keys
        start_time = time.time()
        while key != -1 and (time.time() - start_time) < 0.05:  # 0.05 seconds delay
            keys.add(key)
            key = self.stdscr.getch()
            time.sleep(0.01)  # Adding a slight delay to capture multiple key presses


        if curses.KEY_UP in keys and curses.KEY_LEFT in keys:
            move_y, move_x = -1, -1
        elif curses.KEY_UP in keys and curses.KEY_RIGHT in keys:
            move_y, move_x = -1, 1
        elif curses.KEY_DOWN in keys and curses.KEY_LEFT in keys:
            move_y, move_x = 1, -1
        elif curses.KEY_DOWN in keys and curses.KEY_RIGHT in keys:
            move_y, move_x = 1, 1
        elif curses.KEY_UP in keys:
            move_y = -1
        elif curses.KEY_DOWN in keys:
            move_y = 1
        elif curses.KEY_LEFT in keys:
            move_x = -1
        elif curses.KEY_RIGHT in keys:
            move_x = 1
        elif 27 in keys:
            self.pause_game()
        elif ord('q') in keys:
            self.confirm_quit() 

        if self.joystick:
            pygame.event.pump()  # Process controller events

            # Left stick for movement
            axis_x = self.joystick.get_axis(0)
            axis_y = self.joystick.get_axis(1)

            # Implementing a dead zone
            dead_zone = 0.2
            if abs(axis_y) > dead_zone or abs(axis_x) > dead_zone:
                if axis_y < -0.5:
                    move_y -= 1
                elif axis_y > 0.5:
                    move_y += 1
                if axis_x < -0.5:
                    move_x -= 1
                elif axis_x > 0.5:
                    move_x += 1

            # Handle button press for pause or quit
            if self.joystick.get_button(7):  # Start button for pause
                self.pause_game()
            elif self.joystick.get_button(6):  # Back button for quit
                return True  # Quit the game

        # Only move the hero if enough time has passed since the last move
        if (move_y != 0 or move_x != 0) and (current_time - self.last_move_time > self.move_cooldown):
            self.move_hero(move_y, move_x)
            self.last_move_time = current_time  # Update the last move time
        
        return False

    def pause_game(self):
        """Pause the game and display options."""
        self.last_pause_time = time.time()  # Record the time when the game was paused
        while True:
            # Render the game with the options line shown
            self.render(show_options=True)

            key = self.stdscr.getch()
            if key == ord(' '):  # Space to continue
                # Adjust the paused time
                self.paused_time += time.time() - self.last_pause_time
                self.last_pause_time = None
                return  # Continue the game
            elif key == ord('s'):  
                self.display_high_scores()  # Show high scores
            elif key == ord('q'):  # Quit the game
                exit()

    def confirm_quit(self):
        """Ask the player for confirmation before quitting the game."""
        while True:
            self.stdscr.clear()
            quit_msg = "Are you sure you want to quit? (y/n)"
            self.stdscr.addstr(self.height // 2, (self.width * 2 - len(quit_msg)) // 2, quit_msg)
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord('y'):
                self.stdscr.clear()
                self.stdscr.refresh()
                raise SystemExit("Game over. You chose to exit.")
            elif key == ord('n'):
                return  # Return to the game if the player chooses not to quit

    def move_entity(self, entity_pos, dy, dx):
        """Common method to move the hero or a CRUSHER and handle block pushing."""
        new_y = entity_pos[0] + dy
        new_x = entity_pos[1] + dx
        next_pos = (new_y, new_x)

        # If the next position is within bounds:
        if 0 <= new_y < self.height and 0 <= new_x < self.width:
            # Check if the next position is a block that potentially needs pushing
            if next_pos in self.block_positions:
                block_type = self.block_positions[next_pos]
                if block_type == self.CHARACTER_MAP[self.WALL]:
                    return entity_pos  # Unmovable block, entity can't move it
                elif self.can_push_blocks(new_y, new_x, dy, dx):
                    self.push_blocks(new_y, new_x, dy, dx)
                    entity_pos = next_pos  # Move entity to the position of the first block
            else:
                # Move entity if the space is free from blocks and enemies
                if next_pos not in self.enemy_positions and next_pos not in self.egg_positions:
                    entity_pos = next_pos

        return entity_pos

    def move_hero(self, dy, dx):
        """Move the hero using the common move_entity method."""
        self.hero_pos = self.move_entity(self.hero_pos, dy, dx)
        self.moves += 1

    def move_CRUSHER(self, CRUSHER_pos, dy, dx):
        """Move a CRUSHER using the common move_entity method."""
        new_pos = self.move_entity(CRUSHER_pos, dy, dx)
        if new_pos != CRUSHER_pos:  # If the CRUSHER actually moved
            self.enemy_positions[new_pos] = self.enemy_positions.pop(CRUSHER_pos)


    def can_push_blocks(self, block_y, block_x, dy, dx):
        """Check recursively if all sequential blocks can be pushed."""
        next_y = block_y + dy
        next_x = block_x + dx
        next_pos = (next_y, next_x)

        # Check if the next position is within bounds
        if not (0 <= next_y < self.height and 0 <= next_x < self.width):
            return False  # Stop if the next position is out of bounds

        # Check if the block is unmovable
        if next_pos in self.block_positions:
            block_type = self.block_positions[next_pos]
            if block_type == self.CHARACTER_MAP[self.WALL]:
                return False  # Unmovable block, can't push

        # Check if the next space contains an HUNTER or an egg
        if next_pos in self.enemy_positions or next_pos in self.egg_positions:
            # If there's no block behind the HUNTER or egg, stop the push
            behind_y = next_y + dy
            behind_x = next_x + dx
            if not (0 <= behind_y < self.height and 0 <= behind_x < self.width):
                return False  # Stop if behind the HUNTER or egg is out of bounds
            if (behind_y, behind_x) not in self.block_positions:
                return False  # Stop if there is no block behind the HUNTER or egg

        # If the next space contains another block, check if it can be pushed
        if next_pos in self.block_positions:
            return self.can_push_blocks(next_y, next_x, dy, dx)  # Recursive check for the next block

        return True  # If the next space is free, the blocks can be pushed


    def push_blocks(self, block_y, block_x, dy, dx):
        """Push blocks starting from the specified position, handling squishing logic."""
        blocks_to_move = []
        current_y, current_x = block_y, block_x

        # Collect all blocks that need to be pushed
        while (current_y, current_x) in self.block_positions:
            blocks_to_move.append((current_y, current_x))
            current_y += dy
            current_x += dx

        # Check if the last block can move
        if (current_y, current_x) in self.enemy_positions:
            # HUNTER is in the way, check if it can be squished
            if (current_y + dy, current_x + dx) in self.block_positions:
                # There's a block behind the HUNTER, squish it
                self.enemy_positions.pop((current_y, current_x))
                self.total_squished_enemies += 1
                self.score += 2
                self.play_sound('squish')
            else:
                # No block behind the egg, stop the block movement
                return

        # Move all collected blocks
        for y, x in reversed(blocks_to_move):
            new_y = y + dy
            new_x = x + dx
            self.block_positions[(new_y, new_x)] = self.block_positions.pop((y, x))

        # Update the game state after pushing blocks
        self.render()  # Re-render the screen to show changes


    def check_squish(self, y, x):
        """Check and handle squishing of enemies or eggs by the hero or blocks."""
        adjacent_positions = [
            (y + dy, x + dx)
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if not (dy == dx == 0)
        ]

        for pos in adjacent_positions:
            self.remove_position(pos)

    def play_sound(self, sound_name):
        try:
            if sound_name in self.sounds:
                # Use pygame.mixer for sound playback
                pygame.mixer.init()
                pygame.mixer.Sound(self.sounds[sound_name]).play()
            else:
                debug(f"Sound '{sound_name}' not found in preloaded sounds.\n")
        except Exception as e:
            debug(f"Error playing sound {sound_name}: {e}\n")

    def update_game_state(self):
        """Update the game state, primarily checking for collisions."""
        self.check_collisions()

    def bfs_find_path(self, start, goal):
        """Find the shortest path from start to goal using BFS, including diagonal movements."""
        queue = deque([start])
        visited = {start: None}

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while queue:
            current = queue.popleft()

            if current == goal:
                path = []
                while current:
                    path.append(current)
                    current = visited[current]
                return path[::-1]  # Return reversed path

            for dy, dx in directions:
                neighbor = (current[0] + dy, current[1] + dx)
                if (0 <= neighbor[0] < self.height and
                    0 <= neighbor[1] < self.width and
                    neighbor not in visited and
                    neighbor not in self.block_positions and
                    neighbor not in self.enemy_positions):
                    visited[neighbor] = current
                    queue.append(neighbor)

        return []  # Return an empty path if no path is found

    def is_within_CRUSHER_radius(self, pos):
        """Check if a CRUSHER is within the CRUSHER_RADIUS of the hero."""
        CRUSHER_y, CRUSHER_x = pos
        hero_y, hero_x = self.hero_pos
        distance = ((CRUSHER_y - hero_y) ** 2 + (CRUSHER_x - hero_x) ** 2) ** 0.5  # Calculate Euclidean distance

        return distance <= self.CRUSHER_RADIUS


    def move_enemies(self):
        """Move enemies towards the hero using BFS for intelligent movement. Eggs do not move."""
        new_positions = {}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

        for pos, HUNTER_char in list(self.enemy_positions.items()):
            if HUNTER_char == self.CHARACTER_MAP[self.EGG]:
                # Eggs do not move, just copy their position
                new_positions[pos] = HUNTER_char
            elif HUNTER_char == self.CHARACTER_MAP[self.CRUSHER]:
                # CRUSHERs move towards the hero within a certain radius
                if self.is_within_CRUSHER_radius(pos):
                    path = self.bfs_find_path(pos, self.hero_pos)
                    if len(path) > 1:  # Path found, move towards hero
                        next_pos = path[1]
                        dy, dx = next_pos[0] - pos[0], next_pos[1] - pos[1]
                        new_pos = self.move_entity(pos, dy, dx)
                        new_positions[new_pos] = HUNTER_char
                    else:
                        # No path found, move randomly
                        random.shuffle(directions)
                        for dy, dx in directions:
                            next_pos = (pos[0] + dy, pos[1] + dx)
                            if (0 <= next_pos[0] < self.height and
                                0 <= next_pos[1] < self.width and
                                next_pos not in self.block_positions and
                                next_pos not in self.enemy_positions and
                                next_pos not in self.egg_positions):
                                new_pos = self.move_entity(pos, dy, dx)
                                new_positions[new_pos] = HUNTER_char
                                break
            else:
                # Regular enemies move towards the hero intelligently
                path = self.bfs_find_path(pos, self.hero_pos)
                if len(path) > 1:  # Path found, move towards hero
                    next_pos = path[1]
                    if next_pos not in self.block_positions and next_pos not in new_positions:
                        new_positions[next_pos] = HUNTER_char
                    else:
                        new_positions[pos] = HUNTER_char
                else:
                    # No path found, stay in place
                    new_positions[pos] = HUNTER_char

        self.enemy_positions = new_positions


    def check_collisions(self):
        """Check for collisions between the hero and enemies."""
        hero_pos_tuple = (self.hero_pos[0], self.hero_pos[1])
        if hero_pos_tuple in self.enemy_positions:
            self.handle_hero_collision()

    def handle_hero_collision(self):
        """Handle what happens when the hero collides with an HUNTER."""
        self.play_sound('collision')  # Play collision sound

        self.lives -= 1  # Decrease the number of lives

        if self.lives > 0:
            # Respawn hero at a new position farthest from enemies and blocks
            self.hero_pos = self.find_farthest_position()
            self.render()  # Render the updated game state
            self.respawn_animation()  # Play the respawn animation
        else:
            self.end_game()  # End the game if no lives remain


    def respawn_animation(self):
        """Animate the hero's spawn with a cycle of characters and random colors."""
        
        animation_frames = ["  ", "░░", "▒▒", "▓▓", "  ", "░░", "▒▒", "▓▓"]
        
        # Possible colors for the animation (you can add more if you like)
        colors = [curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_YELLOW]

        for frame in animation_frames:
            # Choose a random color for each frame
            random_color = random.choice(colors)
            curses.init_pair(5, random_color, curses.COLOR_BLACK)  # Use pair 5 for animation colors
            
            # Display the frame with the random color
            self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, frame, curses.color_pair(5))
            self.stdscr.refresh()
            time.sleep(0.1)  # Adjust sleep time for animation speed

        # Finally, display the hero in the standard color
        self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO], curses.color_pair(self.HERO))
        self.stdscr.refresh()

    def end_game(self):
        """End the game when the player runs out of lives or quits, and save the score."""
        duration = time.time() - self.start_time  # Calculate total time played

        # Display completion message and save high score
        if self.display_completion_message("Game Over!", duration):
            self.save_high_score()
            self.display_high_scores()  # Show high scores after saving

        # Prompt the player to play another game or quit
        while True:
            self.stdscr.clear()
            end_msg = "Game Over!"
            prompt_msg = "Would you like to play another game? (y/n): "
            self.stdscr.addstr(self.height // 2 - 1, (self.width * 2 - len(end_msg)) // 2, end_msg)
            self.stdscr.addstr(self.height // 2 + 1, (self.width * 2 - len(prompt_msg)) // 2, prompt_msg)
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == ord('y'):
                self.reset_game()
                break
            elif key == ord('n') or key == ord('q'):
                self.stdscr.clear()
                self.stdscr.refresh()
                raise SystemExit("Game over. You chose to exit.")


    def reset_game(self):
        """Resets the game state for a new game."""
        self.level = 1
        self.lives = 5
        self.score = 0
        self.total_squished_enemies = 0
        self.moves = 0
        self.start_time = time.time()
        self.init_game()
        self.main_loop()


    def save_high_score(self):
        """Prompt for player's name and save the high score."""
        self.stdscr.clear()
        self.stdscr.addstr(self.height // 2, (self.width * 2 - len("Enter your name: ")) // 2, "Enter your name: ")
        curses.echo()
        player_name = self.stdscr.getstr(self.height // 2 + 1, (self.width * 2 - 20) // 2, 20).decode('utf-8')
        curses.noecho()

        # Generate current date/time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Compute a simple hash to prevent trivial changes
        hash_input = f"{player_name}{self.score}{current_time}".encode('utf-8')
        score_hash = hashlib.sha256(hash_input).hexdigest()

        # Prepare the score entry (encoded as bytes)
        score_entry = f"{player_name},{self.score},{current_time},{score_hash}".encode('utf-8')

        # Encode the entry using base85
        encoded_entry = base64.b85encode(score_entry).decode('utf-8')

        # Write the encoded score entry to a file
        with open("high_scores.txt", "a") as file:
            file.write(encoded_entry + "\n")

        self.stdscr.addstr(self.height // 2 + 3, (self.width * 2 - len("High score saved!")) // 2, "High score saved!")
        self.stdscr.refresh()
        time.sleep(2)  # Wait for 2 seconds before closing


    def load_high_scores(self):
        """Load and decode high scores from the file."""
        high_scores = []
        try:
            with open("high_scores.txt", "r") as file:
                for line in file:
                    line = line.strip()
                    if line:
                        decoded_entry = base64.b85decode(line.encode('utf-8')).decode('utf-8')
                        high_scores.append(decoded_entry)
        except FileNotFoundError:
            pass  # No high scores file exists yet
        return high_scores

    def display_high_scores(self):
        """Display the high scores in a centered window over the playing field, leaving the border visible."""
        high_scores = self.load_high_scores()

        if not high_scores:
            self.stdscr.addstr(self.height // 2, (self.width * 2 - len("No high scores available.")) // 2, "No high scores available.")
            self.stdscr.refresh()
            while True:
                key = self.stdscr.getch()
                if key in [ord(' '), 27]:  # Space bar or ESC key
                    break
            return

        high_scores.sort(reverse=True, key=lambda x: int(x.split(',')[1]))  # Sort by score

        max_scores_to_display = min(len(high_scores), self.height - 6)

        # Calculate the max length of the name for alignment
        longest_name = max(len(entry.split(',')[0]) for entry in high_scores[:max_scores_to_display])
        name_column_width = longest_name + 4
        date_column_width = 10  # "YYYY-MM-DD" is 10 characters
        time_column_width = 8   # "HH:MM:SS" is 8 characters
        score_column_width = 5  # Score width, assuming up to 99999

        # Calculate the width of the high score window
        win_width = name_column_width + date_column_width + time_column_width + score_column_width + 12  # Adjust for padding and borders
        win_height = max_scores_to_display + 2 + 3  # 2 for header, 2 for top/bottom borders, 1 for the title

        # Set the window position
        start_y = (self.height - win_height) // 2
        start_x = (self.width * 2 - win_width) // 2

        # Draw the border
        self.stdscr.addstr(start_y, start_x, f"╔{'═' * (win_width - 2)}╗")
        self.stdscr.addstr(start_y + win_height - 1, start_x, f"╚{'═' * (win_width - 2)}╝")

        for i in range(1, win_height - 1):
            self.stdscr.addstr(start_y + i, start_x, "║")
            self.stdscr.addstr(start_y + i, start_x + win_width - 1, "║")

        # Fill the background of the window
        for i in range(1, win_height - 1):
            self.stdscr.addstr(start_y + i, start_x + 1, " " * (win_width - 2))

        # Add the title
        title = "HIGH SCORES"
        title_start_x = start_x + (win_width - len(title)) // 2
        self.stdscr.addstr(start_y + 1, title_start_x, title)

        # Calculate the starting x positions for each column
        name_start_x = start_x + 2
        date_start_x = name_start_x + name_column_width + 2
        time_start_x = date_start_x + date_column_width + 2
        score_start_x = time_start_x + time_column_width + 4  # Adjust space before score

        # Print the header
        self.stdscr.addstr(start_y + 2, name_start_x + 4, "Name")
        self.stdscr.addstr(start_y + 2, date_start_x, "Date")
        self.stdscr.addstr(start_y + 2, time_start_x, "Time")
        self.stdscr.addstr(start_y + 2, score_start_x, "Score".rjust(score_column_width))

        # Print the high scores and highlight the current score
        for idx, entry in enumerate(high_scores[:max_scores_to_display]):
            name, score, date_time, _ = entry.split(',')
            date, time = date_time.split(' ')
            color = curses.color_pair(self.WALL) if int(score) == self.score else curses.color_pair(self.BLOCK)
            self.stdscr.addstr(start_y + 3 + idx, name_start_x, f"{str(idx + 1) + '.':>3} {name}", color)
            self.stdscr.addstr(start_y + 3 + idx, date_start_x, date, color)
            self.stdscr.addstr(start_y + 3 + idx, time_start_x, time, color)
            self.stdscr.addstr(start_y + 3 + idx, score_start_x, score.rjust(score_column_width), color)

        self.stdscr.refresh()

        # Wait for space or ESC key to be pressed
        while True:
            key = self.stdscr.getch()
            if key in [ord(' '), 27]:  # Space bar or ESC key
                break


    def calculate_current_rank(self):
        """Calculate and return the current rank based on the current score."""
        try:
            high_scores = self.load_high_scores()  # Use the existing load_high_scores method
        except FileNotFoundError:
            high_scores = []

        # Extract scores and sort them
        sorted_scores = sorted([int(score.split(',')[1]) for score in high_scores], reverse=True)

        # Calculate rank
        count = len([score for score in sorted_scores if score > self.score])
        final_rank = count + 1
        return final_rank



 
    def display_completion_message(self, title, duration):
        """Displays a completion message (for level or game over) and waits for user input to continue."""
        self.stdscr.clear()
        msg = [
            title,
            "",
            f"Enemies Eliminated: {self.total_squished_enemies}",
            f"Moves Taken: {self.moves}",
            f"Time Taken: {int(duration)} seconds",
            f"Score: {self.score}",
            "",
            "Press <space> to continue"
        ]
        longest_line = max(len(line) for line in msg)
        start_y = (self.height - len(msg)) // 2
        start_x = (self.width * 2 - longest_line) // 2  # Considering double width

        # Display the message in a centered window
        for i, line in enumerate(msg):
            self.stdscr.addstr(start_y + i, start_x, line)
        self.stdscr.refresh()

        while True:
            key = self.stdscr.getch()
            if key == ord(' '):
                return True
            elif key == ord('q'):
                return False



    def display_level_completion(self, duration):
        """Displays the end of level completion message."""
        self.score += 5  # Add 5 points for completing a level
        return self.display_completion_message(f"Level {self.level} Completed!", duration)



def main(stdscr):

    try:
        game = Game(stdscr)
        game.main_loop()
    except Exception as e:
        print(f"Unhandled exception: {e}")
        debug(f"Unhandled exception: {e}\n")

if __name__ == "__main__":
    curses.wrapper(main)
