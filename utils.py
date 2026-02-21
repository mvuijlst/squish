import os
import sys
import pygame
import config

# Keep track of pause duration globally within utils or pass Game state around
_global_pause_offset = 0

############################################################
# RESOURCE PATH HELPER
############################################################
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller --onefile.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

############################################################
# TYPE & TIME HELPERS
############################################################
def cell_type(cell):
    """Returns the type identifier of a grid cell."""
    if isinstance(cell, tuple):
        return cell[0]
    return cell

def get_game_time():
    """Gets the current game time, adjusted for pauses."""
    return pygame.time.get_ticks() - _global_pause_offset

def add_pause_offset(duration):
    """Increases the global pause offset."""
    global _global_pause_offset
    _global_pause_offset += duration

def reset_pause_offset():
    """Resets the global pause offset."""
    global _global_pause_offset
    _global_pause_offset = 0

############################################################
# GRAPHICS HELPERS
############################################################
def tint_surface(surface, tint_color):
    """Tints a Pygame surface with a given color."""
    tinted = surface.copy()
    tinted.fill(tint_color, special_flags=pygame.BLEND_RGBA_MULT)
    return tinted

def get_egg_color(cell):
    """Determines the color of an egg based on its incubation progress."""
    now = get_game_time()
    egg_total_time = cell[1]
    egg_start = cell[2]
    elapsed = now - egg_start
    if elapsed < 0: elapsed = 0 # Should not happen with proper pause handling

    progress = elapsed / egg_total_time if egg_total_time > 0 else 1.0

    if progress < 0.75:
        return config.EGG_COLOR_0
    elif progress < 0.90:
        return config.EGG_COLOR_1
    else:
        # Flash quickly when about to hatch
        flash_period = 250  # milliseconds
        flashes = (now // flash_period) % 2
        return config.EGG_COLOR_FLASH1 if flashes == 0 else config.EGG_COLOR_FLASH2

def get_cell_color(cell):
    """Gets the display color for a given grid cell."""
    t = cell_type(cell)
    if t == config.PLAYER:
        return config.PLAYER_COLOR
    elif t == config.UNMOVEABLE_BLOCK:
        return config.WALL_COLOR
    elif t == config.MOVEABLE_BLOCK:
        return config.BLOCK_COLOR
    elif t == config.HUNTER:
        return config.HUNTER_COLOR
    elif t == config.EGG:
        return get_egg_color(cell)
    elif t == config.PUSHER:
        return config.PUSHER_COLOR
    elif t == config.SENTINEL:
        return config.SENTINEL_COLOR
    elif t == config.POWERUP:
        # v5: colour depends on powerup sub-type stored in cell[1]
        ptype = cell[1] if isinstance(cell, tuple) and len(cell) > 1 else None
        if ptype == config.POWERUP_SLOW:
            return config.POWERUP_SLOW_COLOR
        elif ptype == config.POWERUP_SHIELD:
            return config.POWERUP_SHIELD_COLOR
        elif ptype == config.POWERUP_EXTRA_LIFE:
            return config.POWERUP_EXTRA_LIFE_COLOR
        return (0xff, 0xff, 0xff)  # fallback white
    return (0, 0, 0) # Default to black for EMPTY or unknown

############################################################
# FORMATTING & ENCRYPTION
############################################################
def format_time(seconds: int) -> str:
    """Formats seconds into MM:SS string."""
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes:02}:{sec:02}"

def encrypt_xor(data: bytes, key: int = config.XOR_KEY) -> bytes:
    """Simple XOR encryption."""
    return bytes(b ^ key for b in data)

def decrypt_xor(data: bytes, key: int = config.XOR_KEY) -> bytes:
    """Simple XOR decryption."""
    return encrypt_xor(data, key) # XORing twice decrypts

############################################################
# INPUT HELPERS
############################################################
def wait_for_key():
    """Waits until any key is pressed."""
    waiting = True
    clock = pygame.time.Clock()
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                 pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                waiting = False
        clock.tick(15) # Keep CPU usage low
