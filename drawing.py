import math
import pygame
import config
import utils
import resources
# Need to import GameState if it's defined elsewhere, or assume it's passed correctly
# from squish import GameState # Example if GameState is in squish.py

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

# Moved from squish.py - needed by draw_grid
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
    elif t == config.POWERUP:
        # v5: choose chars based on power-up sub-type
        ptype = cell[1] if isinstance(cell, tuple) and len(cell) > 1 else None
        if ptype == config.POWERUP_SLOW:       return config.POWERUP_SLOW_CHARS
        elif ptype == config.POWERUP_SHIELD:   return config.POWERUP_SHIELD_CHARS
        elif ptype == config.POWERUP_EXTRA_LIFE: return config.POWERUP_EXTRA_LIFE_CHARS
        return "\x0F\x0F"  # fallback
    else: return "??"

# Moved from squish.py
def draw_grid(screen, grid):
    """Draws the main game grid."""
    screen.fill((0, 0, 0)) # Clear screen
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            cell_content = grid[y][x]
            cell_str = get_cell_string(cell_content) # Use local function
            color = utils.get_cell_color(cell_content)
            px = x * (config.CHAR_WIDTH * config.SCALE_X * 2) # Double char width for cells
            py = y * (config.CHAR_HEIGHT * config.SCALE_Y)
            draw_text(screen, cell_str, px, py, color) # Use local function

# Updated to accept GameState object
def draw_status_line(screen, grid, game_state): # game_state replaces multiple parameters
    """Draws the status bar at the bottom using GameState."""
    status_y = config.GRID_HEIGHT * (config.CHAR_HEIGHT * config.SCALE_Y)
    status_area_rect = pygame.Rect(0, status_y, screen.get_width(), config.STATUS_HEIGHT)
    screen.fill(config.STATUS_BG_COLOR, status_area_rect)

    # Get values from game_state
    elapsed_seconds = game_state.get_elapsed_time()
    time_str = utils.format_time(elapsed_seconds)
    current_lives = game_state.lives
    level_name = game_state.current_level_name
    current_score = game_state.score
    initial_egg_count = game_state.initial_egg_count

    current_enemy_count = sum(1 for row in grid for cell in row
                              if utils.cell_type(cell) in
                              [config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG])

    # --- Row 1: classic stats ---
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
    row1_y = status_y + (config.CHAR_HEIGHT * config.SCALE_Y) // 4

    for text, col in segments:
        draw_text(screen, text, x, row1_y, col)
        x += len(text) * config.CHAR_WIDTH * config.SCALE_X

    # --- Row 2: v5 status indicators (shield, slow, controls hint) ---
    now = utils.get_game_time()
    row2_y = status_y + config.CHAR_HEIGHT * config.SCALE_Y + (config.CHAR_HEIGHT * config.SCALE_Y) // 4

    indicators = []
    if game_state.shield_active:
        indicators.append(("\x01 SHIELD", config.POWERUP_SHIELD_COLOR))
    if game_state.slow_active_until > now:
        remaining = (game_state.slow_active_until - now) // 1000
        indicators.append((f"\x0F SLOW {remaining}s", config.POWERUP_SLOW_COLOR))

    hint = "Arrows:move  Shift+arrow:pull  ESC:pause  Q:quit"
    hint_x = 5
    draw_text(screen, hint, hint_x, row2_y, config.TEXT_COLOR_DEFAULT)

    if indicators:
        ind_x = screen.get_width() - 5
        for text, col in reversed(indicators):
            w = len(text) * config.CHAR_WIDTH * config.SCALE_X
            ind_x -= w + 10
            draw_text(screen, text, ind_x, row2_y, col)


# ---------------------------------------------------------------------------
# v5 -- OVERLAY DRAWING HELPERS
# ---------------------------------------------------------------------------

def draw_particles(screen, particles, now):
    """Draws live particle effects and removes expired ones in-place."""
    alive = []
    for p in particles:
        age = now - p['birth']
        if age >= p['lifetime']:
            continue  # expired
        alive.append(p)
        # Compute current position from spawn + velocity * elapsed time
        draw_x = p['px'] + p['vx'] * age / 1000.0
        draw_y = p['py'] + p['vy'] * age / 1000.0
        # Fade out toward end of lifetime
        alpha = max(0, 255 - int(255 * age / p['lifetime']))
        r, g, b = p['color']
        try:
            surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            surf.fill((r, g, b, alpha))
            screen.blit(surf, (int(draw_x), int(draw_y)))
        except Exception:
            pass
    # Shrink the particles list in-place
    particles[:] = alive


def draw_flash(screen, flash_until, flash_color, now):
    """Draws a fading colour flash overlay (e.g. red on death)."""
    if flash_until <= now:
        return
    flash_window = 500  # total duration in ms
    remaining = flash_until - now
    alpha = int(160 * remaining / flash_window)
    alpha = max(0, min(160, alpha))
    try:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        r, g, b = flash_color
        overlay.fill((r, g, b, alpha))
        screen.blit(overlay, (0, 0))
    except Exception:
        pass


def draw_combo_text(screen, combo_count, last_kill_time, now):
    """Draws the combo multiplier text near the centre of the screen."""
    if combo_count < 2:
        return
    age = now - last_kill_time
    if age > config.COMBO_DISPLAY_MS:
        return
    # Fade out
    alpha_ratio = 1.0 - age / config.COMBO_DISPLAY_MS
    base_colors = [(0xff, 0xff, 0x00), (0xff, 0xa0, 0x00), (0xff, 0x40, 0x00)]
    color = base_colors[min(combo_count - 2, len(base_colors) - 1)]
    r, g, b = color
    r = int(r * alpha_ratio)
    g = int(g * alpha_ratio)
    b = int(b * alpha_ratio)
    msg = f"COMBO x{combo_count}!"
    cw = config.CHAR_WIDTH * config.SCALE_X
    ch = config.CHAR_HEIGHT * config.SCALE_Y
    x = (screen.get_width() - len(msg) * cw) // 2
    y = screen.get_height() // 2 - ch * 3
    draw_text(screen, msg, x, y, (r, g, b))


def draw_wave_banner(screen, banner_text, banner_until, now):
    """Draws the 'ROUND X' banner that appears at the start of each sublevel."""
    if not banner_text or banner_until <= now:
        return
    total = 2000  # must match value in play_sublevel
    age = total - (banner_until - now)
    # Fade in for first 400ms, stay, then fade out last 400ms
    fade_ms = 400
    if age < fade_ms:
        alpha_ratio = age / fade_ms
    elif (banner_until - now) < fade_ms:
        alpha_ratio = (banner_until - now) / fade_ms
    else:
        alpha_ratio = 1.0
    alpha_ratio = max(0.0, min(1.0, alpha_ratio))

    r = int(0xff * alpha_ratio)
    g = int(0xff * alpha_ratio)
    b = int(0x00 * alpha_ratio)
    color = (r, g, b) if (r + g + b) > 0 else (1, 1, 0)

    cw = config.CHAR_WIDTH * config.SCALE_X
    ch = config.CHAR_HEIGHT * config.SCALE_Y
    x = (screen.get_width() - len(banner_text) * cw) // 2
    y = screen.get_height() // 2 - ch * 2
    draw_text(screen, banner_text, x, y, color)
