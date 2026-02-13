import csv, math, json, os, webbrowser, sys
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# Data classes
class City:
    def __init__(self, cid, name, state, sea_level_m):
        self.cid = cid
        self.name = name
        self.state = state
        self.sea_level_m = sea_level_m

class Edge:
    def __init__(self, src, dst, map_dist, real_dist):
        self.src = src
        self.dst = dst
        self.map_dist = map_dist
        self.real_dist = real_dist

# Graph
class Graph:
    def __init__(self):
        self.cities = {}
        self.adj = defaultdict(list)

    def add_c(self, c: City):
        self.cities[c.cid] = c

    def add_bidir_edge(self, src: str, dst: str, map_dist: float):
        if src not in self.cities or dst not in self.cities:
            return
        A = self.cities[src]; B = self.cities[dst]
        # elevation diff in miles (meters -> miles)(1 mile=1609.34 meters)
        delta_miles = (B.sea_level_m - A.sea_level_m) / 1609.34 if (A.sea_level_m is not None and B.sea_level_m is not None) else 0.0
        tan_ab = (delta_miles / map_dist) if map_dist != 0 else 0.0
        tan_ba = -tan_ab
        real_ab = max(map_dist * (1 + tan_ab), 0.01)
        real_ba = max(map_dist * (1 + tan_ba), 0.01)
        self.adj[src].append(Edge(src, dst, map_dist, real_ab))
        self.adj[dst].append(Edge(dst, src, map_dist, real_ba))

    def edge_dist(self, u, v):
        for e in self.adj.get(u, []):
            if e.dst == v:
                return e.real_dist
        for e in self.adj.get(v, []):
            if e.dst == u:
                return e.real_dist
        return 0.0

    # BFS path
    def bfs_path(self, start, dest):
        q = deque([start]); visited = {start}; parent = {start: None}
        while q:
            u = q.popleft()
            if u == dest: break
            for e in self.adj.get(u, []):
                if e.dst not in visited:
                    visited.add(e.dst)
                    parent[e.dst] = u
                    q.append(e.dst)
        return reconstruct(parent, start, dest)

    # DFS path (recursive)
    def dfs_path(self, start, dest):
        visited = set(); parent = {start: None}; found = [False]
        def _dfs(u):
            if found[0]: return
            visited.add(u)
            if u == dest:
                found[0] = True; return
            for e in self.adj.get(u, []):
                if e.dst not in visited:
                    parent[e.dst] = u
                    _dfs(e.dst)
        _dfs(start)
        return reconstruct(parent, start, dest)

    # Prim MST edges from start
    def prim_mst_edges(self, start):
        import heapq
        if start not in self.cities:
            return []
        visited = {start}
        pq = []
        for e in self.adj.get(start, []):
            heapq.heappush(pq, (e.real_dist, e.src, e.dst))
        mst = []
        while pq and len(visited) < len(self.cities):
            dist, u, v = heapq.heappop(pq)
            if v in visited:
                continue
            visited.add(v)
            for e in self.adj[u]:
                if e.dst == v:
                    mst.append(e)
                    break
            for ne in self.adj.get(v, []):
                if ne.dst not in visited:
                    heapq.heappush(pq, (ne.real_dist, ne.src, ne.dst))
        return mst

    def prim_path(self, start, dest):
        mst = self.prim_mst_edges(start)
        mst_adj = defaultdict(list)
        for e in mst:
            mst_adj[e.src].append(e.dst)
            mst_adj[e.dst].append(e.src)
        return tree_path_in_adj(mst_adj, start, dest)

    # Kruskal MST
    def kruskal_mst_edges(self):
        parent = {}; rank = {}
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        def union(a,b):
            ra, rb = find(a), find(b)
            if ra != rb:
                if rank[ra] < rank[rb]:
                    parent[ra] = rb
                elif rank[ra] > rank[rb]:
                    parent[rb] = ra
                else:
                    parent[rb] = ra
                    rank[ra] += 1

        for cid in self.cities:
            parent[cid] = cid; rank[cid] = 0

        edges = []
        seen = set()
        for u in self.adj:
            for e in self.adj[u]:
                key = tuple(sorted((e.src, e.dst)))
                if key not in seen:
                    seen.add(key)
                    edges.append(e)
        edges.sort(key=lambda x: x.real_dist)
        mst=[]
        for e in edges:
            if find(e.src) != find(e.dst):
                union(e.src, e.dst)
                mst.append(e)
        return mst

    def kruskal_path(self, start, dest):
        mst = self.kruskal_mst_edges()
        mst_adj = defaultdict(list)
        for e in mst:
            mst_adj[e.src].append(e.dst)
            mst_adj[e.dst].append(e.src)
        return tree_path_in_adj(mst_adj, start, dest)

    # Bellman-Ford
    def bellman_ford(self, start):
        dist = {c: math.inf for c in self.cities}
        pred = {c: None for c in self.cities}
        if start not in self.cities:
            return dist, pred
        dist[start] = 0.0
        all_edges = []
        for u in self.adj:
            for e in self.adj[u]:
                all_edges.append(e)
        for _ in range(len(self.cities)-1):
            updated = False
            for e in all_edges:
                if dist[e.src] + e.real_dist < dist[e.dst]:
                    dist[e.dst] = dist[e.src] + e.real_dist
                    pred[e.dst] = e.src
                    updated = True
            if not updated:
                break
        return dist, pred

    def bellman_path(self, start, dest):
        dist, pred = self.bellman_ford(start)
        if dist.get(dest, math.inf) == math.inf:
            return []
        return reconstruct(pred, start, dest)

# WeatherRisk
class WeatherRisk:
    def __init__(self):
        self.risk = defaultdict(dict)
        self.dates = []

    def load(self, path):
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                cid = (r.get("city_id") or r.get("city") or r.get("id") or "").strip()
                if not cid:
                    continue
                date = (r.get("date") or "").strip()
                raw = (r.get("risk") or "").strip()
                try:
                    val = float(raw)
                except:
                    digits = ''.join(ch for ch in raw if (ch.isdigit() or ch=='.' or ch=='-'))
                    val = float(digits) if digits else 0.0
                self.risk[cid][date] = val
                if date and date not in self.dates:
                    self.dates.append(date)
        self.dates.sort()

    def edge_risk(self, c1, c2, date):
        return (self.risk.get(c1, {}).get(date, 0.0) + self.risk.get(c2, {}).get(date, 0.0)) / 2.0

# helpers
def reconstruct(parent, start, dest):
    if dest == start:
        return [start]
    if dest not in parent:
        return []
    path = []
    cur = dest
    while cur is not None:
        path.append(cur)
        if cur == start:
            break
        cur = parent.get(cur)
    path.reverse()
    if path and path[0] == start:
        return path
    return []

def tree_path_in_adj(adj, start, dest):
    q = deque([start]); visited = {start}; parent = {start: None}
    while q:
        u = q.popleft()
        if u == dest:
            break
        for v in adj.get(u, []):
            if v not in visited:
                visited.add(v); parent[v] = u; q.append(v)
    return reconstruct(parent, start, dest)

def path_distance(g, route):
    total = 0.0
    for i in range(len(route)-1):
        total += g.edge_dist(route[i], route[i+1])
    return total

def gas_used(distance):
    return distance / 45.0

def best_date_for_path(route, wr):
    best_date = None; best_risk = math.inf
    if not route or len(route) < 2:
        return None, 0.0
    for date in wr.dates:
        ok = True; total = 0.0
        for i in range(len(route)-1):
            c1, c2 = route[i], route[i+1]
            if date not in wr.risk.get(c1, {}) or date not in wr.risk.get(c2, {}):
                ok = False; break
            total += wr.edge_risk(c1, c2, date)
        if ok and total < best_risk:
            best_risk = total; best_date = date
    if best_date is None:
        return None, 0.0
    return best_date, best_risk


# Global objects
G = None
WR = None
ID_TO_NAME = {}

# HTTP Handler
class RouteHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/cities":
            self.handle_cities()
        elif path == "/route":
            self.handle_route(parsed.query)
        else:
            return super().do_GET()

    def handle_cities(self):
        data = {"cities": []}
        # sort by name for UI nicety
        for cid, c in sorted(G.cities.items(), key=lambda x: x[1].name):
            data["cities"].append({"id": cid, "name": c.name, "state": c.state})
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def handle_route(self, query):
        params = parse_qs(query)
        src = params.get("src", [None])[0]
        dst = params.get("dst", [None])[0]
        alg = (params.get("alg", ["BEST"])[0] or "BEST").upper()
        if not src or not dst:
            self.send_error(400, "Missing src or dst")
            return
        if src not in G.cities or dst not in G.cities:
            self.send_error(400, "Invalid src/dst")
            return

        def compute(algorithm):
            if algorithm == "BFS":
                route = G.bfs_path(src, dst); label = "BFS"
            elif algorithm == "DFS":
                route = G.dfs_path(src, dst); label = "DFS"
            elif algorithm == "PRIM":
                route = G.prim_path(src, dst); label = "Prim MST"
            elif algorithm == "KRUSKAL":
                route = G.kruskal_path(src, dst); label = "Kruskal MST"
            elif algorithm == "BELLMAN":
                route = G.bellman_path(src, dst); label = "Bellman-Ford"
            else:
                route = []; label = algorithm

            if not route:
                return {"ok": False, "label": label, "message": "No route found"}

            total = path_distance(G, route)
            gas = gas_used(total)
            best_date, risk = best_date_for_path(route, WR)
            segments = []
            for i in range(len(route)-1):
                u = route[i]; v = route[i+1]
                dist = G.edge_dist(u, v)
                segments.append({
                    "src_id": u,
                    "dst_id": v,
                    "src_name": ID_TO_NAME.get(u, u),
                    "dst_name": ID_TO_NAME.get(v, v),
                    "real_dist": dist
                })
            return {
                "ok": True,
                "algorithm_label": label,
                "route_ids": route,
                "route_names": [ID_TO_NAME.get(x, x) for x in route],
                "segments": segments,
                "total_distance": total,
                "gas_used": gas,
                "total_risk": risk,
                "best_travel_date": best_date,
                "score": total + 20.0 * risk
            }

        if alg == "BEST":
            results = {}
            for a in ["BFS","DFS","PRIM","KRUSKAL","BELLMAN"]:
                r = compute(a)
                if r.get("ok"):
                    results[a] = r
            if not results:
                data = {"ok": False, "message": "No algorithm found a path"}
            else:
                best_alg = min(results.keys(), key=lambda k: results[k]["score"])
                best = results[best_alg]
                data = {"ok": True, "algorithm": best_alg, "algorithm_label": best.get("algorithm_label"), **best}
        else:
            data = compute(alg)

        data["src_id"] = src
        data["dst_id"] = dst
        data["src_name"] = ID_TO_NAME.get(src, src)
        data["dst_name"] = ID_TO_NAME.get(dst, dst)

        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode('utf-8'))

# Server start function
def start_server():
    web_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(web_dir)
    port = 8080
    httpd = HTTPServer(("localhost", port), RouteHandler)
    url = f"http://localhost:{port}/index.html"
    print(f"[INFO] Serving directory: {web_dir}")
    print(f"[INFO] Opening browser at {url}")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server")
        httpd.server_close()

# Main: load CSVs, build graph, start server

def main():
    global G, WR, ID_TO_NAME
    folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(folder)
    G = Graph(); WR = WeatherRisk()

    # load cities.csv
    cities_file = "cities.csv"
    if not os.path.exists(cities_file):
        print("ERROR: cities.csv not found in folder:", folder); sys.exit(1)
    with open(cities_file, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            cid = (r.get("city_id") or r.get("id") or r.get("city") or "").strip()
            name = (r.get("city") or r.get("name") or cid).strip()
            state = (r.get("state") or "").strip()
            sea_raw = r.get("sea_level(in meters(m))") or r.get("sea") or r.get("elevation") or "0"
            try:
                sea = float(sea_raw)
            except:
                sea = 0.0
            if cid:
                G.add_c(City(cid, name, state, sea))

    ID_TO_NAME = {cid: c.name for cid, c in G.cities.items()}

    # load edges.csv
    edges_file = "edges.csv"
    if not os.path.exists(edges_file):
        print("ERROR: edges.csv not found"); sys.exit(1)
    with open(edges_file, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            src = (r.get("src_id") or r.get("src") or r.get("from") or "").strip()
            dst = (r.get("dst_id") or r.get("dst") or r.get("to") or "").strip()
            dist_raw = r.get("map_distance_miles") or r.get("distance") or r.get("dist") or "0"
            try:
                d = float(dist_raw)
            except:
                s = ''.join([c for c in dist_raw if c.isdigit() or c=='.'])
                d = float(s) if s else 0.0
            if src and dst:
                G.add_bidir_edge(src, dst, d)

    # load weather risk
    wr_file = "weather_risk.csv"
    if os.path.exists(wr_file):
        try:
            WR.load(wr_file)
        except Exception as ex:
            print("Warning: weather_risk load failed:", ex)

    print("[INFO] Graph loaded: cities:", len(G.cities), "edges approx:", sum(len(v) for v in G.adj.values())//2)
    start_server()

if __name__ == "__main__":
    main()
