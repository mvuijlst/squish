"""
#############################################################
##                                                         ##
##                 S Q U I S H  v.1.1.0                    ##
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
import pygame
import simpleaudio as sa
class Game:
    """
    A class representing the game.
    """
    BLOCK_COVERAGE = 0.30
    UNMOVABLE_BLOCKS = 0.01
    INITIAL_NUM_ENEMIES = 1
    ENEMY_MOVE_DELAY = 1000

    HERO = 1
    ENEMY = 2
    UNPUSHABLE_BLOCK = 3
    BLOCK = 4

    CHARACTER_MAP = {
        HERO: "◄►",
        ENEMY: "├┤",
        UNPUSHABLE_BLOCK: "██",
    }

    MOVABLE_BLOCK_CHARACTERS = ['░░', '▒▒', '▓▓']  # Different characters for movable blocks

    COLOR_MAP = {
        HERO: curses.COLOR_CYAN,
        ENEMY: curses.COLOR_RED,
        UNPUSHABLE_BLOCK: curses.COLOR_YELLOW,
        BLOCK: curses.COLOR_WHITE,
    }

    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.height, self.width = stdscr.getmaxyx()
        self.height -= 2
        self.width //= 2
        self.init_colors()
        self.hero_pos = (self.height // 2, self.width // 4)
        self.block_positions = {}
        self.enemy_positions = {}
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

        # Initialize pygame and the joystick
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
        else:
            self.joystick = None

    def init_game(self):
        """Places game elements on the board."""
        self.place_blocks()
        self.place_enemies()
        self.hero_pos = self.find_farthest_position()
        self.render()
        self.respawn_animation()

    def init_colors(self):
        """Initialize color pairs dynamically based on the COLOR_MAP."""
        curses.start_color()
        for color_id, color in self.COLOR_MAP.items():
            curses.init_pair(color_id, color, curses.COLOR_BLACK)

    def place_blocks(self):
        """Randomly places blocks and a border of unmovable blocks on the grid."""
        self.block_positions = {}
        
        # Ensure that we're working with the screen's usable width and height
        max_x = self.width - 1  # Adjusting so that we don't exceed screen width
        max_y = self.height - 3  # Adjusting height to leave space for status lines

        # Place unmovable border blocks
        for x in range(max_x + 1):  # Avoid overflow by ensuring x stays within the range
            self.block_positions[(0, x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]  # Top border
            self.block_positions[(max_y, x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]  # Bottom border (above status lines)
        for y in range(1, max_y):
            self.block_positions[(y, 0)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]  # Left border
            self.block_positions[(y, max_x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]  # Right border

        # Place random movable blocks inside the borders
        for _ in range(int((max_x - 1) * (max_y - 1) * self.BLOCK_COVERAGE)):
            while True:
                x = random.randint(1, max_x - 1)  # Ensure x is within valid range for rendering
                y = random.randint(1, max_y - 1)
                if (y, x) not in self.block_positions:
                    self.block_positions[(y, x)] = random.choice(self.MOVABLE_BLOCK_CHARACTERS)
                    break

        # Add additional unmovable blocks randomly
        num_unmovable_blocks = int((max_x * max_y) * self.UNMOVABLE_BLOCKS)
        for _ in range(num_unmovable_blocks):
            while True:
                x = random.randint(1, max_x - 1)
                y = random.randint(1, max_y - 1)
                if (y, x) not in self.block_positions:
                    self.block_positions[(y, x)] = self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]
                    break


    def place_enemies(self):
        """Randomly places enemies within the bounds of the playing field."""
        self.enemy_positions = {}
        max_x = self.width - 2
        max_y = self.height - 2

        for _ in range(self.level + self.INITIAL_NUM_ENEMIES):
            while True:
                x = random.randint(1, max_x - 1)
                y = random.randint(1, max_y - 1)
                if (y, x) not in self.block_positions and (y, x) not in self.enemy_positions:
                    self.enemy_positions[(y, x)] = self.CHARACTER_MAP[self.ENEMY]
                    break

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
        """Find the position farthest from any enemy or block, with enemies weighted more heavily."""
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
        # Initialize distances
        distances = [[float('inf') for _ in range(self.width)] for _ in range(self.height)]
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
        """Main game loop with strict enemy movement delay."""
        last_enemy_move_time = time.time()

        self.stdscr.nodelay(True)  # Non-blocking getch()

        while True:
            current_time = time.time()

            # Render the current state (without options line)
            self.render()

            # Handle input without blocking the loop
            if self.handle_input():
                break

            # Strictly check if it's time to move the enemies
            time_since_last_move = current_time - last_enemy_move_time

            if time_since_last_move >= self.ENEMY_MOVE_DELAY / 1000.0:
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

    def render(self, show_options=False):
        """Renders the game state to the screen using characters from CHARACTER_MAP."""
        self.stdscr.clear()

        # Display blocks
        for pos, char in self.block_positions.items():
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                # Use the correct color pair for unmovable blocks
                if char == self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]:
                    self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.UNPUSHABLE_BLOCK))
                else:
                    self.stdscr.addstr(pos[0], pos[1] * 2, char, curses.color_pair(self.BLOCK))

        # Display enemies
        for pos in self.enemy_positions:
            if 0 <= pos[0] < self.height - 2 and 0 <= pos[1] < self.width:
                self.stdscr.addstr(pos[0], pos[1] * 2, self.CHARACTER_MAP[self.ENEMY], curses.color_pair(self.ENEMY))

        # Display hero
        if 0 <= self.hero_pos[0] < self.height - 2 and 0 <= self.hero_pos[1] < self.width:
            self.stdscr.addstr(self.hero_pos[0], self.hero_pos[1] * 2, self.CHARACTER_MAP[self.HERO], curses.color_pair(self.HERO))

        # Draw the unbreakable block line above the status line
        for x in range(self.width):
            self.stdscr.addstr(self.height - 3, x * 2, self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK], curses.color_pair(self.UNPUSHABLE_BLOCK))

        # Calculate if there's room for the status line
        elapsed_time = int(self.paused_time + (time.time() - self.start_time) if not self.paused else self.paused_time)
        minutes = elapsed_time // 60
        seconds = elapsed_time % 60
        enemy_count = len(self.enemy_positions)
        status_line = f"Enemies: {enemy_count}  |  Time: {minutes:02}:{seconds:02}  |  Lives: {self.lives}  |  Score: {self.score} ({self.rank})"

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

    def move_hero(self, dy, dx):
        """Move the hero in the specified direction, handling block pushing."""
        new_y = self.hero_pos[0] + dy
        new_x = self.hero_pos[1] + dx
        next_pos = (new_y, new_x)

        # If the next position is within bounds:
        if 0 <= new_y < self.height and 0 <= new_x < self.width:
            # Check if the next position is a block that potentially needs pushing
            if next_pos in self.block_positions:
                block_type = self.block_positions[next_pos]
                if block_type == self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]:
                    return  # Unmovable block, hero can't move it
                elif self.can_push_blocks(new_y, new_x, dy, dx):
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

        # Check if the next position is within bounds
        if not (0 <= next_y < self.height and 0 <= next_x < self.width):
            return False  # Stop if the next position is out of bounds

        # Check if the block is unmovable
        if next_pos in self.block_positions:
            block_type = self.block_positions[next_pos]
            if block_type == self.CHARACTER_MAP[self.UNPUSHABLE_BLOCK]:
                return False  # Unmovable block, can't push

        # Check if the next space contains an enemy
        if next_pos in self.enemy_positions:
            # If there's no block behind the enemy, stop the push
            behind_enemy_y = next_y + dy
            behind_enemy_x = next_x + dx
            if not (0 <= behind_enemy_y < self.height and 0 <= behind_enemy_x < self.width):
                return False  # Stop if behind the enemy is out of bounds
            if (behind_enemy_y, behind_enemy_x) not in self.block_positions:
                return False  # Stop if there is no block behind the enemy

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


    def move_enemies(self):
        """Move enemies towards the hero using BFS or randomly if no path is found."""
        new_positions = {}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

        for pos, enemy_char in self.enemy_positions.items():
            path = self.bfs_find_path(pos, self.hero_pos)
            if len(path) > 1:  # Path found, move towards hero
                next_pos = path[1]
                if next_pos not in self.block_positions and next_pos not in new_positions:
                    new_positions[next_pos] = enemy_char
                else:
                    new_positions[pos] = enemy_char
            else:  # No path found, move randomly
                random.shuffle(directions)
                for dy, dx in directions:
                    next_pos = (pos[0] + dy, pos[1] + dx)
                    if (0 <= next_pos[0] < self.height and
                        0 <= next_pos[1] < self.width and
                        next_pos not in self.block_positions and
                        next_pos not in new_positions):
                        new_positions[next_pos] = enemy_char
                        break
                else:
                    new_positions[pos] = enemy_char  # Stay in place if no move is possible

        self.enemy_positions = new_positions


    def check_collisions(self):
        """Check for collisions between the hero and enemies."""
        hero_pos_tuple = (self.hero_pos[0], self.hero_pos[1])
        if hero_pos_tuple in self.enemy_positions:
            self.handle_hero_collision()

    def handle_hero_collision(self):
        """Handle what happens when the hero collides with an enemy."""
        self.play_sound('collision.wav')  # Play collision sound

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
            color = curses.color_pair(self.UNPUSHABLE_BLOCK) if int(score) == self.score else curses.color_pair(self.BLOCK)
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
    game = Game(stdscr)
    game.main_loop()

if __name__ == "__main__":
    curses.wrapper(main)
