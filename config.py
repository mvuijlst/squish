import pygame

# 1) BASIC CONFIGURATION
EMPTY = 0
PLAYER = 1
MOVEABLE_BLOCK = 2
UNMOVEABLE_BLOCK = 3
HUNTER = 4
EGG = 5
PUSHER = 6
SENTINEL = 7
POWERUP = 8           # v5: collectible power-up item

# Power-up sub-types
POWERUP_SLOW       = 'slow'        # Slows all enemies for 8 seconds
POWERUP_SHIELD     = 'shield'      # Absorbs the next lethal hit
POWERUP_EXTRA_LIFE = 'extra_life'  # +1 life (capped at MAX_LIVES)

GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE * 2      # v5: doubled status bar height for extra info
MAX_LIVES   = 5                    # v5: cap on maximum lives

CHAR_WIDTH  = 8
CHAR_HEIGHT = 16
SCALE_X = 2
SCALE_Y = 2
SHEET_COLS = 16
SHEET_ROWS = 16

HUNTER_VALUE   = 2
EGG_VALUE      = 3
PUSHER_VALUE   = 5
SENTINEL_VALUE = 7
POWERUP_SCORE  = 1  # small score bonus for picking up a power-up

# 2) COLOR DEFINITIONS
TEXT_COLOR_DEFAULT = (0xa7, 0xa7, 0xa7)
HIGHLIGHT_COLOR    = (0xfa, 0xfa, 0xfa)

PLAYER_COLOR   = (0x59, 0xe1, 0xe3)
WALL_COLOR     = (0xff, 0xea, 0x16)
BLOCK_COLOR    = (0x00, 0x55, 0x00)

HUNTER_COLOR   = (0xff, 0x16, 0xb0)
EGG_COLOR_0    = (0xfa, 0xe9, 0x01)
EGG_COLOR_1    = (0xfa, 0x82, 0x01)
EGG_COLOR_FLASH1 = (0xfa, 0x01, 0x01)
EGG_COLOR_FLASH2 = (0xff, 0xff, 0xff)
PUSHER_COLOR   = (0x99, 0x35, 0xff)
SENTINEL_COLOR = (0x47, 0x52, 0xcb)

# v5 power-up colours
POWERUP_SLOW_COLOR       = (0x00, 0xff, 0xff)   # Cyan   – slow enemies
POWERUP_SHIELD_COLOR     = (0x00, 0xff, 0x44)   # Green  – absorb one hit
POWERUP_EXTRA_LIFE_COLOR = (0xff, 0xff, 0x00)   # Yellow – extra life

STATUS_BG_COLOR = (0x00, 0x00, 0x00)

# 7) ENTITY MAPPINGS (Character representations)
WALL_CHARS     = "\xDB\xDB"
BLOCK0_CHARS   = "\xB0\xB0"
BLOCK1_CHARS   = "\xB1\xB1"
BLOCK2_CHARS   = "\xB2\xB2"
PLAYER_CHARS   = "\x11\x10"
HUNTER_CHARS   = "\xC3\xB4"
EGG_CHARS      = "\x09\x09"
EMPTY_CHARS    = "  "
PUSHER_CHARS   = "\xCE\xCE"
SENTINEL_CHARS = "\xC7\xB6"
POWERUP_SLOW_CHARS       = "\x0F\x0F"  # ☼ speed/slow icon
POWERUP_SHIELD_CHARS     = "\x01\x01"  # ☺ shield icon
POWERUP_EXTRA_LIFE_CHARS = "\x03\x03"  # ♥ heart icon

# High Score Config
SCORE_FILE = "highscores.dat"
XOR_KEY = 0xAA
MAX_HIGH_SCORES = 20
MAX_LEVEL_HIGH_SCORES = 5

# Spritesheet Config
DEFAULT_SPRITESHEET = "dos_spritesheet.png"
ALT_SPRITESHEET = "st_spritesheet.png"

# Sound Files
SOUND_SQUISH           = "sound/squish.mp3"
SOUND_COLLISION        = "sound/collision.mp3"
SOUND_LEVEL_COMPLETE   = "sound/level.mp3"
SOUND_SUBLEVEL_COMPLETE= "sound/sublevel.mp3"
SOUND_EXPLOSION        = "sound/explosion.mp3"
SOUND_POWERUP          = "sound/powerup.mp3"   # v5 – power-up pickup (optional)

# Other
GAME_TITLE = "S Q U I S H  v5.0"
COPYRIGHT_TEXT = "(c) 2025 Michel Vuijlsteke"

# v5 – Combo system
COMBO_TIMEOUT_MS  = 3000   # ms window between kills to maintain combo
COMBO_DISPLAY_MS  = 1500   # how long to show the combo text after last kill

# v5 – Speed-up per sublevel (implements the 'speed_up' flag in levels.json)
SPEED_UP_FACTOR   = 0.90   # enemy speed_ms is multiplied by this each sublevel
SPEED_UP_MIN_MS   = 150    # hard floor so enemies never become impossibly fast

# v5 – Slow power-up duration
POWERUP_SLOW_DURATION_MS  = 8000   # 8 seconds of slowed enemies
POWERUP_FLASH_DURATION_MS = 5000   # how long the shield-flash lasts visually
