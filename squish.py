"""
#############################################################
##                                                         ##
##                 S Q U I S H  v.1.0.1                    ##
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
class Game:
    BLOCK_COVERAGE = 0.35
    INITIAL_NUM_ENEMIES = 1
    ENEMY_MOVE_DELAY = 1000

    HERO_ID = 1
    ENEMY_ID = 2
    UNPUSHABLE_BLOCK_ID = 3
    BLOCK_ID = 4  # Single ID for all movable blocks

    CHARACTER_MAP = {
        HERO_ID: "<>",
        ENEMY_ID: "├┤",
        UNPUSHABLE_BLOCK_ID: "██",
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
        self.init_game()

    def init_colors(self):
        """Initialize color pairs dynamically based on the COLOR_MAP."""
        curses.start_color()
        for color_id, color in self.COLOR_MAP.items():
            curses.init_pair(color_id, color, curses.COLOR_BLACK)

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
                    self.enemy_positions[(y, x)] = self.CHARACTER_MAP[self.ENEMY_ID]
                    break

    def find_hero_start_position(self):
        """Find a suitable starting position for the hero."""
        return (self.height // 2, self.width // 4)

    def main_loop(self):
        """Main game loop with strict enemy movement delay."""
        last_enemy_move_time = time.time()

        self.stdscr.nodelay(True)  # Non-blocking getch()

        while True:
            current_time = time.time()

            # Handle input without blocking the loop
            if self.handle_input():
                break

            # Render the current state
            self.render()

            # Strictly check if it's time to move the enemies
            time_since_last_move = current_time - last_enemy_move_time
            print(f"Time since last move: {time_since_last_move:.3f}s")

            if time_since_last_move >= self.ENEMY_MOVE_DELAY / 1000.0:
                print(f"Moving enemies at {current_time}")
                self.move_enemies()
                last_enemy_move_time = current_time  # Reset the timer

            # Update game state (e.g., collisions, etc.)
            self.update_game_state()

            # Check if the level is completed (no more enemies)
            if not self.enemy_positions:
                duration = time.time() - self.start_time
                if not self.display_level_completion(duration):
                    break  # Player chose to exit
                self.level += 1
                self.init_game()  # Start a new level

            # Short sleep to avoid maxing out CPU
            time.sleep(0.01)


    def render(self):
        """Renders the game state to the screen using characters from CHARACTER_MAP."""
        self.stdscr.clear()
        max_y, max_x = self.stdscr.getmaxyx()

        # Display blocks
        for pos, char in self.block_positions.items():
            y, x = pos
            x *= 2  # Adjust x for double-width characters
            if 0 <= y < max_y and 0 <= x < max_x - len(char):
                try:
                    self.stdscr.addstr(y, x, char, curses.color_pair(self.BLOCK_ID))
                except curses.error as e:
                    print(f"Error rendering block at {y}, {x}: {e}")
            else:
                print(f"Block out of bounds: {pos} -> {y}, {x}")

        # Display enemies
        for pos in self.enemy_positions:
            y, x = pos
            x *= 2  # Adjust x for double-width characters
            if 0 <= y < max_y and 0 <= x < max_x - len(self.CHARACTER_MAP[self.ENEMY_ID]):
                try:
                    self.stdscr.addstr(y, x, self.CHARACTER_MAP[self.ENEMY_ID], curses.color_pair(self.ENEMY_ID))
                except curses.error as e:
                    print(f"Error rendering enemy at {y}, {x}: {e}")
            else:
                print(f"Enemy out of bounds: {pos} -> {y}, {x}")

        # Display hero
        hero_y, hero_x = self.hero_pos
        hero_x *= 2  # Adjust x for double-width characters
        if 0 <= hero_y < max_y and 0 <= hero_x < max_x - len(self.CHARACTER_MAP[self.HERO_ID]):
            try:
                self.stdscr.addstr(hero_y, hero_x, self.CHARACTER_MAP[self.HERO_ID], curses.color_pair(self.HERO_ID))
            except curses.error as e:
                print(f"Error rendering hero at {hero_y}, {hero_x}: {e}")
        else:
            print(f"Hero out of bounds: {self.hero_pos} -> {hero_y}, {hero_x}")

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

        # Check if the next position is within bounds and not occupied by unmovable objects
        if not (0 <= next_y < self.height and 0 <= next_x < self.width):
            return False  # Stop if the next position is out of bounds

        # Check if there's an enemy in the next position with no block behind it
        if next_pos in self.enemy_positions and (next_y + dy, next_x + dx) not in self.block_positions:
            return False  # Stop if there's an enemy without a block behind it

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
            # Enemy is in the way, check if it can be squished
            if (current_y + dy, current_x + dx) in self.block_positions:
                # There's a block behind the enemy, squish it
                self.enemy_positions.pop((current_y, current_x))
                self.total_squished_enemies += 1
                self.play_sound('squish.wav')
                print(f"Enemy squished at {(current_y, current_x)}")
            else:
                # No block behind the enemy, stop the block movement
                return

        # Move all collected blocks
        for y, x in reversed(blocks_to_move):
            new_y = y + dy
            new_x = x + dx
            self.block_positions[(new_y, new_x)] = self.block_positions.pop((y, x))


    def check_squish(self, y, x):
        """Check and handle squishing of enemies by the hero or blocks."""
        adjacent_positions = [
            (y + dy, x + dx)
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if not (dy == dx == 0)
        ]

        for pos in adjacent_positions:
            if pos in self.enemy_positions:
                self.enemy_positions.pop(pos)
                self.total_squished_enemies += 1
                self.play_sound('squish.wav')
                print(f"Enemy squished at {pos}")


    def play_sound(self, filename):
        """Play a sound effect."""
        wave_obj = sa.WaveObject.from_wave_file(filename)
        wave_obj.play()

    def update_game_state(self):
        """Update the game state, primarily checking for collisions."""
        self.check_collisions()

    def bfs_find_path(self, start, goal):
        """Find the shortest path from start to goal using BFS."""
        queue = deque([start])
        visited = {start: None}

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

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

    def move_enemies(self):
        """Move enemies towards the hero using BFS or randomly if no path is found."""
        new_positions = {}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        for pos in self.enemy_positions:
            path = self.bfs_find_path(pos, self.hero_pos)
            if len(path) > 1:  # Path found, move towards hero
                next_pos = path[1]
                if next_pos not in self.block_positions and next_pos not in new_positions:
                    new_positions[next_pos] = self.enemy_positions[pos]
                else:
                    new_positions[pos] = self.enemy_positions[pos]
            else:  # No path found, move randomly
                random.shuffle(directions)
                for dy, dx in directions:
                    next_pos = (pos[0] + dy, pos[1] + dx)
                    if (0 <= next_pos[0] < self.height and
                        0 <= next_pos[1] < self.width and
                        next_pos not in self.block_positions and
                        next_pos not in new_positions):
                        new_positions[next_pos] = self.enemy_positions[pos]
                        break
                else:
                    new_positions[pos] = self.enemy_positions[pos]  # Stay in place if no move is possible

        self.enemy_positions = new_positions


    def check_collisions(self):
        """Check for collisions between the hero and enemies."""
        hero_pos_tuple = (self.hero_pos[0], self.hero_pos[1])
        if hero_pos_tuple in self.enemy_positions:
            self.handle_hero_collision()

    def handle_hero_collision(self):
        """Handle what happens when the hero collides with an enemy."""
        self.play_sound('collision.wav')  # Assuming you have a collision sound
        # For simplicity, just reset the game or decrease life, etc.
        self.init_game()  # Reset game for simplicity

    def display_level_completion(self, duration):
        """Displays a level completion message and waits for user input to continue."""
        self.stdscr.clear()
        msg = [
            f"Level {self.level} Completed!",
            "",
            f"Enemies Eliminated: {self.total_squished_enemies}",
            f"Moves Taken: {self.moves}",
            f"Time Taken: {int(duration)} seconds",
            "",
            "Press <space> to continue or 'q' to quit"
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

def main(stdscr):
    game = Game(stdscr)
    game.main_loop()

if __name__ == "__main__":
    curses.wrapper(main)
