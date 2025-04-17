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

GRID_WIDTH  = 40
GRID_HEIGHT = 25
CELL_SIZE   = 32
STATUS_HEIGHT = CELL_SIZE

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

# High Score Config
SCORE_FILE = "highscores.dat"
XOR_KEY = 0xAA
MAX_HIGH_SCORES = 20
MAX_LEVEL_HIGH_SCORES = 5

# Spritesheet Config
DEFAULT_SPRITESHEET = "dos_spritesheet.png"
ALT_SPRITESHEET = "st_spritesheet.png"

# Sound Files
SOUND_SQUISH = "sound/squish.mp3"
SOUND_COLLISION = "sound/collision.mp3"
SOUND_LEVEL_COMPLETE = "sound/level.mp3"
SOUND_SUBLEVEL_COMPLETE = "sound/sublevel.mp3"
SOUND_EXPLOSION = "sound/explosion.mp3" # Assuming an explosion sound might be added later

# Other
GAME_TITLE = "S Q U I S H  v4.0.1"
COPYRIGHT_TEXT = "(c) 2025 Michel Vuijlsteke"
