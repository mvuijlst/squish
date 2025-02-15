#!/usr/bin/env python3
"""
#############################################################
##                                                         ##
##                 S Q U I S H  v.1.2.2                    ##
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
    """Get the absolute path to the resource, works for both development and PyInstaller packaging."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def debug(msg):
    """General-purpose debugging."""
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

    MOVABLE_BLOCK_CHARACTERS = ['░░', '▒▒']  # Different characters for movable blocks

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
        self.width //= 2  # because each cell is printed as two characters wide
        self.hero_pos = (self.height // 2, self.width // 4)
        self.block_positions = {}
        self.enemy_positions = {}   # Active enemies: Hunters and Crushers.
        self.egg_positions = {}     # Eggs waiting to hatch.
        self.hatching_times = {}    # Mapping egg positions to their hatch time.
        self.level = 1
        self.lives = 2  # Hero lives
        self.total_squished_enemies = 0
        self.moves = 0
        self.score = 0
        self.rank = 0
        self.start_time = time.time()
        self.paused = False
        self.paused_time = 0  # Time spent in paused state
        self.last_pause_time = None  # Time when the game was paused
        self.last_move_time = 0
        self.move_cooldown = 0  # Minimum time between hero moves (set to 0.1 for controller)

        # Initialize Pygame once
        self.init_pygame()

        # Set up colors and start the game
        self.init_game()

    def init_game(self):
        """Initialize the game for the current level."""
        self.init_colors()
        self.place_walls()
        self.place_blocks()
        self.place_enemies()  # Eggs go into egg_positions; hunters go into enemy_positions.
        self.check_positions()
        self.hero_pos = self.find_farthest_position()
        self.render()
        self.respawn_animation()

    def init_pygame(self):
        """Initialize pygame systems."""
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
        """Initialize color pairs dynamically based on the COLOR_MAP."""
        curses.start_color()
        for color_id, color in self.COLOR_MAP.items():
            curses.init_pair(color_id, color, curses.COLOR_BLACK)

    def place_walls(self):
        """Place unmovable border blocks."""
        for x in range(self.width):
            self.block_positions[(0, x)] = self.CHARACTER_MAP[self.WALL]
            self.block_positions[(self.height - 1, x)] = self.CHARACTER_MAP[self.WALL]
        for y in range(self.height):
            self.block_positions[(y, 0)] = self.CHARACTER_MAP[self.WALL]
            self.block_positions[(y, self.width - 1)] = self.CHARACTER_MAP[self.WALL]

        debug(f"Block positions (walls): {sorted(self.block_positions.keys())}\n")

    def place_blocks(self):
        """Randomly places movable and unmovable blocks on the grid (inside borders)."""
        max_x = self.width - 2  # excluding borders
        max_y = self.height - 2

        total_internal_cells = max_x * max_y
        num_movable_blocks = int(total_internal_cells * self.BLOCK_COVERAGE)
        num_unmovable_blocks = int(total_internal_cells * self.UNMOVABLE_BLOCKS)

        internal_positions = [(y, x) for y in range(1, max_y + 1) for x in range(1, max_x + 1)]

        movable_block_positions = random.sample(internal_positions, num_movable_blocks)
        for pos in movable_block_positions:
            self.block_positions[pos] = random.choice(self.MOVABLE_BLOCK_CHARACTERS)

        remaining_positions = set(internal_positions) - set(movable_block_positions)
        unmovable_block_positions = random.sample(list(remaining_positions), num_unmovable_blocks)
        for pos in unmovable_block_positions:
            self.block_positions[pos] = self.CHARACTER_MAP[self.WALL]

    def place_enemies(self):
        """Place hunters and eggs in free positions (avoiding walls/blocks)."""
        self.enemy_positions = {}
        self.egg_positions = {}
        self.hatching_times = {}

        max_x = self.width - 2
        max_y = self.height - 2

        all_positions = {(y, x) for y in range(1, max_y + 1) for x in range(1, max_x + 1)}
        blocked_positions = set(self.block_positions.keys())

        free_positions = all_positions - blocked_positions

        total_needed = self.NUM_EGGS + self.level + self.INITIAL_NUM_ENEMIES
        if len(free_positions) < total_needed:
            debug("Warning: Not enough free positions to place all enemies and eggs.\n")
            return

        # Place eggs (only in egg_positions)
        egg_positions = random.sample(list(free_positions), self.NUM_EGGS)
        for pos in egg_positions:
            self.egg_positions[pos] = self.CHARACTER_MAP[self.EGG]
            self.hatching_times[pos] = time.time() + self.HATCHING_TIME

        free_positions -= set(egg_positions)

        # Place hunters (active enemies)
        num_enemies = self.level + self.INITIAL_NUM_ENEMIES
        enemy_positions = random.sample(list(free_positions), num_enemies)
        for pos in enemy_positions:
            self.enemy_positions[pos] = self.CHARACTER_MAP[self.HUNTER]

        self.check_positions()

    def check_positions(self):
        """Verify that no eggs or enemies are placed in wall/block positions."""
        for pos in self.egg_positions.keys():
            if pos in self.block_positions:
                debug(f"Error: Egg generated in a wall at {pos}!\n")
        for pos in self.enemy_positions.keys():
            if pos in self.block_positions:
                debug(f"Error: Enemy generated in a wall at {pos}!\n")

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

    def calculate_weighted_distances(self, occupied_positions):
        """Calculate a weighted distance from occupied positions using BFS."""
        distances = [[float('inf') for _ in range(self.width)] for _ in range(self.height)]
        queue = deque()

        for pos in occupied_positions:
            # Enemies count more than blocks
            weight = 100 if pos in self.enemy_positions else 1
            y, x = pos
            distances[y][x] = 0
            queue.append((y, x, 0, weight))

        while queue:
            y, x, current_distance, current_weight = queue.popleft()
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.height and 0 <= nx < self.width:
                    new_distance = current_distance + current_weight
                    if new_distance < distances[ny][nx]:
                        distances[ny][nx] = new_distance
                        queue.append((ny, nx, new_distance, current_weight))
        return distances

    def find_farthest_position(self):
        """Find the position farthest from any enemy or block."""
        occupied_positions = list(self.enemy_positions.keys()) + list(self.block_positions.keys())
        distances = self.calculate_weighted_distances(occupied_positions)
        max_distance = -1
        farthest_position = None

        for y in range(self.height):
            for x in range(self.width):
                if distances[y][x] > max_distance and (y, x) not in self.block_positions \
                   and (y, x) not in self.enemy_positions and (y, x) not in self.egg_positions:
                    max_distance = distances[y][x]
                    farthest_position = (y, x)
        return farthest_position

    def main_loop(self):
        """Main game loop with strict HUNTER movement delay."""
        try:
            last_hunter_move_time = time.time()
            last_hatch_check_time = time.time()
            self.stdscr.nodelay(True)  # Non-blocking input

            while True:
                current_time = time.time()
                self.render()

                if self.handle_input():
                    break

                # Move enemies at fixed intervals.
                if current_time - last_hunter_move_time >= self.HUNTER_MOVE_DELAY / 1000.0:
                    self.move_enemies()
                    last_hunter_move_time = current_time

                # Check egg hatching every second.
                if current_time - last_hatch_check_time >= 1.0:
                    self.hatch_eggs()
                    last_hatch_check_time = current_time

                self.update_game_state()

                # Level is complete if no active enemies and no eggs remain.
                if not self.enemy_positions and not self.egg_positions:
                    duration = time.time() - self.start_time
                    if not self.display_level_completion(duration):
                        break
                    self.level += 1
                    self.init_game()

                time.sleep(0.01)
        except Exception as e:
            debug(f"Exception in main loop: {e}\n")

    def hatch_eggs(self):
        """Handle the hatching process for eggs."""
        current_time = time.time()
        new_crushers = {}

        for pos, hatch_time in list(self.hatching_times.items()):
            if current_time >= hatch_time:
                random_hatch_time = random.uniform(0, self.HATCHING_TIME)
                if current_time >= hatch_time + random_hatch_time:
                    if pos in self.egg_positions:
                        new_crushers[pos] = self.CHARACTER_MAP[self.CRUSHER]

        for pos, crusher in new_crushers.items():
            if pos in self.egg_positions:
                self.egg_positions.pop(pos)
                self.hatching_times.pop(pos, None)
                self.enemy_positions[pos] = crusher

    def remove_position(self, pos):
        """Remove a position from enemy or egg lists."""
        self.enemy_positions.pop(pos, None)
        self.egg_positions.pop(pos, None)

    def render(self, show_options=False):
        """Renders the game state to the screen."""
        self.stdscr.clear()

        # Display blocks.
        for pos, char in self.block_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                color = curses.color_pair(self.WALL if char == self.CHARACTER_MAP[self.WALL] else self.BLOCK)
                self.stdscr.addstr(pos[0], pos[1] * 2, char, color)

        # Display active enemies.
        for pos, char in self.enemy_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                if char == self.CHARACTER_MAP[self.CRUSHER]:
                    self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.CRUSHER))
                else:
                    self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.HUNTER], curses.color_pair(self.HUNTER))

        # Display eggs.
        for pos, char in self.egg_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.EGG))

        # Display hero.
        if 0 <= self.hero_pos[0] < self.height - 2 and 0 <= self.hero_pos[1] < self.width:
            self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO], curses.color_pair(self.HERO))

        # Draw a dividing wall above the status line.
        for x in range(self.width):
            self.stdscr.addstr(self.height - 3, x * 2, self.CHARACTER_MAP[self.WALL], curses.color_pair(self.WALL))

        elapsed_time = int(self.paused_time + (time.time() - self.start_time) if not self.paused else self.paused_time)
        minutes = elapsed_time // 60
        seconds = elapsed_time % 60
        hunter_count = len(self.enemy_positions) + len(self.egg_positions)
        status_line = f"Enemies: {hunter_count}  |  Time: {minutes:02}:{seconds:02}  |  Lives: {self.lives}  |  Score: {self.score} ({self.rank})"

        self.stdscr.addstr(self.height - 2, 0, status_line.ljust(self.width * 2))

        if show_options:
            options_line = "<space> = continue | s = Scores | q = Exit"
            self.stdscr.addstr(self.height - 1, 0, options_line.ljust(self.width * 2))

        self.stdscr.refresh()

    def handle_input(self):
        """Process player input."""
        key = self.stdscr.getch()
        move_y, move_x = 0, 0
        current_time = time.time()
        keys = set()

        start_time = time.time()
        while key != -1 and (time.time() - start_time) < 0.05:
            keys.add(key)
            key = self.stdscr.getch()
            time.sleep(0.01)

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
            pygame.event.pump()
            axis_x = self.joystick.get_axis(0)
            axis_y = self.joystick.get_axis(1)
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
            if self.joystick.get_button(7):
                self.pause_game()
            elif self.joystick.get_button(6):
                return True

        if (move_y != 0 or move_x != 0) and (current_time - self.last_move_time > self.move_cooldown):
            self.move_hero(move_y, move_x)
            self.last_move_time = current_time

        return False

    def pause_game(self):
        """Pause the game and show options."""
        self.last_pause_time = time.time()
        while True:
            self.render(show_options=True)
            key = self.stdscr.getch()
            if key == ord(' '):
                self.paused_time += time.time() - self.last_pause_time
                self.last_pause_time = None
                return
            elif key == ord('s'):
                self.display_high_scores()
            elif key == ord('q'):
                exit()

    def confirm_quit(self):
        """Ask for confirmation before quitting."""
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
                return

    def move_entity(self, entity_pos, dy, dx):
        """Move an entity (hero or crusher), handling block pushing."""
        new_y = entity_pos[0] + dy
        new_x = entity_pos[1] + dx
        next_pos = (new_y, new_x)

        if 0 <= new_y < self.height and 0 <= new_x < self.width:
            if next_pos in self.block_positions:
                block_type = self.block_positions[next_pos]
                if block_type == self.CHARACTER_MAP[self.WALL]:
                    return entity_pos
                elif self.can_push_blocks(new_y, new_x, dy, dx):
                    self.push_blocks(new_y, new_x, dy, dx)
                    entity_pos = next_pos
            else:
                if next_pos not in self.enemy_positions and next_pos not in self.egg_positions:
                    entity_pos = next_pos
        return entity_pos

    def move_hero(self, dy, dx):
        """Move the hero and increment move count."""
        self.hero_pos = self.move_entity(self.hero_pos, dy, dx)
        self.moves += 1
        self.check_squish(self.hero_pos[0], self.hero_pos[1])

    def move_crusher(self, pos, dy, dx):
        """Move a crusher using move_entity."""
        new_pos = self.move_entity(pos, dy, dx)
        if new_pos != pos:
            self.enemy_positions[new_pos] = self.enemy_positions.pop(pos)

    def can_push_blocks(self, block_y, block_x, dy, dx):
        """Check recursively if sequential blocks can be pushed."""
        next_y = block_y + dy
        next_x = block_x + dx
        next_pos = (next_y, next_x)

        if not (0 <= next_y < self.height and 0 <= next_x < self.width):
            return False

        if next_pos in self.block_positions:
            if self.block_positions[next_pos] == self.CHARACTER_MAP[self.WALL]:
                return False

        if next_pos in self.enemy_positions or next_pos in self.egg_positions:
            behind_y = next_y + dy
            behind_x = next_x + dx
            if not (0 <= behind_y < self.height and 0 <= behind_x < self.width):
                return False
            if (behind_y, behind_x) not in self.block_positions:
                return False

        if next_pos in self.block_positions:
            return self.can_push_blocks(next_y, next_x, dy, dx)

        return True

    def push_blocks(self, block_y, block_x, dy, dx):
        """Push blocks starting at (block_y, block_x), handling squishing logic."""
        blocks_to_move = []
        current_y, current_x = block_y, block_x

        while (current_y, current_x) in self.block_positions:
            blocks_to_move.append((current_y, current_x))
            current_y += dy
            current_x += dx

        if (current_y, current_x) in self.enemy_positions:
            if (current_y + dy, current_x + dx) in self.block_positions:
                self.enemy_positions.pop((current_y, current_x))
                self.total_squished_enemies += 1
                self.score += 2
                self.play_sound('squish')
            else:
                return

        for y, x in reversed(blocks_to_move):
            new_y = y + dy
            new_x = x + dx
            self.block_positions[(new_y, new_x)] = self.block_positions.pop((y, x))

        self.render()

    def check_squish(self, y, x):
        """Check and handle squishing of adjacent enemies or eggs."""
        adjacent_positions = [
            (y + dy, x + dx)
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if not (dy == dx == 0)
        ]
        for pos in adjacent_positions:
            self.remove_position(pos)

    def play_sound(self, sound_name):
        """Play a sound if available."""
        try:
            if sound_name in self.sounds:
                self.sounds[sound_name].play()
            else:
                debug(f"Sound '{sound_name}' not found.\n")
        except Exception as e:
            debug(f"Error playing sound {sound_name}: {e}\n")

    def update_game_state(self):
        """Update the game state by checking for collisions."""
        self.check_collisions()

    def bfs_find_path(self, start, goal):
        """Find the shortest path from start to goal using BFS (including diagonals)."""
        queue = deque([start])
        visited = {start: None}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while queue:
            current = queue.popleft()
            if current == goal:
                path = []
                while current:
                    path.append(current)
                    current = visited[current]
                return path[::-1]

            for dy, dx in directions:
                neighbor = (current[0] + dy, current[1] + dx)
                if (0 <= neighbor[0] < self.height and 0 <= neighbor[1] < self.width and
                        neighbor not in visited and
                        neighbor not in self.block_positions and
                        neighbor not in self.enemy_positions and
                        neighbor not in self.egg_positions):
                    visited[neighbor] = current
                    queue.append(neighbor)
        return []

    def is_within_CRUSHER_radius(self, pos):
        """Check if a crusher at pos is within CRUSHER_RADIUS of the hero."""
        CRUSHER_y, CRUSHER_x = pos
        hero_y, hero_x = self.hero_pos
        distance = ((CRUSHER_y - hero_y) ** 2 + (CRUSHER_x - hero_x) ** 2) ** 0.5
        return distance <= self.CRUSHER_RADIUS

    def move_enemies(self):
        """Move active enemies (hunters and crushers) towards the hero."""
        new_positions = {}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]

        for pos, enemy_char in list(self.enemy_positions.items()):
            if enemy_char == self.CHARACTER_MAP[self.CRUSHER]:
                if self.is_within_CRUSHER_radius(pos):
                    path = self.bfs_find_path(pos, self.hero_pos)
                    if len(path) > 1:
                        next_pos = path[1]
                        dy, dx = next_pos[0] - pos[0], next_pos[1] - pos[1]
                        new_pos = self.move_entity(pos, dy, dx)
                        new_positions[new_pos] = enemy_char
                    else:
                        random.shuffle(directions)
                        for dy, dx in directions:
                            next_pos = (pos[0] + dy, pos[1] + dx)
                            if (0 <= next_pos[0] < self.height and 0 <= next_pos[1] < self.width and
                                    next_pos not in self.block_positions and
                                    next_pos not in self.enemy_positions and
                                    next_pos not in self.egg_positions):
                                new_pos = self.move_entity(pos, dy, dx)
                                new_positions[new_pos] = enemy_char
                                break
                else:
                    new_positions[pos] = enemy_char
            else:
                # Regular hunter movement.
                path = self.bfs_find_path(pos, self.hero_pos)
                if len(path) > 1:
                    next_pos = path[1]
                    if next_pos not in self.block_positions and next_pos not in new_positions:
                        new_positions[next_pos] = enemy_char
                    else:
                        new_positions[pos] = enemy_char
                else:
                    new_positions[pos] = enemy_char

        self.enemy_positions = new_positions

    def check_collisions(self):
        """
        Check for collisions between the hero and any enemy or egg.
        Here we treat eggs specially:
          - If the hero moves onto a cell with an egg, the egg is squished (removed and score awarded).
          - Colliding with a hunter (or crusher) still triggers a collision.
        """
        if self.hero_pos in self.egg_positions:
            # Squish the egg: remove it and award points.
            self.egg_positions.pop(self.hero_pos)
            self.hatching_times.pop(self.hero_pos, None)
            self.score += 2
        elif self.hero_pos in self.enemy_positions:
            self.handle_hero_collision()

    def handle_hero_collision(self):
        """Handle a collision involving the hero."""
        self.play_sound('collision')
        self.lives -= 1

        if self.lives > 0:
            self.hero_pos = self.find_farthest_position()
            self.render()
            self.respawn_animation()
        else:
            self.end_game()

    def respawn_animation(self):
        """Animate the hero's respawn."""
        animation_frames = ["  ", "░░", "▒▒", "▓▓", "  ", "░░", "▒▒", "▓▓"]
        colors = [curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_BLUE,
                  curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_YELLOW]

        for frame in animation_frames:
            random_color = random.choice(colors)
            curses.init_pair(5, random_color, curses.COLOR_BLACK)
            self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, frame, curses.color_pair(5))
            self.stdscr.refresh()
            time.sleep(0.1)

        self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO],
                           curses.color_pair(self.HERO))
        self.stdscr.refresh()

    def end_game(self):
        """End the game and offer to save high score or restart."""
        duration = time.time() - self.start_time
        if self.display_completion_message("Game Over!", duration):
            self.save_high_score()
            self.display_high_scores()

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
            elif key in (ord('n'), ord('q')):
                self.stdscr.clear()
                self.stdscr.refresh()
                raise SystemExit("Game over. You chose to exit.")

    def reset_game(self):
        """Reset the game state for a new game."""
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
        prompt = "Enter your name: "
        self.stdscr.addstr(self.height // 2, (self.width * 2 - len(prompt)) // 2, prompt)
        curses.echo()
        player_name = self.stdscr.getstr(self.height // 2 + 1, (self.width * 2 - 20) // 2, 20).decode('utf-8')
        curses.noecho()

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hash_input = f"{player_name}{self.score}{current_time}".encode('utf-8')
        score_hash = hashlib.sha256(hash_input).hexdigest()
        score_entry = f"{player_name},{self.score},{current_time},{score_hash}".encode('utf-8')
        encoded_entry = base64.b85encode(score_entry).decode('utf-8')

        with open("high_scores.txt", "a") as file:
            file.write(encoded_entry + "\n")

        self.stdscr.addstr(self.height // 2 + 3, (self.width * 2 - len("High score saved!")) // 2, "High score saved!")
        self.stdscr.refresh()
        time.sleep(2)

    def load_high_scores(self):
        """Load and decode high scores from file."""
        high_scores = []
        try:
            with open("high_scores.txt", "r") as file:
                for line in file:
                    line = line.strip()
                    if line:
                        decoded_entry = base64.b85decode(line.encode('utf-8')).decode('utf-8')
                        high_scores.append(decoded_entry)
        except FileNotFoundError:
            pass
        return high_scores

    def display_high_scores(self):
        """Display high scores in a centered overlay."""
        high_scores = self.load_high_scores()
        if not high_scores:
            self.stdscr.addstr(self.height // 2, (self.width * 2 - len("No high scores available.")) // 2,
                               "No high scores available.")
            self.stdscr.refresh()
            while True:
                key = self.stdscr.getch()
                if key in [ord(' '), 27]:
                    break
            return

        high_scores.sort(reverse=True, key=lambda x: int(x.split(',')[1]))
        max_scores_to_display = min(len(high_scores), self.height - 6)
        longest_name = max(len(entry.split(',')[0]) for entry in high_scores[:max_scores_to_display])
        name_column_width = longest_name + 4
        date_column_width = 10
        time_column_width = 8
        score_column_width = 5
        win_width = name_column_width + date_column_width + time_column_width + score_column_width + 12
        win_height = max_scores_to_display + 5

        start_y = (self.height - win_height) // 2
        start_x = (self.width * 2 - win_width) // 2

        self.stdscr.addstr(start_y, start_x, f"╔{'═' * (win_width - 2)}╗")
        self.stdscr.addstr(start_y + win_height - 1, start_x, f"╚{'═' * (win_width - 2)}╝")
        for i in range(1, win_height - 1):
            self.stdscr.addstr(start_y + i, start_x, "║")
            self.stdscr.addstr(start_y + i, start_x + win_width - 1, "║")
            self.stdscr.addstr(start_y + i, start_x + 1, " " * (win_width - 2))

        title = "HIGH SCORES"
        title_start_x = start_x + (win_width - len(title)) // 2
        self.stdscr.addstr(start_y + 1, title_start_x, title)

        name_start_x = start_x + 2
        date_start_x = name_start_x + name_column_width + 2
        time_start_x = date_start_x + date_column_width + 2
        score_start_x = time_start_x + time_column_width + 4

        self.stdscr.addstr(start_y + 2, name_start_x + 4, "Name")
        self.stdscr.addstr(start_y + 2, date_start_x, "Date")
        self.stdscr.addstr(start_y + 2, time_start_x, "Time")
        self.stdscr.addstr(start_y + 2, score_start_x, "Score".rjust(score_column_width))

        for idx, entry in enumerate(high_scores[:max_scores_to_display]):
            name, score, date_time, _ = entry.split(',')
            date_part, time_part = date_time.split(' ')
            color = curses.color_pair(self.WALL) if int(score) == self.score else curses.color_pair(self.BLOCK)
            self.stdscr.addstr(start_y + 3 + idx, name_start_x, f"{str(idx + 1) + '.':>3} {name}", color)
            self.stdscr.addstr(start_y + 3 + idx, date_start_x, date_part, color)
            self.stdscr.addstr(start_y + 3 + idx, time_start_x, time_part, color)
            self.stdscr.addstr(start_y + 3 + idx, score_start_x, score.rjust(score_column_width), color)

        self.stdscr.refresh()
        while True:
            key = self.stdscr.getch()
            if key in [ord(' '), 27]:
                break

    def calculate_current_rank(self):
        """Calculate the current rank based on the score."""
        try:
            high_scores = self.load_high_scores()
        except FileNotFoundError:
            high_scores = []
        sorted_scores = sorted([int(score.split(',')[1]) for score in high_scores], reverse=True)
        count = len([score for score in sorted_scores if score > self.score])
        final_rank = count + 1
        return final_rank

    def display_completion_message(self, title, duration):
        """Display a level/game completion message and wait for input."""
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
        start_x = (self.width * 2 - longest_line) // 2

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
        """Update score and display level completion message."""
        self.score += 5  # Add points for completing a level
        return self.display_completion_message(f"Level {self.level} Completed!", duration)


def main(stdscr):
    try:
        game = Game(stdscr)
        game.main_loop()
    except Exception as e:
        debug(f"Unhandled exception: {e}\n")
        print(f"Unhandled exception: {e}")


if __name__ == "__main__":
    curses.wrapper(main)
