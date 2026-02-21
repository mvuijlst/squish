import pygame
import json
import os
import utils
import config

_sprite_sheet = None
_sounds = {}
_levels_data = []
_current_spritesheet_path = config.DEFAULT_SPRITESHEET

def load_sprite_sheet(filename=None):
    """Loads the specified sprite sheet, or the current default."""
    global _sprite_sheet, _current_spritesheet_path
    if filename is None:
        filename = _current_spritesheet_path
    else:
         _current_spritesheet_path = filename # Update if a specific one is requested

    actual_path = utils.resource_path(filename)
    try:
        _sprite_sheet = pygame.image.load(actual_path).convert_alpha()
        print(f"Loaded spritesheet: {filename}")
    except pygame.error as e:
        print(f"ERROR: Cannot load spritesheet '{filename}': {e}")
        # Optionally create a dummy surface or raise an error
        _sprite_sheet = pygame.Surface((config.SHEET_COLS * config.CHAR_WIDTH, config.SHEET_ROWS * config.CHAR_HEIGHT), pygame.SRCALPHA)


def get_sprite_sheet():
    """Returns the currently loaded sprite sheet surface."""
    if _sprite_sheet is None:
        load_sprite_sheet() # Load default if not loaded yet
    return _sprite_sheet

def toggle_spritesheet():
    """Swaps between the default and alternative spritesheets."""
    global _current_spritesheet_path
    if _current_spritesheet_path == config.DEFAULT_SPRITESHEET:
        load_sprite_sheet(config.ALT_SPRITESHEET)
    else:
        load_sprite_sheet(config.DEFAULT_SPRITESHEET)

def load_sounds():
    """Loads all game sounds."""
    global _sounds
    sound_files = {
        'squish':            config.SOUND_SQUISH,
        'collision':         config.SOUND_COLLISION,
        'level_complete':    config.SOUND_LEVEL_COMPLETE,
        'sublevel_complete': config.SOUND_SUBLEVEL_COMPLETE,
        'powerup':           config.SOUND_POWERUP,   # v5 – power-up pickup
    }
    for name, filename in sound_files.items():
        path = utils.resource_path(filename)
        if os.path.exists(path):
            try:
                _sounds[name] = pygame.mixer.Sound(path)
            except pygame.error as e:
                 print(f"ERROR: Cannot load sound '{filename}': {e}")
                 _sounds[name] = None
        else:
            print(f"WARN: Sound file not found: {filename}")
            _sounds[name] = None

def get_sound(name):
    """Gets a pre-loaded sound object by name."""
    sound = _sounds.get(name)
    if sound:
        return sound
    else:
        # Return a dummy object that doesn't crash when play() is called
        class DummySound:
            def play(self): pass
        return DummySound()


def load_levels_json(filename="levels.json"):
    """Loads level definitions from a JSON file."""
    global _levels_data
    path = utils.resource_path(filename)
    if not os.path.exists(path):
        print(f"ERROR: Cannot find level file '{filename}'. Using empty levels data.")
        _levels_data = []
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            _levels_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse level file '{filename}': {e}")
        _levels_data = []
    except Exception as e:
        print(f"ERROR: Could not read level file '{filename}': {e}")
        _levels_data = []


def get_levels_data():
    """Returns the loaded levels data."""
    if not _levels_data:
        load_levels_json() # Attempt to load if empty
    return _levels_data

def get_level_letters():
    """Returns a sorted list of unique level letters from the loaded data."""
    return sorted({ entry.get("level") for entry in get_levels_data() if entry.get("level") })

def get_main_level_def(level_letter):
    """Gets the full definition for a main level letter."""
    levels = get_levels_data()
    for entry in levels:
        if entry.get("level") == level_letter:
            # Provide defaults for missing keys
            default = {
                "level": level_letter,
                "pull_blocks": False,
                "speed_up": False,
                "explosive_blocks": False,
                "winning_level": 1,
                "enemies": {},
                "egg_incubation_ms": 0 # Default, will be overridden below if needed
            }
            default.update(entry) # Update defaults with loaded data

            # Compatibility/Convenience: Calculate egg_incubation_ms from seconds if needed
            if default["egg_incubation_ms"] == 0:
                egg_def = default.get("enemies", {}).get("egg", {})
                incubation_s = egg_def.get("incubation_s", 0)
                default["egg_incubation_ms"] = incubation_s * 1000

            return default

    # Return a minimal default if the level letter is not found
    print(f"WARN: Level definition for '{level_letter}' not found. Using default.")
    return {
        "level": level_letter,
        "pull_blocks": False,
        "speed_up": False,
        "explosive_blocks": False,
        "winning_level": 1,
        "enemies": {},
        "egg_incubation_ms": 0
    }
