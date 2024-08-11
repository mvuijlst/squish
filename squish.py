import curses
import random
import simpleaudio as sa
import time

class Game:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        self.width //= 2  # Adjust width for character cell width
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
        """Initializes color pairs."""
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)

    def init_game(self):
        """Places game elements on the board."""
        self.place_blocks()
        self.place_enemies()
        self.hero_pos = self.find_hero_start_position()

    def place_blocks(self):
        """Randomly places blocks and a border of unmovable blocks on the grid."""
        # Clear existing blocks if reinitializing
        self.block_positions = {}
        
        # Place unmovable border blocks
        for x in range(self.width):
            self.block_positions[(0, x)] = '▓▓'  # Top border
            self.block_positions[(self.height - 1, x)] = '▓▓'  # Bottom border
        for y in range(self.height):
            self.block_positions[(y, 0)] = '▓▓'  # Left border
            self.block_positions[(y, self.width - 1)] = '▓▓'  # Right border

        # Place random movable blocks inside the borders
        for _ in range(20):  # Number of random blocks
            while True:
                x = random.randint(1, self.width - 2)
                y = random.randint(1, self.height - 2)
                if (y, x) not in self.block_positions:
                    self.block_positions[(y, x)] = '░░'  # Using a different character for movable blocks
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
        """Renders the game state to the screen."""
        self.stdscr.clear()
        for pos, char in self.block_positions.items():
            self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(4))
        for pos, char in self.enemy_positions.items():
            self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(2))
        self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, 'HH', curses.color_pair(1))
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
        """Move the hero in the specified direction."""
        new_y = self.hero_pos[0] + dy
        new_x = self.hero_pos[1] + dx
        # Check for blocks and boundaries
        if 0 <= new_y < self.height and 0 <= new_x < self.width:
            if (new_y, new_x) not in self.block_positions:
                self.hero_pos = (new_y, new_x)
                self.moves += 1
                self.check_squish(new_y, new_x)

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
        """Update the game state, move enemies, check for game over conditions, etc."""
        # Implement enemy movement and collision checks
        pass

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
