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
import simpleaudio as sa
import time

class Game:
    BLOCK_COVERAGE = 0.35
    INITIAL_NUM_ENEMIES = 1
    ENEMY_MOVE_DELAY = 10

    HERO_ID = 1
    ENEMY_ID = 2
    UNPUSHABLE_BLOCK_ID = 3
    BLOCK_ID = 4  # Single ID for all movable blocks

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

    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.height, self.width = stdscr.getmaxyx()
        self.width //= 2  # Adjust width for character cell width
        self.init_colors()
        self.hero_pos = (self.height // 2, self.width // 4)
        self.block_positions = {}
        self.enemy_positions = {}
        self.level = 1
        self.total_squished_enemies = 0
        self.moves = 0
        self.start_time = time.time()
        self.init_colors()
        self.init_game()

    def init_colors(self):
        """Initialize color pairs dynamically based on the COLOR_MAP."""
        curses.start_color()
        for id, color in self.COLOR_MAP.items():
            # Assuming all text will be against a black background
            curses.init_pair(id, color, curses.COLOR_BLACK)

    def init_game(self):
        """Places game elements on the board."""
        self.place_blocks()
        self.place_enemies()
        self.hero_pos = self.find_hero_start_position()

    def place_blocks(self):
        """Randomly places blocks and a border of unmovable blocks on the grid."""
        self.block_positions = {}
        
        # Place unmovable border blocks
        for x in range(self.width):
            self.block_positions[(0, x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK_ID]  # Top border
            self.block_positions[(self.height - 1, x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK_ID]  # Bottom border
        for y in range(1, self.height - 1):
            self.block_positions[(y, 0)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK_ID]  # Left border
            self.block_positions[(y, self.width - 1)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK_ID]  # Right border

        # Place random movable blocks inside the borders
        for _ in range(int((self.width - 2) * (self.height - 2) * self.BLOCK_COVERAGE)):
            while True:
                x = random.randint(1, self.width - 2)
                y = random.randint(1, self.height - 2)
                if (y, x) not in self.block_positions:
                    self.block_positions[(y, x)] = random.choice(self.MOVABLE_BLOCK_CHARACTERS)
                    break

    def place_enemies(self):
        """Randomly places enemies, ensuring they do not overlap blocks."""
        for _ in range(5):
            while True:
                x = random.randint(1, self.width - 2)
                y = random.randint(1, self.height - 2)
                if (y, x) not in self.block_positions:
                    self.enemy_positions[(y, x)] = 'EE'
                    break

    def find_hero_start_position(self):
        """Find a suitable starting position for the hero."""
        return (self.height // 2, self.width // 4)

    def main_loop(self):
        """Main game loop."""
        while True:
            self.render()
            if self.handle_input():
                break
            self.update_game_state()
            if not self.enemy_positions:  # No more enemies left
                duration = time.time() - self.start_time
                if not self.display_level_completion(duration):
                    break  # Player chose to exit
                self.level += 1
                self.init_game()  # Start a new level

    def render(self):
        """Renders the game state to the screen using characters from CHARACTER_MAP."""
        self.stdscr.clear()
        # Display blocks
        for pos, char in self.block_positions.items():
            self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.BLOCK_ID))
        # Display enemies
        for pos in self.enemy_positions:
            self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.ENEMY_ID], curses.color_pair(self.ENEMY_ID))
        # Display hero
        self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO_ID], curses.color_pair(self.HERO_ID))
        self.stdscr.refresh()



    def handle_input(self):
        """Processes player input."""
        key = self.stdscr.getch()
        if key == curses.KEY_UP:
            self.move_hero(-1, 0)
        elif key == curses.KEY_DOWN:
            self.move_hero(1, 0)
        elif key == curses.KEY_LEFT:
            self.move_hero(0, -1)
        elif key == curses.KEY_RIGHT:
            self.move_hero(0, 1)
        elif key == ord('q'):
            return True  # Quit the game
        return False

    def move_hero(self, dy, dx):
        """Move the hero in the specified direction, handling block pushing."""
        new_y = self.hero_pos[0] + dy
        new_x = self.hero_pos[1] + dx
        next_pos = (new_y, new_x)

        # If the next position is within bounds:
        if 0 <= new_y < self.height and 0 <= new_x < self.width:
            # Check if the next position is a block that potentially needs pushing
            if next_pos in self.block_positions:
                if self.can_push_blocks(new_y, new_x, dy, dx):
                    self.push_blocks(new_y, new_x, dy, dx)
                    self.hero_pos = next_pos  # Move hero to the position of the first block
                    self.moves += 1
                # If blocks cannot be pushed, do not update hero's position
            else:
                # Move hero if the space is free from blocks and enemies
                if next_pos not in self.enemy_positions:
                    self.hero_pos = next_pos
                    self.moves += 1

    def can_push_blocks(self, block_y, block_x, dy, dx):
        """Check recursively if all sequential blocks can be pushed."""
        next_y = block_y + dy
        next_x = block_x + dx
        next_pos = (next_y, next_x)
        if not (0 <= next_y < self.height and 0 <= next_x < self.width):
            return False  # Stop if next position is out of bounds
        if next_pos in self.enemy_positions and (next_y + dy, next_x + dx) not in self.block_positions:
            return False  # Stop if there's an enemy with no block behind it
        if next_pos in self.block_positions:
            return self.can_push_blocks(next_y, next_x, dy, dx)  # Recursive check for next block
        return True  # Allow pushing if the next space is free

    def push_blocks(self, block_y, block_x, dy, dx):
        """Push blocks starting from the specified position."""
        current_y, current_x = block_y, block_x
        while (current_y, current_x) in self.block_positions:
            next_y = current_y + dy
            next_x = current_x + dx
            block_char = self.block_positions.pop((current_y, current_x))
            self.block_positions[(next_y, next_x)] = block_char
            current_y, current_x = next_y, next_x



    def check_squish(self, y, x):
        """Check and handle squishing of enemies by the hero."""
        adjacent_positions = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if not (dy == dx == 0)]
        for pos in adjacent_positions:
            if pos in self.enemy_positions:
                self.enemy_positions.pop(pos)
                self.total_squished_enemies += 1
                self.play_sound('squish.wav')

    def play_sound(self, filename):
        """Play a sound effect."""
        wave_obj = sa.WaveObject.from_wave_file(filename)
        wave_obj.play()

    def update_game_state(self):
        """Update the game state, primarily moving enemies and checking for collisions."""
        self.move_enemies()
        self.check_collisions()

    def move_enemies(self):
        """Move enemies towards the hero, randomly or with a simple AI."""
        new_positions = {}
        for pos in self.enemy_positions:
            # Simple AI to move enemies towards the hero: move either in x or y direction
            dy = dx = 0
            if pos[0] < self.hero_pos[0]:
                dy = 1
            elif pos[0] > self.hero_pos[0]:
                dy = -1
            if pos[1] < self.hero_pos[1]:
                dx = 1
            elif pos[1] > self.hero_pos[1]:
                dx = -1

            new_y, new_x = pos[0] + dy, pos[1] + dx
            # Ensure enemies do not overlap each other or blocks and stay within bounds
            if (0 <= new_y < self.height and 0 <= new_x < self.width and
                (new_y, new_x) not in self.block_positions and
                (new_y, new_x) not in new_positions):
                new_positions[(new_y, new_x)] = self.enemy_positions[pos]
            else:
                # If move is not possible, stay in the current position
                new_positions[pos] = self.enemy_positions[pos]

        self.enemy_positions = new_positions

    def check_collisions(self):
        """Check for collisions between the hero and enemies."""
        hero_pos_tuple = (self.hero_pos[0], self.hero_pos[1])
        if hero_pos_tuple in self.enemy_positions:
            self.handle_hero_collision()

    def handle_hero_collision(self):
        """Handle what happens when the hero collides with an enemy."""
        # For now, just reset the game or decrease life, etc.
        print("Collision! Hero has encountered an enemy.")
        # Here you might reset the hero position or end the game
        self.init_game()  # Reset game for simplicity


    def display_level_completion(self, duration):
        """Displays a level completion message and waits for user input to continue."""
        msg = f"Level {self.level} Completed! Time: {int(duration)} sec. Press Space to continue or Q to quit."
        self.stdscr.addstr(self.height // 2, (self.width * 2 - len(msg)) // 2, msg)
        self.stdscr.refresh()
        while True:
            key = self.stdscr.getch()
            if key == ord(' '):
                return True
            elif key == ord('q'):
                return False

def main(stdscr):
    game = Game(stdscr)
    game.main_loop()

curses.wrapper(main)
