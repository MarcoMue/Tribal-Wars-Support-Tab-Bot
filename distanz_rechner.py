import math

class DistanzRechner:
    @staticmethod
    def berechne_distanz(coord1: str, coord2: str) -> float:
        x1, y1 = map(int, coord1.split("|"))
        x2, y2 = map(int, coord2.split("|"))
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
