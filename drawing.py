import pygame
import config
import utils
import resources

# Cache the sprite sheet locally in this module for performance
_sprite_sheet_cache = None

def _get_sprite_sheet():
    """Internal helper to get the cached sprite sheet."""
    global _sprite_sheet_cache
    if _sprite_sheet_cache is None:
        _sprite_sheet_cache = resources.get_sprite_sheet()
        if _sprite_sheet_cache is None:
             print("ERROR in drawing: Sprite sheet not loaded.")
             # Return a dummy surface to prevent crashes, though drawing will fail
             return pygame.Surface((1,1))
    return _sprite_sheet_cache

def invalidate_sprite_sheet_cache():
    """Call this if the sprite sheet is reloaded (e.g., toggled)."""
    global _sprite_sheet_cache
    _sprite_sheet_cache = None


def draw_char(surface, ch, x, y, color):
    """Draws a single character using the loaded sprite sheet."""
    sprite_sheet = _get_sprite_sheet()
    if not sprite_sheet or surface is None: return # Safety check

    code = ord(ch)
    if not (0 <= code <= 255): code = 127 # Use a default char for out-of-range

    col = code % config.SHEET_COLS
    row = code // config.SHEET_COLS
    sx = col * config.CHAR_WIDTH
    sy = row * config.CHAR_HEIGHT

    char_rect = pygame.Rect(sx, sy, config.CHAR_WIDTH, config.CHAR_HEIGHT)

    try:
        # Create a temporary surface for the character to allow tinting
        char_surf = pygame.Surface((config.CHAR_WIDTH, config.CHAR_HEIGHT), pygame.SRCALPHA)
        char_surf.blit(sprite_sheet, (0, 0), char_rect)

        # Scale
        scaled_w = config.CHAR_WIDTH * config.SCALE_X
        scaled_h = config.CHAR_HEIGHT * config.SCALE_Y
        char_surf = pygame.transform.scale(char_surf, (scaled_w, scaled_h))

        # Tint
        char_surf = utils.tint_surface(char_surf, color)

        surface.blit(char_surf, (x, y))
    except pygame.error as e:
        print(f"Error drawing char '{ch}' at ({x},{y}): {e}")
    except Exception as e:
         print(f"Unexpected error drawing char '{ch}' at ({x},{y}): {e}")


def draw_text(surface, text, x, y, color):
    """Draws a string of text using draw_char."""
    offset_x = 0
    for ch in text:
        draw_char(surface, ch, x + offset_x, y, color)
        offset_x += config.CHAR_WIDTH * config.SCALE_X

def draw_grid(screen, grid):
    """Draws the main game grid."""
    screen.fill((0, 0, 0)) # Clear screen
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            cell_content = grid[y][x]
            cell_str = get_cell_string(cell_content) # Need this function here or imported
            color = utils.get_cell_color(cell_content)
            px = x * (config.CHAR_WIDTH * config.SCALE_X * 2) # Double char width for cells
            py = y * (config.CHAR_HEIGHT * config.SCALE_Y)
            draw_text(screen, cell_str, px, py, color)

# Helper needed by draw_grid - TODO: Move get_cell_string to a more appropriate module if needed
def get_cell_string(cell):
    """Gets the character pair representation for a grid cell."""
    t = utils.cell_type(cell)
    if t == config.EMPTY: return config.EMPTY_CHARS
    elif t == config.PLAYER: return config.PLAYER_CHARS
    elif t == config.MOVEABLE_BLOCK:
        block_index = cell[1] if isinstance(cell, tuple) and len(cell) > 1 else 0
        if block_index == 0: return config.BLOCK0_CHARS
        elif block_index == 1: return config.BLOCK1_CHARS
        else: return config.BLOCK2_CHARS
    elif t == config.UNMOVEABLE_BLOCK: return config.WALL_CHARS
    elif t == config.HUNTER: return config.HUNTER_CHARS
    elif t == config.EGG: return config.EGG_CHARS
    elif t == config.PUSHER: return config.PUSHER_CHARS
    elif t == config.SENTINEL: return config.SENTINEL_CHARS
    else: return "??"

def draw_status_line(screen, grid, level_start_time, current_lives, level_name, current_score, time_offset):
    """Draws the status bar at the bottom."""
    status_y = config.GRID_HEIGHT * (config.CHAR_HEIGHT * config.SCALE_Y)
    status_area_rect = pygame.Rect(0, status_y, screen.get_width(), config.STATUS_HEIGHT)
    screen.fill(config.STATUS_BG_COLOR, status_area_rect)

    elapsed_seconds = time_offset + (utils.get_game_time() - level_start_time) // 1000
    elapsed_seconds = max(0, elapsed_seconds)
    time_str = utils.format_time(elapsed_seconds)

    current_enemy_count = sum(1 for row in grid for cell in row
                              if utils.cell_type(cell) in
                              [config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG])

    # TODO: Refactor initial_egg_count handling
    initial_egg_count = getattr(draw_status_line, "initial_egg_count", 0)

    segments = []
    segments.append(("Enemies: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{current_enemy_count}", config.HIGHLIGHT_COLOR))

    if initial_egg_count > 0:
        current_egg_count = sum(1 for row in grid for c in row if utils.cell_type(c) == config.EGG)
        segments.append(("  Eggs: ", config.TEXT_COLOR_DEFAULT))
        segments.append((f"{current_egg_count}", config.HIGHLIGHT_COLOR))

    segments.append(("  Level: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{level_name}", config.HIGHLIGHT_COLOR))
    segments.append(("  Time: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{time_str}", config.HIGHLIGHT_COLOR))
    segments.append(("  Lives: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{current_lives}", config.HIGHLIGHT_COLOR))
    segments.append(("  Score: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{current_score}", config.HIGHLIGHT_COLOR))

    total_seg_width = sum(len(text) * config.CHAR_WIDTH * config.SCALE_X for text, col in segments)
    x = screen.get_width() - total_seg_width - 5
    y = status_y + (config.STATUS_HEIGHT - config.CHAR_HEIGHT * config.SCALE_Y) // 2

    for text, col in segments:
        draw_text(screen, text, x, y, col)
        x += len(text) * config.CHAR_WIDTH * config.SCALE_X
