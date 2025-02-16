# Squish

A game inspired by **Beast**, which was included in a version of WordPerfect Office or WordPerfect Works _ages_ ago. I played it to death on my old Tandy 1000 EX. I created this with some heavy lifting done by ChatGPT (o3 and o1), mainly to see whether it could be done. It obviously can. 

The original free version of the game is on the [Internet Archive](https://archive.org/details/msdos_Beast_1984). The version I played can be found on abandonware sites, as part of WordPerfect Library 2.0, e.g. on [Winworld](https://winworldpc.com/product/wordperfect-library/20). 

## About This Game

In **Squish**, you navigate a playing field while avoiding and eliminating different types of enemies by pushing blocks strategically. The game requires both quick reflexes and careful planning.

## Gameplay Features

- **Enemies**:
  - **Hunters**: Chase you down.
  - **Eggs**: Hatch into **Pushers** over time.
  - **Pushers**: Try to push blocks into you. They can only be squished between a block and a wall.
  - **Sentinels**: Move slower but require a different strategy to eliminate.
- **Scoring**:
  - Points are awarded based on enemy type and level.
  - Sentinels are worth the most points.
- **High Scores**: The game keeps track of your top scores.
- **Grid-Based Movement**: The game plays on a fixed-size grid with tile-based mechanics.

## Controls

- **Arrow Keys**: Move in four directions.
- **Esc**: Pause the game.
- **Q**: Quit the game.

## Running the Game

### Running from Source
Requires Python and `pygame`. Install dependencies and run:

```sh
git clone https://github.com/mvuijlst/squish.git
cd squish
pip install -r requirements.txt
python squish.py
```

### Running the Executable
If you have the `.exe` file, just double-click to start.

## Development Notes

This is a **recreation from memory**, so it's not quite the same as the original **Beast**.

## Contributing

- Report bugs or suggest changes via GitHub Issues.
- Pull requests with improvements are welcome.

## License

Licensed under the **MIT License**. See `LICENSE` for details.
