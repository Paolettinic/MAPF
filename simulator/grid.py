import pathlib
import numpy as np


class Grid:
    """

    """
    def __init__(self, grid_file: pathlib.Path) -> None:
        """
        :param grid_file:
        """
        with open(grid_file, 'r') as grid:
            next(grid)
            self.height = int(next(grid).split(" ")[1])
            self.width = int(next(grid).split(" ")[1])
            self.grid = np.ones((self.height, self.width))
            self.shelves_pos = []
            next(grid)
            for i, row in enumerate(grid):
                for j, cell in enumerate(row):
                    if cell == "T":
                        is_shelf = 1 < i < self.height - 1 and 1 < j < self.width - 1
                        if is_shelf:
                            self.shelves_pos.append((j, i))
                        self.grid[i][j] = 0

    def save(self, path: pathlib.Path = "saved.map") -> None:
        np.save(path, self.grid)

    def load(self, path: pathlib.Path) -> None:
        self.grid = np.load(path)

    def __str__(self):
        return str(self.grid)

    def __getitem__(self, item):
        return self.grid[item]
