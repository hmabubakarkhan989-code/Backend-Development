"""AI search engine: graph model + BFS, DFS, UCS and A* path finding."""
import heapq
import math
import time
from collections import deque


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two coordinates in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Graph:
    """Undirected weighted graph. Locations = nodes, roads = edges."""

    def __init__(self):
        self.names, self.coords, self.adj = {}, {}, {}
        self.blocked = set()  # set of frozenset({a, b})

    def add_node(self, nid, name, lat, lon):
        self.names[nid] = name
        self.coords[nid] = (lat, lon)
        self.adj[nid] = {}

    def add_edge(self, a, b, cost):
        self.adj[a][b] = cost
        self.adj[b][a] = cost

    def has_edge(self, a, b):
        return a in self.adj and b in self.adj[a]

    def is_blocked(self, a, b):
        return frozenset((a, b)) in self.blocked

    def toggle_block(self, a, b):
        key = frozenset((a, b))
        self.blocked.symmetric_difference_update({key})
        return key in self.blocked

    def clear_blocks(self):
        self.blocked.clear()

    def neighbors(self, node):
        """Open (unblocked) neighbours in a fixed order, so results are repeatable."""
        for nbr, cost in sorted(self.adj[node].items()):
            if frozenset((node, nbr)) not in self.blocked:
                yield nbr, cost

    def heuristic(self, a, b):
        """Straight-line distance. Never larger than the real road cost -> admissible."""
        return haversine_km(*self.coords[a], *self.coords[b])

    def path_cost(self, path):
        return sum(self.adj[a][b] for a, b in zip(path, path[1:]))


def _trace(parent, goal):
    path = []
    while goal is not None:
        path.append(goal)
        goal = parent[goal]
    return path[::-1]


def _result(graph, name, path, order, started):
    return {
        "algorithm": name,
        "found": path is not None,
        "path": path or [],
        "cost": round(graph.path_cost(path), 2) if path else None,
        "hops": len(path) - 1 if path else None,
        "visited": len(order),
        "visited_order": order,
        "time_ms": round((time.perf_counter() - started) * 1000, 4),
    }


def bfs(graph, start, goal):
    """Breadth-First Search: fewest roads (edges), ignores road cost."""
    t0 = time.perf_counter()
    queue, parent, order = deque([start]), {start: None}, []
    while queue:
        node = queue.popleft()
        order.append(node)
        if node == goal:
            return _result(graph, "BFS", _trace(parent, goal), order, t0)
        for nbr, _ in graph.neighbors(node):
            if nbr not in parent:
                parent[nbr] = node
                queue.append(nbr)
    return _result(graph, "BFS", None, order, t0)


def dfs(graph, start, goal):
    """Depth-First Search: goes deep first. Finds *a* path, not the best one."""
    t0 = time.perf_counter()
    stack, parent, order = [(start, None)], {}, []
    while stack:
        node, prev = stack.pop()
        if node in parent:
            continue
        parent[node] = prev
        order.append(node)
        if node == goal:
            return _result(graph, "DFS", _trace(parent, goal), order, t0)
        for nbr, _ in reversed(list(graph.neighbors(node))):
            if nbr not in parent:
                stack.append((nbr, node))
    return _result(graph, "DFS", None, order, t0)


def _best_first(graph, name, start, goal, use_heuristic):
    t0 = time.perf_counter()
    h = (lambda n: graph.heuristic(n, goal)) if use_heuristic else (lambda n: 0.0)
    heap = [(h(start), 0.0, start)]
    best, parent, closed, order = {start: 0.0}, {start: None}, set(), []
    while heap:
        _, g, node = heapq.heappop(heap)
        if node in closed:
            continue
        closed.add(node)
        order.append(node)
        if node == goal:
            return _result(graph, name, _trace(parent, goal), order, t0)
        for nbr, cost in graph.neighbors(node):
            new_g = g + cost
            if new_g < best.get(nbr, math.inf):
                best[nbr] = new_g
                parent[nbr] = node
                heapq.heappush(heap, (new_g + h(nbr), new_g, nbr))
    return _result(graph, name, None, order, t0)


def ucs(graph, start, goal):
    """Uniform-Cost Search: cheapest total road cost (optimal)."""
    return _best_first(graph, "UCS", start, goal, use_heuristic=False)


def astar(graph, start, goal):
    """A*: cost so far + straight-line estimate. Optimal and explores fewer nodes."""
    return _best_first(graph, "A*", start, goal, use_heuristic=True)


ALGORITHMS = {"BFS": bfs, "DFS": dfs, "UCS": ucs, "A*": astar}


def run_all(graph, start, goal):
    return [fn(graph, start, goal) for fn in ALGORITHMS.values()]
