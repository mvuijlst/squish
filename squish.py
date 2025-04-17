#############################################
##                                         ##
##          S Q U I S H  v4.0.1            ##
##                                         ##
##      (c) 2025 Michel Vuijlsteke         ##
##                                         ##
#############################################

# Standard library imports
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide" # Hide pygame welcome message
import sys
import pygame
import random
import math
from pygame.locals import *
from heapq import heappush, heappop

# Local module imports
import config
import utils
import resources
import highscore
# Placeholder for future modules
# import drawing
# import entities
# import ui
# import game_logic

# --- TEMPORARY DRAWING FUNCTIONS (to be moved to drawing.py) ---
# These are kept here temporarily until drawing.py is fully implemented
# and imported, to avoid breaking the parts of the code still in this file.

_temp_sprite_sheet_cache = None

def _get_temp_sprite_sheet():
    global _temp_sprite_sheet_cache
    if _temp_sprite_sheet_cache is None:
        _temp_sprite_sheet_cache = resources.get_sprite_sheet()
    return _temp_sprite_sheet_cache

def temp_draw_char(surface, ch, x, y, color):
    sprite_sheet = _get_temp_sprite_sheet()
    if not sprite_sheet: return # Safety check

    code = ord(ch)
    if code < 0 or code > 255: code = 127 # Use a default char for out-of-range

    col = code % config.SHEET_COLS
    row = code // config.SHEET_COLS
    sx = col * config.CHAR_WIDTH
    sy = row * config.CHAR_HEIGHT

    char_rect = pygame.Rect(sx, sy, config.CHAR_WIDTH, config.CHAR_HEIGHT)
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

def temp_draw_text(surface, text, x, y, color):
    offset_x = 0
    for ch in text:
        temp_draw_char(surface, ch, x + offset_x, y, color)
        offset_x += config.CHAR_WIDTH * config.SCALE_X

# Assign to the drawing namespace for compatibility until moved
import drawing as drawing_module # Use alias to avoid conflict if drawing.py exists
drawing_module.draw_text = temp_draw_text
# --- END TEMPORARY DRAWING FUNCTIONS ---


############################################################
# Global Game State (To be moved into a Game class later)
############################################################
lives = 3
current_level = 0 # Perhaps sublevel index?
running_level_score = 0
cumulative_time = 0 # Tracks time across levels in a session
game_over_flag = False
# global_pause_offset is now managed in utils

# High score manager instance
hs_manager = highscore.HighScoreManager()

# Variables to track current sublevel state for high scores upon game over
last_sublevel_name = ""
last_sublevel_start_time = 0
last_sublevel_time_offset = 0


############################################################
# 5b) PAUSE AND QUIT CONFIRMATION (Should move to ui.py)
############################################################
def pause_game(screen):
    # global global_pause_offset # No longer needed, use utils functions
    pause_start = pygame.time.get_ticks() # Use raw ticks for duration calculation
    paused = True
    clock = pygame.time.Clock()

    # Create semi-transparent overlay
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180)) # Black with alpha

    while paused:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key in (K_q, ord('q')):
                    if quit_confirm(screen): # Show confirmation on top of pause
                        return -1  # Signal quit to level select
                elif event.key == K_SPACE:
                    paused = False # Resume game

        # Draw the overlay first
        screen.blit(overlay, (0, 0))

        # Draw pause text on top
        lines = ["Paused", "", "<q> to quit   <space> to continue"]
        total_w = config.GRID_WIDTH * (config.CHAR_WIDTH * config.SCALE_X * 2) # Screen width calculation might need adjustment
        y = screen.get_height() // 2 - 40
        for line in lines:
            lw = len(line) * config.CHAR_WIDTH * config.SCALE_X
            x = (screen.get_width() - lw) // 2 # Center on screen width
            temp_draw_text(screen, line, x, y, config.HIGHLIGHT_COLOR) # Use temp draw
            y += 40

        pygame.display.flip()
        clock.tick(10)

    pause_duration = pygame.time.get_ticks() - pause_start
    utils.add_pause_offset(pause_duration) # Update the offset in utils
    return pause_duration # Return duration for potential use (e.g., adjusting timers)

def quit_confirm(screen) -> bool:
    """Shows a confirmation dialog for quitting."""
    clock = pygame.time.Clock()
    # Create semi-transparent overlay
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200)) # Darker overlay

    confirm = None
    while confirm is None:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key in (K_y, ord('y')):
                    confirm = True
                elif event.key in (K_n, ord('n'), K_ESCAPE): # Allow Esc to cancel
                    confirm = False
                # Ignore other keys

        # Draw overlay
        screen.blit(overlay, (0, 0))

        # Draw confirmation text
        msg = "Do you really want to quit? (y/n)"
        lw = len(msg) * config.CHAR_WIDTH * config.SCALE_X
        x = (screen.get_width() - lw) // 2
        y = screen.get_height() // 2 - 10
        temp_draw_text(screen, msg, x, y, config.HIGHLIGHT_COLOR) # Use temp draw

        pygame.display.flip()
        clock.tick(10)

    return confirm


############################################################
# 7) ENTITY MAPPINGS (Characters - moved to config.py)
############################################################
# Constants like WALL_CHARS, PLAYER_CHARS etc. are now in config.py

def get_cell_string(cell):
    """Gets the character pair representation for a grid cell."""
    t = utils.cell_type(cell)
    if t == config.EMPTY:
        return config.EMPTY_CHARS
    elif t == config.PLAYER:
        return config.PLAYER_CHARS
    elif t == config.MOVEABLE_BLOCK:
        # Block appearance might depend on state (e.g., index)
        block_index = cell[1] if isinstance(cell, tuple) and len(cell) > 1 else 0
        if block_index == 0: return config.BLOCK0_CHARS
        elif block_index == 1: return config.BLOCK1_CHARS
        else: return config.BLOCK2_CHARS # Default or index 2
    elif t == config.UNMOVEABLE_BLOCK:
        return config.WALL_CHARS
    elif t == config.HUNTER:
        return config.HUNTER_CHARS
    elif t == config.EGG:
        return config.EGG_CHARS
    elif t == config.PUSHER:
        return config.PUSHER_CHARS
    elif t == config.SENTINEL:
        return config.SENTINEL_CHARS
    else:
        return "??" # Unknown cell type

############################################################
# 8) DRAWING THE GRID & STATUS (Should move to drawing.py)
############################################################
def draw_grid(screen, grid):
    """Draws the main game grid."""
    screen.fill((0, 0, 0)) # Clear screen
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            cell_content = grid[y][x]
            cell_str = get_cell_string(cell_content)
            color = utils.get_cell_color(cell_content) # Use util function for color
            px = x * (config.CHAR_WIDTH * config.SCALE_X * 2) # Double char width for cells
            py = y * (config.CHAR_HEIGHT * config.SCALE_Y)
            temp_draw_text(screen, cell_str, px, py, color) # Use temp draw

def draw_status_line(screen, grid, level_start_time, current_lives, level_name, current_score, time_offset):
    """Draws the status bar at the bottom."""
    status_y = config.GRID_HEIGHT * (config.CHAR_HEIGHT * config.SCALE_Y)
    status_area_rect = pygame.Rect(0, status_y, screen.get_width(), config.STATUS_HEIGHT)
    screen.fill(config.STATUS_BG_COLOR, status_area_rect) # Black background for status

    # Calculate elapsed time for the current level/sublevel
    elapsed_seconds = time_offset + (utils.get_game_time() - level_start_time) // 1000
    elapsed_seconds = max(0, elapsed_seconds) # Ensure non-negative time
    time_str = utils.format_time(elapsed_seconds)

    # Count enemies (consider optimizing if grid is large)
    current_enemy_count = sum(1 for row in grid for cell in row
                              if utils.cell_type(cell) in
                              [config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG])

    # Count initial eggs (this needs better state management, maybe pass as param or store in Level object)
    # Using a temporary placeholder attribute on the function itself is fragile.
    initial_egg_count = getattr(draw_status_line, "initial_egg_count", 0) # TODO: Refactor this

    # Build status segments
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
    segments.append((f"{current_lives}", config.HIGHLIGHT_COLOR)) # Use passed lives
    segments.append(("  Score: ", config.TEXT_COLOR_DEFAULT))
    segments.append((f"{current_score}", config.HIGHLIGHT_COLOR)) # Use passed score

    # Calculate total width and starting position for right-alignment
    total_seg_width = sum(len(text) * config.CHAR_WIDTH * config.SCALE_X for text, col in segments)
    x = screen.get_width() - total_seg_width - 5 # Right align with padding
    y = status_y + (config.STATUS_HEIGHT - config.CHAR_HEIGHT * config.SCALE_Y) // 2 # Center vertically

    # Draw segments
    for text, col in segments:
        temp_draw_text(screen, text, x, y, col) # Use temp draw
        x += len(text) * config.CHAR_WIDTH * config.SCALE_X

############################################################
# 9) PLAYER SPAWN LOGIC & ANIMATION (Should move to game_logic.py/ui.py)
############################################################
def get_player_position(grid):
    """Finds the player's (x, y) coordinates in the grid."""
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            if utils.cell_type(grid[y][x]) == config.PLAYER:
                return (x, y)
    return None # Player not found

def place_player_best_spot(grid, screen):
    """Finds the 'best' empty spot to spawn the player and places them there."""
    enemies = []
    blocks = [] # Includes walls, blocks, eggs
    empty_spots = []

    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            t = utils.cell_type(grid[y][x])
            if t in [config.HUNTER, config.PUSHER, config.SENTINEL]:
                enemies.append((x, y))
            elif t in (config.UNMOVEABLE_BLOCK, config.MOVEABLE_BLOCK, config.EGG):
                blocks.append((x, y))
            elif t == config.EMPTY and 0 < x < config.GRID_WIDTH - 1 and 0 < y < config.GRID_HEIGHT - 1:
                 # Only consider non-edge spots initially
                 empty_spots.append((x,y))


    best_pos = None
    max_score = -1

    if not empty_spots: # Fallback if no inner empty spots (e.g., very dense level)
        for y in range(config.GRID_HEIGHT):
            for x in range(config.GRID_WIDTH):
                 if utils.cell_type(grid[y][x]) == config.EMPTY:
                      empty_spots.append((x,y))
        if not empty_spots: return # No empty space anywhere!

    # Calculate score for each empty spot (distance from edges, enemies, blocks)
    for (px, py) in empty_spots:
        # Distance from closest edge (higher is better)
        edge_dist = min(px, config.GRID_WIDTH - 1 - px, py, config.GRID_HEIGHT - 1 - py)

        # Min distance to any enemy (higher is better)
        min_enemy_dist = min([abs(px - ex) + abs(py - ey) for ex, ey in enemies] or [999])

        # Min distance to any block/wall (higher is better, but less important than enemies)
        min_block_dist = min([abs(px - bx) + abs(py - by) for bx, by in blocks] or [999])

        # Combine scores (weights can be adjusted)
        # Prioritize enemy distance, then edge distance, then block distance
        score = min_enemy_dist * 100 + edge_dist * 10 + min_block_dist

        if score > max_score:
            max_score = score
            best_pos = (px, py)

    if best_pos:
        x, y = best_pos
        show_spawn_animation(grid, screen, x, y) # Play animation at the chosen spot
        grid[y][x] = config.PLAYER # Place player
    else:
        # This should ideally not happen if there are empty spots
        print("ERROR: Could not find a position to place the player.")
        # As a last resort, place at the first found empty spot
        if empty_spots:
             x, y = empty_spots[0]
             show_spawn_animation(grid, screen, x, y)
             grid[y][x] = config.PLAYER


def respawn_player(grid, screen):
    """Removes the current player and spawns a new one."""
    player_pos = get_player_position(grid)
    if player_pos:
        px, py = player_pos
        grid[py][px] = config.EMPTY # Remove old player first
    place_player_best_spot(grid, screen) # Find new spot and spawn

def show_spawn_animation(grid, screen, x, y):
    """Displays a short animation when the player spawns."""
    # Animation steps: (character pair, color)
    steps = [
        ("\xFA\xFA", (0xff, 0xff, 0xff)), # White flash
        ("--", (0xff, 0x00, 0x00)),       # Red dashes
        ("\x1B\x1A", (0xff, 0x99, 0x00)), # Orange arrows
        ("\xAE\xAF", (0xff, 0xff, 0x00)), # Yellow << >>
        ("<>", (0xff, 0xff, 0xff))        # White <>
    ]
    clock = pygame.time.Clock()
    px = x * (config.CHAR_WIDTH * config.SCALE_X * 2)
    py = y * (config.CHAR_HEIGHT * config.SCALE_Y)

    for glyphs, color in steps:
        # Redraw the grid state *before* drawing the animation frame
        draw_grid(screen, grid)
        # Draw the animation character at the target location
        temp_draw_text(screen, glyphs, px, py, color) # Use temp draw
        # Update the display
        pygame.display.flip()
        # Wait briefly
        clock.tick(8) # Faster animation

############################################################
# 10) GAME OVER & COLLISION (Should move to game_logic.py/ui.py)
############################################################
def game_over_screen(screen):
    """Displays the 'Game Over' message."""
    screen.fill((0, 0, 0)) # Black background
    msg = "Game Over"
    w = len(msg) * config.CHAR_WIDTH * config.SCALE_X
    h = config.CHAR_HEIGHT * config.SCALE_Y
    # Center message on screen
    x = (screen.get_width() - w) // 2
    y = (screen.get_height() - h) // 2
    temp_draw_text(screen, msg, x, y, config.HIGHLIGHT_COLOR) # Use temp draw
    pygame.display.flip()
    pygame.time.wait(3000) # Pause for 3 seconds

def handle_collision(grid, screen):
    """Handles the consequences of the player colliding with an enemy."""
    global lives, running_level_score, game_over_flag # Access global state (TODO: Refactor into Game class)
    global last_sublevel_name, last_sublevel_start_time, last_sublevel_time_offset # For high score context

    resources.get_sound('collision').play() # Play collision sound
    lives -= 1

    if lives <= 0:
        game_over_screen(screen)
        # Calculate time played in the final sublevel before game over
        partial_time = last_sublevel_time_offset + (utils.get_game_time() - last_sublevel_start_time) // 1000
        partial_time = max(0, partial_time)
        # Use the high score manager
        hs_manager.maybe_record_and_show(running_level_score, last_sublevel_name, screen, pygame.time.Clock(), partial_time)
        game_over_flag = True # Set flag to stop the current level loop
    else:
        respawn_player(grid, screen) # Respawn if lives remain

############################################################
# 11) PLAYER MOVEMENT (Should move to entities.py/game_logic.py)
############################################################
def move_player_direction(grid, direction, stats, screen, explosive_enabled=False):
    """Attempts to move the player in a given direction (dx, dy)."""
    player_pos = get_player_position(grid)
    if not player_pos:
        return grid # Should not happen if player is alive

    px, py = player_pos
    dx, dy = direction
    tx, ty = px + dx, py + dy # Target coordinates

    # Check boundaries
    if not (0 <= tx < config.GRID_WIDTH and 0 <= ty < config.GRID_HEIGHT):
        return grid # Cannot move off grid

    target_cell = grid[ty][tx]
    t_type = utils.cell_type(target_cell)

    if t_type == config.EMPTY:
        grid[py][px] = config.EMPTY # Clear old position
        grid[ty][tx] = config.PLAYER # Move to new position
        stats['moves'] += 1 # Count successful moves
    elif t_type == config.MOVEABLE_BLOCK:
        # Attempt to push the block
        push_successful = push_blocks_player(grid, (px, py), direction, stats, screen, explosive_enabled)
        if push_successful:
             stats['moves'] += 1 # Count move only if push was successful
    elif t_type == config.UNMOVEABLE_BLOCK:
        if explosive_enabled:
            # Player bumps into wall with explosives enabled -> collision
            handle_collision(grid, screen)
        # Else: Do nothing, player cannot move
    elif t_type in (config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG):
        # Player walks into an enemy or egg -> collision
        handle_collision(grid, screen)

    # Grid might have been modified by handle_collision or push_blocks
    return grid

def push_blocks_player(grid, start_pos, direction, stats, screen, explosive_enabled=False):
    """Handles the logic for the player pushing a chain of blocks."""
    x, y = start_pos
    dx, dy = direction

    chain = [] # List of (x, y) coordinates of blocks being pushed
    cx, cy = x + dx, y + dy # Start checking from the first block

    # Build the chain of moveable blocks
    while 0 <= cx < config.GRID_WIDTH and 0 <= cy < config.GRID_HEIGHT:
        cell_t = utils.cell_type(grid[cy][cx])
        if cell_t == config.MOVEABLE_BLOCK:
            chain.append((cx, cy))
            cx += dx # Move to the next cell in the push direction
            cy += dy
        else:
            break # Stop if we hit non-moveable block or edge

    # Now check what's immediately after the chain
    final_pos_x, final_pos_y = cx, cy
    can_push = False
    squished_enemy_type = None
    squished_enemy_value = 0

    if not (0 <= final_pos_x < config.GRID_WIDTH and 0 <= final_pos_y < config.GRID_HEIGHT):
        # Chain leads off the grid - cannot push
        can_push = False
    else:
        occupant_t = utils.cell_type(grid[final_pos_y][final_pos_x])

        if occupant_t == config.EMPTY:
            # Space after the chain is empty - can push
            can_push = True
        elif occupant_t == config.UNMOVEABLE_BLOCK:
            # Chain hits a wall
            if explosive_enabled and chain:
                # Explode the last block in the chain
                last_bx, last_by = chain[-1]
                grid[last_by][last_bx] = config.EMPTY # Remove exploded block
                # The rest of the chain moves forward into the space created
                chain.pop() # Remove the last block from the chain to be moved
                can_push = True # Allow the push action for the remaining chain
                resources.get_sound('squish').play() # Use squish sound for explosion? Or add specific sound
                # TODO: Add score for explosion?
            else:
                # Cannot push against wall without explosives
                can_push = False
        elif occupant_t in (config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG):
            # Chain hits an enemy or egg. Check if it can be squished.
            # Need to check the space *behind* the enemy/egg.
            behind_x, behind_y = final_pos_x + dx, final_pos_y + dy
            can_squish = False
            if 0 <= behind_x < config.GRID_WIDTH and 0 <= behind_y < config.GRID_HEIGHT:
                 behind_t = utils.cell_type(grid[behind_y][behind_x])
                 # Can squish if space behind is wall, block, or another enemy/egg
                 if behind_t in (config.UNMOVEABLE_BLOCK, config.MOVEABLE_BLOCK,
                                 config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG):
                     can_squish = True

            if can_squish:
                can_push = True # Allow the push
                squished_enemy_type = occupant_t # Record what was squished
                # Determine score value
                if occupant_t == config.HUNTER: squished_enemy_value = config.HUNTER_VALUE
                elif occupant_t == config.PUSHER: squished_enemy_value = config.PUSHER_VALUE
                elif occupant_t == config.SENTINEL: squished_enemy_value = config.SENTINEL_VALUE
                elif occupant_t == config.EGG: squished_enemy_value = config.EGG_VALUE
            else:
                # Cannot squish (e.g., empty space behind enemy)
                can_push = False
        else:
             # Should not happen unless grid contains unexpected types
             can_push = False


    # If the push is possible, move everything
    if can_push:
        # Move the blocks in the chain (from back to front)
        for bx, by in reversed(chain):
            # Copy block data (including type and index if applicable)
            grid[by + dy][bx + dx] = grid[by][bx]
            # Clear the original block position (will be filled by block behind or player)
            grid[by][bx] = config.EMPTY

        # Move the player into the first block's original position
        grid[y + dy][x + dx] = config.PLAYER
        grid[y][x] = config.EMPTY # Clear player's original position

        # Handle squishing score and stats
        if squished_enemy_type is not None:
            stats["score"] = stats.get("score", 0) + squished_enemy_value
            resources.get_sound('squish').play()
            if squished_enemy_type == config.HUNTER: stats['hunters_killed'] = stats.get('hunters_killed', 0) + 1
            elif squished_enemy_type == config.PUSHER: stats['pushers_killed'] = stats.get('pushers_killed', 0) + 1
            elif squished_enemy_type == config.SENTINEL: stats['sentinels_killed'] = stats.get('sentinels_killed', 0) + 1
            elif squished_enemy_type == config.EGG: stats['eggs_destroyed'] = stats.get('eggs_destroyed', 0) + 1
            # The enemy/egg at (final_pos_x, final_pos_y) is implicitly overwritten by the last block pushed

        return True # Push was successful

    else:
        # Push failed (hit wall without explosion, leads off grid, cannot squish)
        if explosive_enabled and not chain and utils.cell_type(grid[cy][cx]) == config.UNMOVEABLE_BLOCK:
             # Special case: Player directly pushes a wall with explosives enabled
             handle_collision(grid, screen) # Treat as collision
             return False # Push failed, but collision handled

        return False # Push failed

############################################################
# 12) UPDATE EGGS, ENEMIES, AND PATHFINDING (Should move to entities.py/game_logic.py)
############################################################
def update_eggs(grid):
    """Updates egg timers and hatches them into Pushers if time is up."""
    now = utils.get_game_time()
    hatched = False
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            cell = grid[y][x]
            if utils.cell_type(cell) == config.EGG:
                egg_total_time = cell[1]
                egg_start = cell[2]
                if now - egg_start >= egg_total_time:
                    # TODO: Handle hatching into different enemy types based on level def
                    grid[y][x] = config.PUSHER # Currently hardcoded to Pusher
                    hatched = True
    # if hatched: resources.get_sound('hatch').play() # Optional sound
    return grid # Return modified grid (or modify in place)

# --- Pathfinding (A*) ---
# This could be a utility class or functions within utils.py or a dedicated pathfinding.py

def _heuristic(a, b):
    """Manhattan distance heuristic for A*."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def a_star_path(grid, start, goal, allowed_target_types=(config.EMPTY, config.PLAYER), blocked_types=(config.UNMOVEABLE_BLOCK, config.MOVEABLE_BLOCK, config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG), diagonals=True):
    """
    Finds a path from start to goal using A*.
    Args:
        grid: The game grid.
        start: Tuple (x, y) start position.
        goal: Tuple (x, y) goal position.
        allowed_target_types: Cell types the path can end on.
        blocked_types: Cell types the path cannot traverse.
        diagonals: Boolean indicating if diagonal movement is allowed.
    Returns:
        A list of (x, y) tuples representing the path, or None if no path found.
    """
    if start == goal: return [start] # Path is just the start point

    if diagonals:
        directions = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
        move_cost = lambda dx, dy: 1.414 if dx != 0 and dy != 0 else 1 # Diagonal cost
    else:
        directions = [(0,1),(0,-1),(1,0),(-1,0)]
        move_cost = lambda dx, dy: 1 # Orthogonal cost

    open_set = [] # Priority queue (min-heap) storing (f_score, g_score, pos)
    heappush(open_set, (_heuristic(start, goal), 0, start)) # Add start node

    came_from = {} # Stores the node preceding key node on the cheapest path
    g_score = {start: 0} # Cost from start along best known path

    while open_set:
        f_val, current_g, current_pos = heappop(open_set)

        # Check if we reached the goal
        if current_pos == goal:
            # Reconstruct path
            path = [current_pos]
            while current_pos in came_from:
                current_pos = came_from[current_pos]
                path.append(current_pos)
            path.reverse()
            return path

        cx, cy = current_pos

        # Explore neighbors
        for (dx, dy) in directions:
            nx, ny = cx + dx, cy + dy

            # Check grid boundaries
            if not (0 <= nx < config.GRID_WIDTH and 0 <= ny < config.GRID_HEIGHT):
                continue

            neighbor_pos = (nx, ny)
            neighbor_cell_type = utils.cell_type(grid[ny][nx])

            # Check if neighbor is blocked (unless it's the goal itself and allowed)
            is_blocked = neighbor_cell_type in blocked_types
            is_allowed_goal = neighbor_pos == goal and neighbor_cell_type in allowed_target_types

            if is_blocked and not is_allowed_goal:
                continue

            # Calculate tentative g_score
            cost = move_cost(dx, dy)
            tentative_g = current_g + cost

            # Check if this path to neighbor is better than any previous one
            if neighbor_pos not in g_score or tentative_g < g_score[neighbor_pos]:
                g_score[neighbor_pos] = tentative_g
                f_score = tentative_g + _heuristic(neighbor_pos, goal)
                came_from[neighbor_pos] = current_pos
                # Add to open set (or update priority if already there - heapq handles duplicates okay)
                heappush(open_set, (f_score, tentative_g, neighbor_pos))

    return None # No path found

# --- Enemy Update Logic ---

def update_hunters(grid, hunter_accuracy, screen):
    """Updates hunter positions based on A* pathfinding or random movement."""
    player_pos = get_player_position(grid)
    if not player_pos: return # No player to hunt

    # Find all hunters - important to get positions *before* moving any
    hunters_positions = []
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            if utils.cell_type(grid[y][x]) == config.HUNTER:
                hunters_positions.append((x, y))

    collision_occurred = False # Flag to stop processing if player dies mid-update

    for (hx, hy) in hunters_positions:
        if collision_occurred: break # Stop if player was hit

        # Re-check if the hunter is still at this position (might have been squished)
        if utils.cell_type(grid[hy][hx]) != config.HUNTER:
            continue

        moved = False
        # Try A* pathfinding based on accuracy
        if random.random() < (hunter_accuracy / 100.0):
            path = a_star_path(grid, (hx, hy), player_pos, diagonals=True,
                               allowed_target_types=(config.PLAYER, config.EMPTY),
                               blocked_types=(config.UNMOVEABLE_BLOCK, config.MOVEABLE_BLOCK, config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG)) # Hunters can move diagonally and step on player/empty

            if path and len(path) > 1:
                nx, ny = path[1] # Next step in the path
                target_cell_type = utils.cell_type(grid[ny][nx])

                if target_cell_type == config.PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue # Move to next hunter (or stop if collision occurred)
                elif target_cell_type == config.EMPTY:
                    grid[ny][nx] = config.HUNTER # Move hunter
                    grid[hy][hx] = config.EMPTY # Clear old spot
                    moved = True
                # Else: Path blocked by something unexpected, hunter waits or tries random

        # If A* didn't move the hunter, try a random move
        if not moved:
            possible_moves = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)] # Diagonal moves allowed
            random.shuffle(possible_moves)

            for dx, dy in possible_moves:
                nx, ny = hx + dx, hy + dy
                if 0 <= nx < config.GRID_WIDTH and 0 <= ny < config.GRID_HEIGHT:
                    target_cell_type = utils.cell_type(grid[ny][nx])
                    if target_cell_type == config.PLAYER:
                        handle_collision(grid, screen)
                        collision_occurred = True
                        break # Stop trying moves for this hunter
                    elif target_cell_type == config.EMPTY:
                        grid[ny][nx] = config.HUNTER
                        grid[hy][hx] = config.EMPTY
                        moved = True
                        break # Moved successfully

        # If collision occurred in the random move check, break outer loop too
        if collision_occurred: break


def update_sentinels(grid, sentinel_accuracy, screen):
    """Updates sentinel positions (similar to hunters but maybe different rules)."""
    player_pos = get_player_position(grid)
    if not player_pos: return

    sentinel_positions = []
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            if utils.cell_type(grid[y][x]) == config.SENTINEL:
                sentinel_positions.append((x, y))

    collision_occurred = False

    for (sx, sy) in sentinel_positions:
        if collision_occurred: break
        if utils.cell_type(grid[sy][sx]) != config.SENTINEL: continue

        moved = False
        if random.random() < (sentinel_accuracy / 100.0):
            # Sentinels might use different pathing rules (e.g., no diagonals?)
            path = a_star_path(grid, (sx, sy), player_pos, diagonals=True, # Assuming they can move diagonally too
                               allowed_target_types=(config.PLAYER, config.EMPTY),
                               blocked_types=(config.UNMOVEABLE_BLOCK, config.MOVEABLE_BLOCK, config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG))

            if path and len(path) > 1:
                nx, ny = path[1]
                target_cell_type = utils.cell_type(grid[ny][nx])
                if target_cell_type == config.PLAYER:
                    handle_collision(grid, screen)
                    collision_occurred = True
                    continue
                elif target_cell_type == config.EMPTY:
                    grid[ny][nx] = config.SENTINEL
                    grid[sy][sx] = config.EMPTY
                    moved = True

        if not moved:
            # Random move (can also be diagonal)
            possible_moves = [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
            random.shuffle(possible_moves)
            for dx, dy in possible_moves:
                nx, ny = sx + dx, sy + dy
                if 0 <= nx < config.GRID_WIDTH and 0 <= ny < config.GRID_HEIGHT:
                    target_cell_type = utils.cell_type(grid[ny][nx])
                    if target_cell_type == config.PLAYER:
                        handle_collision(grid, screen)
                        collision_occurred = True
                        break
                    elif target_cell_type == config.EMPTY:
                        grid[ny][nx] = config.SENTINEL
                        grid[sy][sx] = config.EMPTY
                        moved = True
                        break
        if collision_occurred: break


def pusher_push_blocks(grid, start_pos, dx, dy, screen):
    """Handles the logic for a Pusher attempting to push blocks or the player."""
    x, y = start_pos
    nx, ny = x + dx, y + dy # Target cell

    if not (0 <= nx < config.GRID_WIDTH and 0 <= ny < config.GRID_HEIGHT):
        return False # Cannot push off grid

    occupant_t = utils.cell_type(grid[ny][nx])

    if occupant_t == config.PLAYER:
        # Pusher hits player -> collision
        handle_collision(grid, screen)
        # Return True because the pusher *attempted* its action, even if it resulted in collision
        # The collision handler might set game_over_flag, stopping further updates.
        return True # Action occurred (collision)
    elif occupant_t == config.EMPTY:
        # Pusher moves into empty space
        grid[ny][nx] = config.PUSHER
        grid[y][x] = config.EMPTY
        return True # Move successful
    elif occupant_t == config.MOVEABLE_BLOCK:
        # Pusher attempts to push a block chain
        chain = []
        cx, cy = nx, ny
        while 0 <= cx < config.GRID_WIDTH and 0 <= cy < config.GRID_HEIGHT:
            cell_t = utils.cell_type(grid[cy][cx])
            if cell_t == config.MOVEABLE_BLOCK:
                chain.append((cx, cy))
                cx += dx
                cy += dy
            else:
                break # End of chain

        # Check what's after the chain
        final_x, final_y = cx, cy
        if not (0 <= final_x < config.GRID_WIDTH and 0 <= final_y < config.GRID_HEIGHT):
            return False # Chain leads off grid

        final_t = utils.cell_type(grid[final_y][final_x])
        if final_t == config.EMPTY:
            # Can push the chain
            # Move blocks from back to front
            for (bx, by) in reversed(chain):
                grid[by + dy][bx + dx] = grid[by][bx] # Copy block data
                grid[by][bx] = config.EMPTY
            # Move pusher into the first block's spot
            grid[ny][nx] = config.PUSHER
            grid[y][x] = config.EMPTY
            return True # Push successful
        else:
            # Cannot push (hits wall, enemy, player, etc.)
            return False
    else:
        # Pusher hits wall, other enemy, egg -> cannot move/push
        return False

def update_pushers(grid, pusher_accuracy, screen):
    """Updates pusher positions and handles their block-pushing behavior."""
    player_pos = get_player_position(grid)
    if not player_pos: return

    px_player, py_player = player_pos

    pusher_positions = []
    for y in range(config.GRID_HEIGHT):
        for x in range(config.GRID_WIDTH):
            if utils.cell_type(grid[y][x]) == config.PUSHER:
                pusher_positions.append((x, y))

    collision_occurred = False # Use local flag, check game_over_flag from global scope if needed

    for (px, py) in pusher_positions:
        if collision_occurred or game_over_flag: break # Stop if player died
        if utils.cell_type(grid[py][px]) != config.PUSHER: continue # Check if still a pusher

        moved = False
        # Decide whether to move towards player or randomly based on accuracy
        move_towards_player = random.random() < (pusher_accuracy / 100.0)

        if move_towards_player:
            # --- Try direct push towards player ---
            dx, dy = 0, 0
            # Prefer moving along the axis with greater distance
            if abs(px_player - px) > abs(py_player - py):
                dx = 1 if px_player > px else -1
            elif abs(py_player - py) > abs(px_player - py): # Check non-zero vertical distance
                dy = 1 if py_player > py else -1
            elif px_player != px: # Equal distance, move horizontally if possible
                 dx = 1 if px_player > px else -1
            elif py_player != py: # Equal distance, move vertically if possible
                 dy = 1 if py_player > py else -1


            if (dx, dy) != (0, 0):
                if pusher_push_blocks(grid, (px, py), dx, dy, screen):
                    moved = True
                    # Check if collision occurred during push
                    if get_player_position(grid) is None: collision_occurred = True

            # --- If direct push failed or wasn't possible, try A* path ---
            if not moved and not collision_occurred:
                 # Pushers use orthogonal pathfinding only
                 path = a_star_path(grid, (px, py), player_pos, diagonals=False,
                                    allowed_target_types=(config.PLAYER, config.EMPTY, config.MOVEABLE_BLOCK), # Can target blocks to push
                                    blocked_types=(config.UNMOVEABLE_BLOCK, config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG)) # Cannot move through walls/enemies

                 if path and len(path) > 1:
                     # Get direction from path
                     next_x, next_y = path[1]
                     path_dx, path_dy = next_x - px, next_y - py
                     if pusher_push_blocks(grid, (px, py), path_dx, path_dy, screen):
                         moved = True
                         if get_player_position(grid) is None: collision_occurred = True


        # --- If not moving towards player or pathing failed, move randomly ---
        if not moved and not collision_occurred:
            possible_moves = [(0,1),(0,-1),(1,0),(-1,0)] # Orthogonal only
            random.shuffle(possible_moves)
            for (rnd_dx, rnd_dy) in possible_moves:
                if pusher_push_blocks(grid, (px, py), rnd_dx, rnd_dy, screen):
                    moved = True
                    if get_player_position(grid) is None: collision_occurred = True
                    break # Stop after first successful random move

        # If collision occurred, stop processing pushers for this frame
        if get_player_position(grid) is None: collision_occurred = True


############################################################
# 15) LEVELS LOADING / DEFINITION (Moved to resources.py)
############################################################
# load_levels_json is now in resources.py
# get_main_level_def is now in resources.py

############################################################
# LEVEL SELECTION & DETAILS SCREENS (Should move to ui.py)
############################################################
def level_selection_screen(screen, clock):
    """Displays the level selection menu."""
    # global current_spritesheet # No longer global, managed in resources
    level_letters = resources.get_level_letters()
    if not level_letters:
        # Handle case where no levels are loaded
        # Show an error message and maybe exit or default to 'A'
        temp_draw_text(screen, "ERROR: No levels found!", 50, 100, config.HIGHLIGHT_COLOR)
        temp_draw_text(screen, "Check levels.json", 50, 140, config.TEXT_COLOR_DEFAULT)
        pygame.display.flip()
        utils.wait_for_key()
        pygame.quit()
        sys.exit()
        # Or default: level_letters = ["A"]

    selected_index = 0

    while True:
        screen.fill((0, 0, 0)) # Clear screen

        # Draw Title (ASCII Art) - Consider making this configurable
        title_y = 2 * config.CELL_SIZE
        title_color = config.PLAYER_COLOR # Example color
        title_lines = [
            ("\xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDB\xDB   \xDB\xDB \xDE\xDB\xDB\xDD \xDC\xDB\xDB\xDB\xDB\xDB\xDC \xDB\xDB   \xDB\xDB", config.PLAYER_COLOR),
            ("\xDB\xDB\xDC\xDC\xDC\xDC  \xDB\xDB   \xDB\xDB \xDB\xDB   \xDB\xDB  \xDB\xDB  \xDB\xDB\xDC\xDC\xDC\xDC  \xDB\xDB\xDC\xDC\xDC\xDB\xDB", config.HIGHLIGHT_COLOR),
            (" \xDF\xDF\xDF\xDF\xDB\xDB \xDB\xDB \xDF\xDC\xDB\xDB \xDB\xDB   \xDB\xDB  \xDB\xDB   \xDF\xDF\xDF\xDF\xDB\xDB \xDB\xDB\xDF\xDF\xDF\xDB\xDB", config.EGG_COLOR_0),
            ("\xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDF\xDB\xDB\xDB\xDB\xDF\xDC \xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDE\xDB\xDB\xDD \xDF\xDB\xDB\xDB\xDB\xDB\xDF \xDB\xDB   \xDB\xDB", config.EGG_COLOR_1),
        ]
        title_start_x = (screen.get_width() - len(title_lines[0][0]) * config.CHAR_WIDTH * config.SCALE_X) // 2
        current_y = title_y
        for line, color in title_lines:
             temp_draw_text(screen, line, title_start_x, current_y, color)
             current_y += config.CHAR_HEIGHT * config.SCALE_Y + 4 # Spacing

        # Draw Level Selection
        level_display_y = current_y + 40 # Space below title
        level_display_x = 128 # Starting x for level letters
        spacing = 40
        for idx, lvl in enumerate(level_letters):
            color = config.HIGHLIGHT_COLOR if idx == selected_index else config.TEXT_COLOR_DEFAULT
            temp_draw_text(screen, lvl, level_display_x + idx * spacing, level_display_y, color)
            # Draw indicator below selected level
            if idx == selected_index:
                 indicator_x = level_display_x + idx * spacing + (config.CHAR_WIDTH * config.SCALE_X // 2) - 4 # Center indicator
                 indicator_y = level_display_y + config.CHAR_HEIGHT * config.SCALE_Y + 4
                 temp_draw_text(screen, "^", indicator_x, indicator_y, config.HIGHLIGHT_COLOR)


        # Draw Instructions
        prompt = "Arrows: select | ENTER: start | H: high scores | A: art style | ESC: quit"
        prompt_y = screen.get_height() - config.STATUS_HEIGHT # Position above status bar area
        prompt_x = (screen.get_width() - len(prompt) * config.CHAR_WIDTH * config.SCALE_X) // 2 # Center prompt
        temp_draw_text(screen, prompt, prompt_x, prompt_y, config.TEXT_COLOR_DEFAULT)

        pygame.display.flip()

        # Event Handling
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == K_h:
                    hs_manager.show_screen(screen, clock) # Use HighScoreManager instance
                    # Need to redraw the level select screen after returning
                    # The loop structure handles this automatically
                elif event.key == K_LEFT:
                    selected_index = (selected_index - 1) % len(level_letters)
                elif event.key == K_RIGHT:
                    selected_index = (selected_index + 1) % len(level_letters)
                elif event.key == K_RETURN:
                    return level_letters[selected_index] # Return selected level letter
                elif event.key == K_a:
                    resources.toggle_spritesheet() # Toggle via resources module
                    # Force redraw with new spritesheet (handled by loop)
                    global _temp_sprite_sheet_cache # Need to invalidate temp cache
                    _temp_sprite_sheet_cache = None


        clock.tick(15) # Limit frame rate

def show_level_details_screen(screen, clock, level_def):
    """Displays details about the selected level before starting."""
    lvl = level_def.get("level", "?")
    winning_level = level_def.get("winning_level", 1)
    # pull_blocks = level_def.get("pull_blocks", False) # Feature not implemented?
    # speed_up = level_def.get("speed_up", False)     # Feature not implemented?
    explosive_blocks = level_def.get("explosive_blocks", False)
    enemies = level_def.get("enemies", {})
    egg_incubation_ms = level_def.get("egg_incubation_ms", 0)

    enemy_lines = []
    # Define enemy types and their display names/order
    enemy_order = ["hunter", "pusher", "sentinel", "egg"]
    enemy_display_names = {"hunter": "Hunters", "pusher": "Pushers", "sentinel": "Sentinels", "egg": "Eggs"}

    for enemy_key in enemy_order:
        if enemy_key in enemies:
            data = enemies[enemy_key]
            count = data.get("count", 0)
            if count == 0: continue # Skip if count is zero

            display_name = enemy_display_names.get(enemy_key, enemy_key.capitalize() + "s")
            line = f"- {count} {display_name}"

            # Add specific details
            if enemy_key == "hunter":
                mutation_ratio = data.get("mutation_ratio", 0)
                mutates_into = data.get("mutates_into", "").capitalize()
                accuracy = data.get("accuracy", "?")
                speed_ms = data.get("speed_ms", "?")
                details = []
                if mutation_ratio > 0 and mutates_into:
                    mut_count = int(round(count * mutation_ratio))
                    details.append(f"{mut_count} mutate to {mutates_into}")
                details.append(f"{accuracy}% accuracy")
                details.append(f"{speed_ms}ms speed")
                if details: line += f" ({', '.join(details)})"

            elif enemy_key == "egg":
                hatches_into = data.get("hatches_into", "Pusher").capitalize() # Default hatch type
                incubation_sec = egg_incubation_ms / 1000.0 if egg_incubation_ms > 0 else 0
                details = []
                details.append(f"hatch into {hatches_into}")
                if incubation_sec > 0: details.append(f"{incubation_sec:.1f}s incubation")
                if details: line += f" ({', '.join(details)})"

            elif enemy_key in ["pusher", "sentinel"]:
                 accuracy = data.get("accuracy", "?")
                 speed_ms = data.get("speed_ms", "?")
                 details = [f"{accuracy}% accuracy", f"{speed_ms}ms speed"]
                 line += f" ({', '.join(details)})"


            enemy_lines.append(line)

    # Assemble all detail lines
    details = [
        f"Level {lvl}",
        "",
        f"Goal: Complete {winning_level} sublevel(s)",
        # f"Pull blocks:        {'Yes' if pull_blocks else 'No'}", # Hide if not implemented
        # f"Game speed up:      {'Yes' if speed_up else 'No'}",   # Hide if not implemented
        f"Explosive blocks: {'Yes' if explosive_blocks else 'No'}",
        "",
    ]
    if enemy_lines:
        details.append("Enemies:")
        details.extend(enemy_lines)
    else:
        details.append("No enemies in this level.")

    details.extend([
        "",
        "Press SPACE to start, or ESC to go back"
    ])

    # Display loop
    line_height = config.CHAR_HEIGHT * config.SCALE_Y + 10
    start_y = 50
    start_x = 50

    while True:
        screen.fill((0, 0, 0))
        y = start_y
        for line in details:
            temp_draw_text(screen, line, start_x, y, config.TEXT_COLOR_DEFAULT) # Use temp draw
            y += line_height

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE or event.key == K_RETURN:
                    return True # Proceed to play level
                elif event.key == K_ESCAPE:
                    return False # Go back to level selection

        clock.tick(15)

############################################################
# PLAY A MAIN LEVEL (with sublevels) (Should move to game_logic.py)
############################################################
def play_main_level(level_def, screen, clock):
    """Plays all sublevels for a given main level definition."""
    global lives, game_over_flag, running_level_score, cumulative_time # Manage global state (TODO: Refactor)
    global last_sublevel_name, last_sublevel_start_time, last_sublevel_time_offset # For high score context

    # Reset state for the main level
    running_level_score = 0 # Score accumulates across sublevels
    # lives are usually reset in main() before calling this
    game_over_flag = False # Reset game over flag
    # cumulative_time is managed outside this function for now

    total_moves_main_level = 0
    total_enemies_main_level = 0
    total_time_main_level = 0
    total_sublevels = level_def.get("winning_level", 1)

    for sublevel_index in range(1, total_sublevels + 1):
        # Bonus score for starting subsequent sublevels (if enemies exist)
        # This logic seems odd - applying bonus *before* playing? Maybe apply *after* completing previous?
        # Let's apply it *after* completing sublevel N-1, before starting N.
        if sublevel_index > 1:
             # Award bonus based on *potential* enemies from the definition
             bonus = 0
             if level_def.get("enemies", {}).get("hunter", {}).get("count", 0) > 0:
                 bonus += 2 * config.HUNTER_VALUE # Example bonus
             if level_def.get("enemies", {}).get("egg", {}).get("count", 0) > 0:
                 bonus += 1 * config.EGG_VALUE # Example bonus
             # Add more bonus types if needed
             running_level_score += bonus
             # print(f"Sublevel {sublevel_index} start bonus: +{bonus}") # Debug

        # Calculate time offset for this sublevel
        # This should be the total time spent *before* this sublevel started
        sub_time_offset = cumulative_time + total_time_main_level

        # Play the sublevel
        result = play_sublevel(level_def, sublevel_index, screen, clock, running_level_score, sub_time_offset)

        if result is None:
            # Player quit or game over during the sublevel
            # High score handling is done within handle_collision or if quit confirmed
            # Reset lives for the next game attempt in main()
            # lives = 3 # Resetting here might be wrong if main loop handles it
            game_over_flag = False # Reset flag for next game attempt
            return None # Indicate main level was not completed

        # Unpack results from completed sublevel
        moves, enemies_eliminated, time_taken, final_sublevel_score, level_name = result
        running_level_score = final_sublevel_score # Update score for next sublevel/final result
        total_moves_main_level += moves
        total_enemies_main_level += enemies_eliminated
        total_time_main_level += time_taken

        # Play sound only if not the very last sublevel
        if sublevel_index < total_sublevels:
            resources.get_sound('sublevel_complete').play()
            # Maybe add a small delay or visual cue between sublevels?
            pygame.time.wait(500)


    # Main level completed successfully
    resources.get_sound('level_complete').play()
    show_level_complete_screen(screen, level_def.get("level", "?"), total_moves_main_level, total_enemies_main_level, total_time_main_level, running_level_score)

    # Return results for the completed main level
    # Note: cumulative_time should be updated *outside* this function after it returns.
    return total_moves_main_level, total_enemies_main_level, total_time_main_level, running_level_score, level_def.get("level", "?")


def play_sublevel(level_def, sublevel_index, screen, clock, initial_sublevel_score, time_offset):
    """Plays a single sublevel."""
    global current_level, running_level_score # TODO: Refactor globals
    global last_sublevel_name, last_sublevel_start_time, last_sublevel_time_offset # For high score context

    # --- Setup Sublevel ---
    current_level = sublevel_index # Update global sublevel tracker (if needed elsewhere)
    level_name = f"{level_def.get('level', '?')}{sublevel_index}"

    # Store context for potential game over high score
    last_sublevel_name = level_name
    last_sublevel_start_time = utils.get_game_time() # Record start time using game time
    last_sublevel_time_offset = time_offset

    # Get enemy parameters from level definition
    enemies_def = level_def.get("enemies", {})
    h_def = enemies_def.get("hunter", {})
    p_def = enemies_def.get("pusher", {})
    s_def = enemies_def.get("sentinel", {})

    h_speed = h_def.get("speed_ms", 1000)
    h_acc   = h_def.get("accuracy", 50)
    p_speed = p_def.get("speed_ms", 1000)
    p_acc   = p_def.get("accuracy", 50)
    s_speed = s_def.get("speed_ms", 1000)
    s_acc   = s_def.get("accuracy", 50)

    # Initialize sublevel state
    running_score = initial_sublevel_score # Start with score carried over
    grid = generate_level(level_def, sublevel_index) # Generate the grid layout
    place_player_best_spot(grid, screen) # Place the player

    # Check if player spawn failed (no empty space)
    if get_player_position(grid) is None:
         print(f"ERROR: Failed to place player in sublevel {level_name}. Aborting.")
         # Handle this error - maybe return None or raise exception
         return None # Indicate failure

    # Store initial egg count for status bar (needs refactoring)
    draw_status_line.initial_egg_count = sum(1 for row in grid for c in row if utils.cell_type(c) == config.EGG)

    # Stats for this specific sublevel
    stats = {
        'moves': 0,
        'eggs_destroyed': 0,
        'hunters_killed': 0,
        'pushers_killed': 0,
        'sentinels_killed': 0,
        'score': running_score # Track score changes within this sublevel
    }

    explosive_enabled = level_def.get("explosive_blocks", False)

    # Timers for enemy updates
    level_start_time_for_updates = utils.get_game_time() # Use game time for update logic
    last_hunter_update = level_start_time_for_updates
    last_pusher_update = level_start_time_for_updates
    last_sentinel_update = level_start_time_for_updates

    # --- Sublevel Game Loop ---
    sublevel_running = True
    while sublevel_running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    # Pause the game
                    pause_result = pause_game(screen)
                    if pause_result == -1: # User chose Quit from pause menu
                        return None # Signal quit up the call stack
                    # Adjust update timers by pause duration? No, get_game_time handles it.
                    # last_hunter_update += pause_result ... No, not needed.
                elif event.key in (K_q, ord('q')):
                    # Direct quit confirmation
                    if quit_confirm(screen):
                        return None # Signal quit
                elif event.key in (K_UP, K_DOWN, K_LEFT, K_RIGHT):
                    # Player movement attempt
                    direction = {K_UP: (0, -1), K_DOWN: (0, 1), K_LEFT: (-1, 0), K_RIGHT: (1, 0)}[event.key]
                    # Pass the *current* grid and stats
                    grid = move_player_direction(grid, direction, stats, screen, explosive_enabled)
                    # Update running score after potential changes in move_player/push_blocks/handle_collision
                    running_score = stats["score"]
                    # Check game over flag after move attempt
                    if game_over_flag:
                        sublevel_running = False
                        break # Exit event loop for this frame

        # Exit main loop if game over flag was set
        if not sublevel_running: break

        # --- Game Logic Updates ---
        current_time = utils.get_game_time()

        # Update Hunters
        if current_time - last_hunter_update >= h_speed:
            update_hunters(grid, h_acc, screen)
            last_hunter_update = current_time # Reset timer
            if game_over_flag: sublevel_running = False; break # Check after update

        # Update Pushers
        if current_time - last_pusher_update >= p_speed:
            update_pushers(grid, p_acc, screen)
            last_pusher_update = current_time
            if game_over_flag: sublevel_running = False; break

        # Update Sentinels
        if current_time - last_sentinel_update >= s_speed:
            update_sentinels(grid, s_acc, screen)
            last_sentinel_update = current_time
            if game_over_flag: sublevel_running = False; break

        # Update Eggs
        update_eggs(grid) # Check for hatching

        # --- Check Win Condition ---
        # Sublevel ends when all enemies (Hunters, Pushers, Sentinels, Eggs) are gone
        any_enemies = any(utils.cell_type(c) in [config.HUNTER, config.PUSHER, config.SENTINEL, config.EGG]
                          for row in grid for c in row)
        if not any_enemies:
            sublevel_running = False # End the loop successfully

        # --- Drawing ---
        draw_grid(screen, grid)
        # Pass current lives and score to status line
        draw_status_line(screen, grid, last_sublevel_start_time, lives, level_name, stats["score"], time_offset)
        pygame.display.flip()

        # --- Frame Limiting ---
        clock.tick(15) # Adjust tick rate as needed (was 10)

    # --- Sublevel End ---
    if game_over_flag:
        # Game ended due to collision
        return None # Signal failure/game over

    # Sublevel completed successfully
    level_end_time = utils.get_game_time()
    time_taken_ms = level_end_time - last_sublevel_start_time
    time_taken_seconds = max(0, time_taken_ms // 1000) # Ensure non-negative

    # Calculate completion bonus (example logic)
    total_sublevels_in_main = level_def.get("winning_level", 1)
    # Bonus based on main level difficulty and current sublevel index
    base_bonus = 5
    difficulty_bonus = math.floor(total_sublevels_in_main / 3) * 4 # More bonus for longer levels
    progression_bonus = (sublevel_index - 1) * 4 # More bonus for later sublevels
    completion_bonus = base_bonus + difficulty_bonus + progression_bonus
    stats["score"] += completion_bonus
    # print(f"Sublevel {level_name} completion bonus: +{completion_bonus}") # Debug

    # Return stats for this completed sublevel
    enemies_killed_this_sublevel = (stats['hunters_killed'] + stats['pushers_killed'] + stats['sentinels_killed'] + stats['eggs_destroyed'])
    return stats['moves'], enemies_killed_this_sublevel, time_taken_seconds, stats["score"], level_name


def show_level_complete_screen(screen, level_letter, moves, enemies_eliminated, time_taken, level_score):
    """Displays summary after completing all sublevels of a main level."""
    screen.fill((0, 0, 0)) # Clear screen
    lines = [
        f"Level {level_letter} Completed!",
        "",
        f"Total Enemies Eliminated: {enemies_eliminated}",
        f"Total Moves Taken: {moves}",
        f"Total Time: {utils.format_time(time_taken)}", # Format time
        f"Final Score: {level_score}",
        "",
        "Press SPACE to return to level selection"
    ]

    line_height = config.CHAR_HEIGHT * config.SCALE_Y + 10
    total_text_height = len(lines) * line_height
    start_y = (screen.get_height() - total_text_height) // 2 # Center vertically
    start_x = 50 # Left margin

    current_y = start_y
    for line in lines:
        # Center each line individually
        line_width = len(line) * config.CHAR_WIDTH * config.SCALE_X
        current_x = (screen.get_width() - line_width) // 2
        temp_draw_text(screen, line, current_x, current_y, config.TEXT_COLOR_DEFAULT) # Use temp draw
        current_y += line_height

    pygame.display.flip()

    # Wait for player input
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE or event.key == K_RETURN:
                    waiting = False
                elif event.key == K_ESCAPE: # Allow escape to quit from here too?
                     pygame.quit(); sys.exit() # Or return to menu?
        pygame.time.Clock().tick(15)


############################################################
# 16) GENERATE LEVEL (Should move to level.py/game_logic.py)
############################################################
def generate_level(level_def, sublevel_index):
    """Generates the grid layout for a specific sublevel."""
    enemies = level_def.get("enemies", {})
    hunter_def = enemies.get("hunter", {})
    egg_def = enemies.get("egg", {})
    pusher_def = enemies.get("pusher", {})
    sentinel_def = enemies.get("sentinel", {})

    # Calculate enemy counts based on base count and sublevel progression
    base_h_count = hunter_def.get("count", 0)
    h_count = base_h_count + 2 * (sublevel_index - 1) if base_h_count > 0 else 0
    h_count = max(0, h_count) # Ensure non-negative

    base_e_count = egg_def.get("count", 0)
    e_count = base_e_count + (sublevel_index - 1) if base_e_count > 0 else 0
    e_count = max(0, e_count)

    # Pusher and Sentinel counts might not increase per sublevel (based on original logic)
    p_count = max(0, pusher_def.get("count", 0))
    s_count = max(0, sentinel_def.get("count", 0))

    # Handle Hunter mutation
    mutation_ratio = hunter_def.get("mutation_ratio", 0)
    mutates_into = hunter_def.get("mutates_into", "").lower() # e.g., "sentinel"

    mutated_count = 0
    if mutation_ratio > 0 and h_count > 0:
        mutated_count = int(round(h_count * mutation_ratio))
        h_count -= mutated_count # Reduce hunter count

        # Increase count of the target mutation type
        if mutates_into == "pusher": p_count += mutated_count
        elif mutates_into == "sentinel": s_count += mutated_count
        # Add other mutation targets if needed
        else: h_count += mutated_count # Revert if target is unknown

    # --- Initialize Grid ---
    grid = [[config.EMPTY for _ in range(config.GRID_WIDTH)] for _ in range(config.GRID_HEIGHT)]

    # Add outer walls
    for x in range(config.GRID_WIDTH):
        grid[0][x] = config.UNMOVEABLE_BLOCK
        grid[config.GRID_HEIGHT-1][x] = config.UNMOVEABLE_BLOCK
    for y in range(1, config.GRID_HEIGHT-1):
        grid[y][0] = config.UNMOVEABLE_BLOCK
        grid[y][config.GRID_WIDTH-1] = config.UNMOVEABLE_BLOCK

    # --- Place Inner Blocks ---
    # Calculate number of potential inner cells
    inner_width = config.GRID_WIDTH - 2
    inner_height = config.GRID_HEIGHT - 2
    total_inner_cells = inner_width * inner_height

    # Define density parameters (adjust as needed)
    wall_density = 0.01 # Percentage of inner cells that become walls
    block_density = 0.30 # Percentage of inner cells that become moveable blocks

    num_walls = int(total_inner_cells * wall_density)
    num_blocks = int(total_inner_cells * block_density)

    # Get all possible inner coordinates
    inner_coords = [(x, y) for y in range(1, config.GRID_HEIGHT-1) for x in range(1, config.GRID_WIDTH-1)]
    random.shuffle(inner_coords) # Shuffle for random placement

    # Place unmoveable blocks (walls)
    placed_count = 0
    coord_index = 0
    while placed_count < num_walls and coord_index < len(inner_coords):
        x, y = inner_coords[coord_index]
        grid[y][x] = config.UNMOVEABLE_BLOCK
        placed_count += 1
        coord_index += 1

    # Place moveable blocks
    placed_count = 0
    # Continue from where wall placement left off in shuffled coords
    while placed_count < num_blocks and coord_index < len(inner_coords):
        x, y = inner_coords[coord_index]
        # Ensure we don't overwrite a wall placed previously
        if grid[y][x] == config.EMPTY:
            block_index = random.choice([0, 1, 2]) # Randomize block appearance
            grid[y][x] = (config.MOVEABLE_BLOCK, block_index)
            placed_count += 1
        coord_index += 1


    # --- Place Enemies and Eggs ---
    # Get remaining empty coordinates after placing blocks/walls
    empty_coords = [(x, y) for y in range(1, config.GRID_HEIGHT-1) for x in range(1, config.GRID_WIDTH-1) if grid[y][x] == config.EMPTY]
    random.shuffle(empty_coords)

    coord_idx = 0 # Index for iterating through shuffled empty_coords

    # Function to safely place an item
    def place_item(item_type, count):
        nonlocal coord_idx
        placed = 0
        while placed < count and coord_idx < len(empty_coords):
            x, y = empty_coords[coord_idx]
            # Double check the cell is still empty (should be, but safety first)
            if grid[y][x] == config.EMPTY:
                grid[y][x] = item_type
                placed += 1
            coord_idx += 1
        if placed < count:
            print(f"WARN: Could not place all {item_type} items. Placed {placed}/{count}.")
        return placed

    # Place Hunters
    place_item(config.HUNTER, h_count)
    # Place Pushers
    place_item(config.PUSHER, p_count)
    # Place Sentinels
    place_item(config.SENTINEL, s_count)

    # Place Eggs (need special handling for time)
    egg_hatch_time_ms = level_def.get("egg_incubation_ms", 10000) # Default 10s
    now = utils.get_game_time()
    placed_eggs = 0
    while placed_eggs < e_count and coord_idx < len(empty_coords):
        x, y = empty_coords[coord_idx]
        if grid[y][x] == config.EMPTY:
            # Add slight randomization to hatch time (+/- 10%)
            factor = 0.9 + 0.2 * random.random()
            hatch_time = int(egg_hatch_time_ms * factor)
            grid[y][x] = (config.EGG, hatch_time, now) # Store type, duration, start time
            placed_eggs += 1
        coord_idx += 1
    if placed_eggs < e_count:
         print(f"WARN: Could not place all Eggs. Placed {placed_eggs}/{e_count}.")


    return grid

############################################################
# MAIN GAME CLASS (Conceptual - to be implemented)
############################################################
# class Game:
#     def __init__(self):
#         pygame.init()
#         # Initialize screen, clock, resources, high scores etc.
#         # Manage game state (menu, playing, game over)
#         # Manage lives, score, time
#         pass
#
#     def run(self):
#         # Main application loop
#         while True:
#             # Show menu / level select
#             # If level selected, create Level object and run game loop
#             # Handle game over, high scores
#             pass
#
#     def game_loop(self, level):
#         # Loop for playing a specific level (or sublevel)
#         # Handle input, updates, drawing for the level
#         pass

############################################################
# MAIN EXECUTION
############################################################
def main():
    global lives, cumulative_time, game_over_flag # Manage global state (TODO: Refactor)

    # --- Initialization ---
    pygame.init()
    pygame.mixer.init() # Initialize mixer for sounds

    # Set window title
    pygame.display.set_caption(f"{config.GAME_TITLE} - {config.COPYRIGHT_TEXT}")

    # Calculate screen dimensions based on config
    screen_width = config.GRID_WIDTH * (config.CHAR_WIDTH * config.SCALE_X * 2)
    screen_height = config.GRID_HEIGHT * (config.CHAR_HEIGHT * config.SCALE_Y) + config.STATUS_HEIGHT
    try:
        screen = pygame.display.set_mode((screen_width, screen_height))
    except pygame.error as e:
        print(f"ERROR: Failed to set display mode: {e}")
        sys.exit()

    clock = pygame.time.Clock()

    # Load resources
    resources.load_sprite_sheet() # Load default initially
    resources.load_sounds()
    resources.load_levels_json() # Load level definitions

    # --- Main Application Loop ---
    while True:
        # Reset game state for a new attempt
        lives = 3
        cumulative_time = 0 # Reset time for the whole game session
        utils.reset_pause_offset() # Reset pause timer offset
        game_over_flag = False # Ensure flag is reset

        # Show Level Selection
        selected_level_letter = level_selection_screen(screen, clock)
        if selected_level_letter is None: # Should not happen with current logic, but safety check
            break # Exit if level selection failed somehow

        # Get Level Definition
        level_def = resources.get_main_level_def(selected_level_letter)

        # Show Level Details and Confirm Start
        if show_level_details_screen(screen, clock, level_def):
            # Player confirmed, start playing the main level
            level_result = play_main_level(level_def, screen, clock)

            if level_result is not None:
                # Level completed successfully
                moves, enemies, time, score, level_name = level_result
                # Update cumulative time for potential high score recording
                # Note: play_main_level returns the time for *that level only*
                total_session_time = time # In this structure, cumulative time isn't tracked across multiple level plays in one run
                # Record high score if qualified
                hs_manager.maybe_record_and_show(score, level_name, screen, clock, total_session_time)
            else:
                # Level was quit or ended in game over
                # High score handling (if game over) is done within handle_collision -> hs_manager
                # If quit, no score is recorded here. hs_manager.show_screen might be called if needed.
                # Loop continues back to level selection
                pass
        else:
            # Player cancelled from level details screen, loop back to level selection
            continue

# Entry point
if __name__ == "__main__":
    main()
