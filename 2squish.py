import curses
import random
import time

# Abstract playing field that manages logical grid vs. screen positions
class PlayingField:
    def __init__(self, width, height):
        self.width = width  # Logical width in blocks
        self.height = height  # Logical height in rows

    def to_screen_x(self, logical_x):
        """Convert logical x position to screen x position (double-width)."""
        return logical_x * 2

    def to_screen_y(self, logical_y):
        """Convert logical y position to screen y position (single height)."""
        return logical_y

    def is_in_bounds(self, logical_x, logical_y):
        """Check if a position is within the playing field bounds."""
        return 0 <= logical_x < self.width and 0 <= logical_y < self.height

# Base class for all game objects
class GameObject:
    def __init__(self, logical_x, logical_y, symbol, color, playing_field):
        self.logical_x = logical_x
        self.logical_y = logical_y
        self.symbol = symbol
        self.color = color
        self.playing_field = playing_field

    def move(self, dx, dy):
        new_x = self.logical_x + dx
        new_y = self.logical_y + dy
        if self.playing_field.is_in_bounds(new_x, new_y):
            self.logical_x = new_x
            self.logical_y = new_y

    def draw(self, screen, clear_old=True):
        if clear_old:
            screen.addstr(self.playing_field.to_screen_y(self.logical_y), 
                          self.playing_field.to_screen_x(self.logical_x), '  ')
        screen_x = self.playing_field.to_screen_x(self.logical_x)
        screen_y = self.playing_field.to_screen_y(self.logical_y)
        screen.addstr(screen_y, screen_x, self.symbol, curses.color_pair(self.color))

    def get_position(self):
        return self.logical_x, self.logical_y

    def get_object_at(self, x, y, objects):
        """Return the object at the specified position, or None if empty."""
        for obj in objects:
            if obj.logical_x == x and obj.logical_y == y:
                return obj
        return None

class Hero(GameObject):
    def __init__(self, logical_x, logical_y, playing_field):
        super().__init__(logical_x, logical_y, "◄►", curses.COLOR_CYAN, playing_field)

    def handle_input(self, key, blocks, enemies):
        if key == curses.KEY_UP:
            self.try_move(0, -1, blocks, enemies)
        elif key == curses.KEY_DOWN:
            self.try_move(0, 1, blocks, enemies)
        elif key == curses.KEY_LEFT:
            self.try_move(-1, 0, blocks, enemies)
        elif key == curses.KEY_RIGHT:
            self.try_move(1, 0, blocks, enemies)

    def try_move(self, dx, dy, blocks, enemies):
        target_x = self.logical_x + dx
        target_y = self.logical_y + dy
        block = self.get_object_at(target_x, target_y, blocks)
        if block:
            if self.can_push_blocks(block, dx, dy, blocks, enemies):
                self.push_blocks(block, dx, dy, blocks)
                self.move(dx, dy)
                self.check_for_squished_enemies(block, blocks, enemies)
        else:
            self.move(dx, dy)

    def can_push_blocks(self, block, dx, dy, blocks, enemies):
        current_block = block
        while current_block:
            next_x = current_block.logical_x + dx
            next_y = current_block.logical_y + dy
            next_obj = self.get_object_at(next_x, next_y, blocks + enemies)
            if next_obj is None:
                current_block = None
            elif isinstance(next_obj, Block) and next_obj.symbol == "░░":
                current_block = next_obj
            elif isinstance(next_obj, Enemy):
                next_x = next_obj.logical_x + dx
                next_y = next_obj.logical_y + dy
                obstacle = self.get_object_at(next_x, next_y, blocks)
                if obstacle or not self.playing_field.is_in_bounds(next_x, next_y):
                    enemies.remove(next_obj)
                    return True
                else:
                    return False
            else:
                return False
        return True

    def push_blocks(self, block, dx, dy, blocks):
        push_list = []
        current_block = block
        while current_block:
            push_list.append(current_block)
            next_x = current_block.logical_x + dx
            next_y = current_block.logical_y + dy
            current_block = self.get_object_at(next_x, next_y, blocks)
        for block in reversed(push_list):
            block.move(dx, dy)

    def check_for_squished_enemies(self, block, blocks, enemies):
        """Check if a block has squished any enemies against a wall or another block."""
        for enemy in enemies[:]:
            if enemy.logical_x == block.logical_x and enemy.logical_y == block.logical_y:
                next_x = block.logical_x + (block.logical_x - self.logical_x)
                next_y = block.logical_y + (block.logical_y - self.logical_y)
                obstacle = self.get_object_at(next_x, next_y, blocks)
                if obstacle or not self.playing_field.is_in_bounds(next_x, next_y):
                    enemies.remove(enemy)

class Enemy(GameObject):
    def __init__(self, logical_x, logical_y, symbol, color, playing_field):
        super().__init__(logical_x, logical_y, symbol, color, playing_field)
        self.move_delay = 0.5
        self.last_move_time = time.time()

    def update(self, hero_position, blocks):
        if time.time() - self.last_move_time > self.move_delay:
            self.last_move_time = time.time()
            self.do_move(hero_position, blocks)

class Hunter(Enemy):
    def do_move(self, hero_position, blocks):
        hero_x, hero_y = hero_position
        dx = 1 if hero_x > self.logical_x else -1 if hero_x < self.logical_x else 0
        dy = 1 if hero_y > self.logical_y else -1 if hero_y < self.logical_y else 0
        if not self.get_object_at(self.logical_x + dx, self.logical_y + dy, blocks):
            self.move(dx, dy)

class Crusher(Enemy):
    def do_move(self, hero_position, blocks):
        hero_x, hero_y = hero_position
        dx = 1 if hero_x > self.logical_x else -1 if hero_x < self.logical_x else 0
        dy = 1 if hero_y > self.logical_y else -1 if hero_y < self.logical_y else 0
        target_x = self.logical_x + dx
        target_y = self.logical_y + dy
        block = self.get_object_at(target_x, target_y, blocks)
        if not block:
            self.move(dx, dy)
        elif isinstance(block, Block) and block.symbol == "░░":
            block.move(dx, dy)
            self.move(dx, dy)

class Sentinel(Enemy):
    def do_move(self, hero_position, blocks):
        hero_x, _ = hero_position
        dx = 1 if hero_x > self.logical_x else -1 if hero_x < self.logical_x else 0
        if dx != 0 and not self.get_object_at(self.logical_x + dx, self.logical_y, blocks):
            self.move(dx, 0)

class Block(GameObject):
    def __init__(self, logical_x, logical_y, playing_field, movable=True):
        symbol = "░░" if movable else "██"
        color = curses.COLOR_BLUE if movable else curses.COLOR_WHITE
        super().__init__(logical_x, logical_y, symbol, color, playing_field)

    def move(self, dx, dy):
        new_x = self.logical_x + dx
        new_y = self.logical_y + dy
        if not self.playing_field.is_in_bounds(new_x, new_y):
            return False
        self.logical_x = new_x
        self.logical_y = new_y
        return True

class Level:
    def __init__(self, width, height, playing_field):
        self.width = width
        self.height = height
        self.enemies = []
        self.blocks = []
        self.playing_field = playing_field

    def generate_blocks(self, coverage=0.3, unmovable_ratio=0.1):
        num_blocks = int(coverage * self.width * self.height)
        num_unmovable = int(num_blocks * unmovable_ratio)
        for _ in range(num_blocks):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self.blocks.append(Block(x, y, self.playing_field, movable=len(self.blocks) >= num_unmovable))

    def generate_enemies(self, num_enemies):
        for _ in range(num_enemies):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            enemy_type = random.choice([Hunter, Crusher, Sentinel])
            self.enemies.append(enemy_type(x, y, self.playing_field))

class Game:
    def __init__(self, screen, level, playing_field):
        self.screen = screen
        self.hero = Hero(5, 5, playing_field)
        self.level = level
        self.enemies = level.enemies
        self.blocks = level.blocks

    def update(self):
        """Update all game objects, including enemies."""
        hero_position = self.hero.get_position()
        for enemy in self.enemies:
            enemy.update(hero_position, self.blocks)

    def draw(self):
        """Draw all game objects onto the screen."""
        self.screen.clear()
        self.hero.draw(self.screen)
        for enemy in self.enemies:
            enemy.draw(self.screen)
        for block in self.blocks:
            block.draw(self.screen)
        self.screen.refresh()

    def run(self):
        """Main game loop."""
        while True:
            key = self.screen.getch()
            self.hero.handle_input(key, self.blocks, self.enemies)
            self.update()
            self.draw()
            time.sleep(0.1)

def main(stdscr):
    """Initialize curses and start the game."""
    curses.start_color()
    curses.init_pair(curses.COLOR_CYAN, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_RED, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_YELLOW, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_MAGENTA, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_GREEN, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_BLUE, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_BLACK)

    # Setup the playing field and level
    playing_field = PlayingField(40, 24)  # Logical grid size: 40x24
    level = Level(40, 24, playing_field)
    level.generate_blocks(coverage=0.3, unmovable_ratio=0.1)  # Generate blocks with some immovable ones
    level.generate_enemies(5)  # Add 5 random enemies (Hunters, Crushers, Sentinels)

    # Create and run the game
    game = Game(stdscr, level, playing_field)
    game.run()

# Run the game with curses
if __name__ == "__main__":
    curses.wrapper(main)
