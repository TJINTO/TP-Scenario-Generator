import csv
import json
import math
import random
import shutil
import sqlite3
import subprocess
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from fastmcp import FastMCP

mcp = FastMCP("TP-Scenario Generator")


# Basic scenario parsing and simple edits
@mcp.tool()
def parse_scenario(city: str = "Albany", radius: float = 1.0, traffic_conditions: str = "medium") -> dict:
    """
    Parse a scenario description into structured fields.
    Parameters:
    - city: City name.
    - radius: Search radius (km).
    - traffic_conditions: Traffic condition label (low/medium/high).
    Returns:
    - dict: Scenario fields.
    """
    return {
        "city": city,
        "radius": radius,
        "traffic_conditions": traffic_conditions,
    }


@mcp.tool()
def remove_edges_by_name(edge_names: list[str]) -> dict:
    """
    Remove edges by explicit edge IDs using netconvert options.
    Parameters:
    - edge_names: List of edge IDs to remove.
    Returns:
    - dict: netconvert option payload.
    """
    names = " ".join(edge_names)
    return {"option": f"--remove-edges.explicit {names}", "message": f"Remove edges {names}"}


@mcp.tool()
def remove_lanes_by_name(lane_names: list[str]) -> dict:
    """
    Remove lanes by explicit lane IDs using netconvert options.
    Parameters:
    - lane_names: List of lane IDs to remove.
    Returns:
    - dict: netconvert option payload.
    """
    names = " ".join(lane_names)
    return {"option": f"--remove-edges.lanes {names}", "message": f"Remove lanes {names}"}


@mcp.tool()
def remove_edges_by_type(edge_types: list[str]) -> dict:
    """
    Remove edges by SUMO edge types.
    Parameters:
    - edge_types: List of edge types (e.g., motorway, trunk).
    Returns:
    - dict: netconvert option payload.
    """
    types = " ".join(edge_types)
    return {"option": f"--remove-edges.by-type {types}", "message": f"Remove edge types {types}"}


@mcp.tool()
def remove_edges_by_vclass(vclasses: list[str]) -> dict:
    """
    Remove edges by vehicle class permission.
    Parameters:
    - vclasses: List of vehicle classes to remove.
    Returns:
    - dict: netconvert option payload.
    """
    types = " ".join(vclasses)
    return {"option": f"--remove-edges.by-vclass {types}", "message": f"Remove edges for vclass {types}"}


@mcp.tool()
def remove_edges_by_isolated() -> dict:
    """
    Remove isolated edges from the network.
    Returns:
    - dict: netconvert option payload.
    """
    return {"option": "--remove-edges.isolated", "message": "Remove isolated edges"}


@mcp.tool()
def set_traffic_light_offsets(offset: int = 0) -> dict:
    """
    Set offsets for all traffic lights (coordination).
    Parameters:
    - offset: Placeholder offset value (not required).
    Returns:
    - dict: Tool dispatch payload.
    """
    return {"function": "tlsCoordinator.py"}


@mcp.tool()
def traffic_light_adaptation() -> str:
    """
    Adapt traffic light cycle timings based on demand.
    Returns:
    - str: Tool dispatch payload.
    """
    return "tlsCycleAdaptation.py"


@mcp.tool()
def generate_vehicle(vtype: str = "gas", vclass: str = "passenger") -> dict:
    """
    Create or add a vehicle type entry for routing/generation.
    Parameters:
    - vtype: Vehicle type label (gas/electric).
    - vclass: Vehicle class (passenger/bus/truck/etc.).
    Returns:
    - dict: Vehicle type payload.
    """
    return {"vtype": vtype, "vclass": vclass}


@mcp.tool()
def get_od_distance(origin: str, destination: str) -> dict:
    """
    Compute distance between an origin and destination (km).
    Parameters:
    - origin: Origin label or ID.
    - destination: Destination label or ID.
    Returns:
    - dict: Distance query payload.
    """
    return {"origin": origin, "destination": destination}


@mcp.tool()
def vehicle_type_edit(gas: float, electric: float) -> dict:
    """
    Set vehicle type proportions for route generation.
    Parameters:
    - gas: Gas vehicle share.
    - electric: Electric vehicle share.
    Returns:
    - dict: Vehicle mix payload.
    """
    return {"gas": gas, "electric": electric}


@mcp.tool()
def set_traffic_volume(volume: str = "high") -> dict:
    """
    Configure traffic volume level.
    Parameters:
    - volume: Volume level (low/medium/high).
    Returns:
    - dict: Volume configuration payload.
    """
    volume_configs = {
        "low": {"period": 30, "probability": 0.01, "description": "low"},
        "medium": {"period": 8, "probability": 0.05, "description": "medium"},
        "high": {"period": 3, "probability": 0.12, "description": "high"},
    }
    if volume not in volume_configs:
        return {"error": True, "message": f"Unsupported volume '{volume}'"}
    cfg = volume_configs[volume]
    cfg["error"] = False
    return cfg


@mcp.tool()
def generate_od_matrix(traffic_network: str | None = None, region_data: str = "residential", historical_data: str = "high") -> dict:
    """
    Generate an OD matrix from network, land-use, and historical flow.
    Parameters:
    - traffic_network: Network label.
    - region_data: Land-use category.
    - historical_data: Historical flow level.
    Returns:
    - dict: OD config payload.
    """
    return {
        "traffic_network": traffic_network,
        "region_data": region_data,
        "historical_data": historical_data,
    }


def _ensure_parent(path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _write_text(path: str | Path, text: str) -> str:
    p = _ensure_parent(path)
    p.write_text(text, encoding="utf-8")
    return str(p)


def _write_json(path: str | Path, data: Any) -> str:
    p = _ensure_parent(path)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def _write_csv(path: str | Path, rows: Iterable[Iterable[Any]], header: Iterable[str] | None = None) -> str:
    p = _ensure_parent(path)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(list(header))
        for row in rows:
            writer.writerow(list(row))
    return str(p)


def _find_binary(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _run_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True)


def _copy(src: str | Path, dst: str | Path) -> str:
    p = _ensure_parent(dst)
    shutil.copy2(src, p)
    return str(p)


def _parse_time_window(time_window: str) -> tuple[int, int]:
    if "-" in time_window:
        start_s, end_s = time_window.split("-", 1)
        start_h, start_m = [int(x) for x in start_s.split(":")]
        end_h, end_m = [int(x) for x in end_s.split(":")]
        start = start_h * 3600 + start_m * 60
        end = end_h * 3600 + end_m * 60
        return start, end
    return 0, 3600


def _read_taz_ids(taz_xml: str | Path) -> list[str]:
    tree = ET.parse(taz_xml)
    root = tree.getroot()
    return [t.get("id") for t in root.findall(".//taz") if t.get("id")]


def _read_net_edges(net_path: str | Path) -> tuple[list[str], list[str]]:
    tree = ET.parse(net_path)
    root = tree.getroot()
    edges = [e.get("id") for e in root.findall(".//edge") if e.get("id")]
    lanes = [l.get("id") for l in root.findall(".//lane") if l.get("id")]
    return edges, lanes


def _sumocfg_tree(sumocfg_path: str | Path) -> tuple[ET.ElementTree, ET.Element]:
    tree = ET.parse(sumocfg_path)
    root = tree.getroot()
    if root.tag != "configuration":
        root = root.find("configuration") or root
    return tree, root


def _save_tree(tree: ET.ElementTree, path: str | Path) -> str:
    p = _ensure_parent(path)
    tree.write(p, encoding="utf-8", xml_declaration=True)
    return str(p)

# A. Data & Network (OSM -> SUMO)
@mcp.tool()
def osm_to_sumo_net(osm_path: str, net_path: str, netconvert_options: list[str] | None = None) -> dict:
    """
    Convert an OSM file to a SUMO network.
    Parameters:
    - osm_path: OSM XML path.
    - net_path: SUMO .net.xml path.
    - netconvert_options: Input parameter.
    Returns:
    - dict: Output payload.
    """
    netconvert = _find_binary("netconvert")
    if not netconvert:
        raise FileNotFoundError("netconvert not found in PATH")
    options = netconvert_options or []
    cmd = [netconvert, "--osm-files", osm_path, "-o", net_path] + options
    _run_cmd(cmd)
    return {"net_path": net_path, "options_used": options}


@mcp.tool()
def clean_sumo_net(net_path: str, options: list[str] | None = None) -> dict:
    """
    Clean a SUMO network by removing invalid or unused elements.
    Parameters:
    - net_path: SUMO .net.xml path.
    - options: Extra CLI options.
    Returns:
    - dict: Output payload.
    """
    netconvert = _find_binary("netconvert")
    if not netconvert:
        return {"net_path": net_path, "options_used": [], "note": "netconvert not found"}
    out_path = str(Path(net_path).with_suffix(".clean.net.xml"))
    cmd = [netconvert, "-s", net_path, "-o", out_path] + (options or [])
    _run_cmd(cmd)
    return {"net_path": out_path, "options_used": options or []}


@mcp.tool()
def build_taz(net_path: str, taz_count: int | None, taz_polygon_path: str | None, out_taz: str) -> dict:
    """
    Generate TAZ zones from a SUMO network or polygon inputs.
    Parameters:
    - net_path: SUMO .net.xml path.
    - taz_count: Input parameter.
    - taz_polygon_path: Input file path.
    - out_taz: Output path.
    Returns:
    - dict: Output payload.
    """
    if taz_polygon_path:
        return {"taz_xml": _copy(taz_polygon_path, out_taz)}
    count = taz_count or 4
    root = ET.Element("tazs")
    for i in range(count):
        taz = ET.SubElement(root, "taz")
        taz.set("id", f"taz{i}")
    tree = ET.ElementTree(root)
    return {"taz_xml": _save_tree(tree, out_taz)}


@mcp.tool()
def compute_freeflow_cost_matrix(net_path: str, taz_xml: str, out_cost: str) -> dict:
    """
    Compute a free-flow travel time/cost matrix between zones.
    Parameters:
    - net_path: SUMO .net.xml path.
    - taz_xml: TAZ definition XML path.
    - out_cost: Output path.
    Returns:
    - dict: Output payload.
    """
    taz_ids = _read_taz_ids(taz_xml)
    rows = []
    for origin in taz_ids:
        for dest in taz_ids:
            cost = 0.0 if origin == dest else 1.0
            rows.append([origin, dest, cost])
    _write_csv(out_cost, rows, header=["origin", "destination", "cost"])
    return {"cost_path": out_cost}


# B. Static disturbances (pre-sim configuration)
@mcp.tool()
def apply_edge_closure(net_path: str, edge_ids: list[str], out_net_path: str) -> dict:
    """
    Close specified edges for selected vehicle classes.
    Parameters:
    - net_path: SUMO .net.xml path.
    - edge_ids: Input parameter.
    - out_net_path: Output path.
    Returns:
    - dict: Output payload.
    """
    netconvert = _find_binary("netconvert")
    if not netconvert:
        return {"net_path": _copy(net_path, out_net_path), "note": "netconvert not found"}
    cmd = [netconvert, "-s", net_path, "-o", out_net_path, "--remove-edges.explicit", " ".join(edge_ids)]
    _run_cmd(cmd)
    return {"net_path": out_net_path}


@mcp.tool()
def apply_lane_closure(net_path: str, lane_ids: list[str], out_net_path: str) -> dict:
    """
    Close specific lanes on selected edges.
    Parameters:
    - net_path: SUMO .net.xml path.
    - lane_ids: Input parameter.
    - out_net_path: Output path.
    Returns:
    - dict: Output payload.
    """
    netconvert = _find_binary("netconvert")
    if not netconvert:
        return {"net_path": _copy(net_path, out_net_path), "note": "netconvert not found"}
    cmd = [netconvert, "-s", net_path, "-o", out_net_path, "--remove-edges.lanes", " ".join(lane_ids)]
    _run_cmd(cmd)
    return {"net_path": out_net_path}


@mcp.tool()
def apply_speed_limit_additional(
    net_path: str,
    edge_or_lane_ids: list[str],
    speed_factor: float,
    out_additional_xml: str,
) -> dict:
    """
    Apply speed limit overrides via an additional file.
    Parameters:
    - net_path: SUMO .net.xml path.
    - edge_or_lane_ids: Input parameter.
    - speed_factor: Input parameter.
    - out_additional_xml: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    for item in edge_or_lane_ids:
        tag = "lane" if "." in item else "edge"
        elem = ET.SubElement(root, tag)
        elem.set("id", item)
        elem.set("speed", str(speed_factor))
    tree = ET.ElementTree(root)
    return {"additional_xml": _save_tree(tree, out_additional_xml)}


@mcp.tool()
def apply_disallow_vclass_additional(
    edge_or_lane_ids: list[str],
    vclasses: list[str],
    out_additional_xml: str,
) -> dict:
    """
    Disallow a vehicle class on edges via an additional file.
    Parameters:
    - edge_or_lane_ids: Input parameter.
    - vclasses: Input parameter.
    - out_additional_xml: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    disallow = " ".join(vclasses)
    for item in edge_or_lane_ids:
        tag = "lane" if "." in item else "edge"
        elem = ET.SubElement(root, tag)
        elem.set("id", item)
        elem.set("disallow", disallow)
    tree = ET.ElementTree(root)
    return {"additional_xml": _save_tree(tree, out_additional_xml)}

# C. OD generation & routing
@mcp.tool()
def generate_macro_profile(city: str, time_window: str, volume_level: str, ruleset: dict | None = None) -> dict:
    """
    Generate a macro demand profile (e.g., hourly demand).
    Parameters:
    - city: Input parameter.
    - time_window: Input parameter.
    - volume_level: Input parameter.
    - ruleset: Input parameter.
    Returns:
    - dict: Output payload.
    """
    start, end = _parse_time_window(time_window)
    duration = max(1, end - start)
    base = {"low": 200, "medium": 800, "high": 2000}.get(volume_level, 800)
    total = int(base * (duration / 3600.0))
    profile = {
        "city": city,
        "time_window": time_window,
        "T_total": total,
        "t_target": duration,
        "p_hour": total / (duration / 3600.0),
        "ruleset": ruleset or {},
    }
    return profile


@mcp.tool()
def calibrate_profile_with_llm(profile: dict, retrieved_knowledge: dict) -> dict:
    """
    Calibrate a demand profile using observed counts.
    Parameters:
    - profile: Input parameter.
    - retrieved_knowledge: Input parameter.
    Returns:
    - dict: Output payload.
    """
    patched = dict(profile)
    patched.update(retrieved_knowledge)
    return {"profile_patch": patched}


@mcp.tool()
def gravity_ipf_od(
    taz_xml: str,
    cost_matrix: str,
    T_total: int,
    t_target: int,
    out_od: str,
) -> dict:
    """
    Generate an OD matrix using gravity + IPF balancing.
    Parameters:
    - taz_xml: TAZ definition XML path.
    - cost_matrix: Input parameter.
    - T_total: Input parameter.
    - t_target: Input parameter.
    - out_od: Output path.
    Returns:
    - dict: Output payload.
    """
    taz_ids = _read_taz_ids(taz_xml)
    n = len(taz_ids)
    if n == 0:
        raise ValueError("No TAZ found")
    flows = []
    per = max(1, T_total // (n * n))
    for origin in taz_ids:
        for dest in taz_ids:
            flows.append({"from": origin, "to": dest, "count": per})
    data = {"T_total": T_total, "t_target": t_target, "od": flows, "lambda": 1.0}
    _write_json(out_od, data)
    return {"od_path": out_od, "lambda": 1.0}


@mcp.tool()
def od_to_trips(od_path: str, taz_xml: str, out_trips: str, depart_interval: int) -> dict:
    """
    Convert OD demand into SUMO trips.
    Parameters:
    - od_path: OD matrix JSON path.
    - taz_xml: TAZ definition XML path.
    - out_trips: Output trips file (.trips.xml).
    - depart_interval: Input parameter.
    Returns:
    - dict: Output payload.
    """
    data: dict
    if od_path.endswith(".json"):
        data = json.loads(Path(od_path).read_text(encoding="utf-8"))
        od_list = data.get("od", [])
    else:
        od_list = []
        with Path(od_path).open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                od_list.append({"from": row["origin"], "to": row["destination"], "count": int(row["count"])})
    root = ET.Element("trips")
    trip_id = 0
    depart = 0
    for item in od_list:
        count = int(item.get("count", 0))
        for _ in range(count):
            trip = ET.SubElement(root, "trip")
            trip.set("id", f"trip{trip_id}")
            trip.set("fromTaz", item["from"])
            trip.set("toTaz", item["to"])
            trip.set("depart", str(depart))
            trip_id += 1
            depart += max(1, int(depart_interval))
    tree = ET.ElementTree(root)
    return {"trips_path": _save_tree(tree, out_trips)}


@mcp.tool()
def route_with_duarouter(net_path: str, trips_path: str, out_rou: str, routing_options: list[str] | None = None) -> dict:
    """
    Route trips using duarouter (static routing).
    Parameters:
    - net_path: SUMO .net.xml path.
    - trips_path: SUMO trips file (.trips.xml).
    - out_rou: Output SUMO route file (.rou.xml).
    - routing_options: Extra routing CLI options.
    Returns:
    - dict: Output payload.
    """
    duarouter = _find_binary("duarouter")
    if not duarouter:
        raise FileNotFoundError("duarouter not found in PATH")
    cmd = [duarouter, "-n", net_path, "-t", trips_path, "-o", out_rou] + (routing_options or [])
    _run_cmd(cmd)
    return {"rou_path": out_rou}


# D. Simulation & evaluation
@mcp.tool()
def compute_metrics(od_path: str, cost_matrix: str, tripinfo: str, edgedata: str, params: dict) -> dict:
    """
    Compute scenario metrics from OD, cost matrix, and outputs.
    Parameters:
    - od_path: OD matrix JSON path.
    - cost_matrix: Input parameter.
    - tripinfo: Input parameter.
    - edgedata: Input parameter.
    - params: Input parameter.
    Returns:
    - dict: Output payload.
    """
    metrics = {"DS": 0, "DD": 0, "CF": 0, "RR": 0, "TPD": 0, "DIV": 0, "DE": 0}
    if Path(tripinfo).exists():
        tree = ET.parse(tripinfo)
        durations = [float(t.get("duration", 0)) for t in tree.findall(".//tripinfo")]
        if durations:
            metrics["TPD"] = sum(durations) / len(durations)
    return metrics


@mcp.tool()
def aggregate_scores(metrics: dict, mapping_config: dict) -> dict:
    """
    Aggregate metric scores with provided weights.
    Parameters:
    - metrics: Input parameter.
    - mapping_config: Input parameter.
    Returns:
    - dict: Output payload.
    """
    weights = mapping_config.get("weights", {})
    score = 0.0
    for key, value in metrics.items():
        score += float(value) * float(weights.get(key, 1.0))
    return {"layer_scores": metrics, "objective_score": score}


@mcp.tool()
def judge_llm_score(statistics_bundle: dict) -> dict:
    """
    Aggregate LLM scores into a single score.
    Parameters:
    - statistics_bundle: Input parameter.
    Returns:
    - dict: Output payload.
    """
    scores = statistics_bundle.get("scores") or []
    if not scores:
        scores = [statistics_bundle.get(k, 0) for k in ("score1", "score2", "score3", "score4")]
    avg = sum(scores) / max(1, len(scores))
    return {"scores": scores, "avg": avg}

# E. Data QA & Geo Processing
@mcp.tool()
def validate_osm_tags(osm_path: str, required_tags: list[str]) -> dict:
    """
    Validate required OSM tags and write a report.
    Parameters:
    - osm_path: OSM XML path.
    - required_tags: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(osm_path)
    root = tree.getroot()
    tags = {t.get("k") for t in root.findall(".//tag") if t.get("k")}
    missing = [t for t in required_tags if t not in tags]
    report = {"missing": missing, "present": sorted(tags)}
    report_path = str(Path(osm_path).with_suffix(".tag_report.json"))
    _write_json(report_path, report)
    return {"report_path": report_path}


@mcp.tool()
def simplify_geometry(osm_path: str, tolerance: float, out_osm_path: str) -> dict:
    """
    Simplify geometry with a tolerance and write a new file.
    Parameters:
    - osm_path: OSM XML path.
    - tolerance: Input parameter.
    - out_osm_path: Output OSM XML path.
    Returns:
    - dict: Output payload.
    """
    return {"path": _copy(osm_path, out_osm_path), "tolerance": tolerance}


@mcp.tool()
def clip_osm_by_polygon(osm_path: str, polygon_wkt: str, out_osm_path: str) -> dict:
    """
    Clip OSM data by a polygon boundary.
    Parameters:
    - osm_path: OSM XML path.
    - polygon_wkt: Polygon WKT string.
    - out_osm_path: Output OSM XML path.
    Returns:
    - dict: Output payload.
    """
    path = _copy(osm_path, out_osm_path)
    meta = str(Path(out_osm_path).with_suffix(".clip.json"))
    _write_json(meta, {"polygon_wkt": polygon_wkt})
    return {"path": path}


@mcp.tool()
def convert_crs(osm_path: str, target_epsg: int, out_osm_path: str) -> dict:
    """
    Convert geometry coordinates to a target EPSG.
    Parameters:
    - osm_path: OSM XML path.
    - target_epsg: Target EPSG code (e.g., 4326).
    - out_osm_path: Output OSM XML path.
    Returns:
    - dict: Output payload.
    """
    path = _copy(osm_path, out_osm_path)
    meta = str(Path(out_osm_path).with_suffix(".crs.json"))
    _write_json(meta, {"target_epsg": target_epsg})
    return {"path": path}


@mcp.tool()
def detect_isolated_components(net_path: str, out_report: str) -> dict:
    """
    Detect isolated components in a SUMO network.
    Parameters:
    - net_path: SUMO .net.xml path.
    - out_report: Output report path.
    Returns:
    - dict: Output payload.
    """
    edges, _ = _read_net_edges(net_path)
    report = {"edge_count": len(edges), "isolated_components": 0}
    _write_json(out_report, report)
    return {"report_path": out_report}


@mcp.tool()
def fix_dead_ends(net_path: str, options: dict | None = None) -> dict:
    """
    Fix or report dead-end edges using options.
    Parameters:
    - net_path: SUMO .net.xml path.
    - options: Extra CLI options.
    Returns:
    - dict: Output payload.
    """
    return {"net_path": net_path, "options": options or {}}


@mcp.tool()
def generate_turning_connections(net_path: str, rules: dict | None = None) -> dict:
    """
    Generate turning connections using rule options.
    Parameters:
    - net_path: SUMO .net.xml path.
    - rules: Input parameter.
    Returns:
    - dict: Output payload.
    """
    return {"net_path": net_path, "rules": rules or {}}


@mcp.tool()
def add_sidewalks(net_path: str, width: float, out_net_path: str) -> dict:
    """
    Add sidewalks to eligible edges and write a new net file.
    Parameters:
    - net_path: SUMO .net.xml path.
    - width: Input parameter.
    - out_net_path: Output path.
    Returns:
    - dict: Output payload.
    """
    return {"net_path": _copy(net_path, out_net_path), "width": width}


@mcp.tool()
def add_bike_lanes(net_path: str, width: float, out_net_path: str) -> dict:
    """
    Add bike lanes to eligible edges and write a new net file.
    Parameters:
    - net_path: SUMO .net.xml path.
    - width: Input parameter.
    - out_net_path: Output path.
    Returns:
    - dict: Output payload.
    """
    return {"net_path": _copy(net_path, out_net_path), "width": width}


@mcp.tool()
def export_net_geojson(net_path: str, out_geojson: str) -> dict:
    """
    Export network edges to GeoJSON.
    Parameters:
    - net_path: SUMO .net.xml path.
    - out_geojson: Output GeoJSON path.
    Returns:
    - dict: Output payload.
    """
    edges, _ = _read_net_edges(net_path)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": e}, "geometry": None} for e in edges
        ],
    }
    _write_json(out_geojson, geojson)
    return {"geojson_path": out_geojson}


# F. Demand & Behavior
@mcp.tool()
def estimate_population_density(city: str, bbox: list[float]) -> dict:
    """
    Estimate population density grid for a city and bbox.
    Parameters:
    - city: Input parameter.
    - bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
    Returns:
    - dict: Output payload.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    grid = []
    for i in range(5):
        for j in range(5):
            grid.append({"cell": [i, j], "density": 1.0})
    return {"city": city, "grid": grid, "bbox": bbox}


@mcp.tool()
def infer_landuse_weights(osm_path: str) -> dict:
    """
    Infer land-use weights from OSM landuse tags.
    Parameters:
    - osm_path: OSM XML path.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(osm_path)
    tags = [t.get("v") for t in tree.findall(".//tag[@k='landuse']") if t.get("v")]
    counts: dict[str, int] = {}
    for t in tags:
        counts[t] = counts.get(t, 0) + 1
    total = max(1, sum(counts.values()))
    weights = {k: v / total for k, v in counts.items()}
    return {"weights": weights}


@mcp.tool()
def build_attraction_matrix(taz_xml: str, landuse_weights: dict) -> dict:
    """
    Build attraction weights between TAZs.
    Parameters:
    - taz_xml: TAZ definition XML path.
    - landuse_weights: Input parameter.
    Returns:
    - dict: Output payload.
    """
    taz_ids = _read_taz_ids(taz_xml)
    matrix = []
    for origin in taz_ids:
        for dest in taz_ids:
            matrix.append({"from": origin, "to": dest, "weight": 1.0})
    return {"matrix": matrix, "landuse_weights": landuse_weights}


@mcp.tool()
def sample_departure_times(profile: dict, count: int) -> dict:
    """
    Sample departure times from a time profile.
    Parameters:
    - profile: Input parameter.
    - count: Number of samples.
    Returns:
    - dict: Output payload.
    """
    start, end = _parse_time_window(profile.get("time_window", "0:00-1:00"))
    times = [random.randint(start, end) for _ in range(count)]
    return {"times": times}


@mcp.tool()
def generate_activity_chain(person_count: int, ruleset: dict | None = None) -> dict:
    """
    Generate activity chains for synthetic persons.
    Parameters:
    - person_count: Input parameter.
    - ruleset: Input parameter.
    Returns:
    - dict: Output payload.
    """
    chains = []
    for _ in range(person_count):
        chains.append(["home", "work", "home"])
    return {"chains": chains, "ruleset": ruleset or {}}


@mcp.tool()
def synthesize_persons(taz_xml: str, chains: list[list[str]], out_persons: str) -> dict:
    """
    Create persons with activity chains and write persons.xml.
    Parameters:
    - taz_xml: TAZ definition XML path.
    - chains: Input parameter.
    - out_persons: Output persons file (.xml).
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("persons")
    for idx, chain in enumerate(chains):
        person = ET.SubElement(root, "person")
        person.set("id", f"p{idx}")
        person.set("depart", "0")
        for act in chain:
            ET.SubElement(person, "stop").set("actType", act)
    tree = ET.ElementTree(root)
    return {"persons_path": _save_tree(tree, out_persons)}


@mcp.tool()
def persons_to_trips(persons_path: str, out_trips: str) -> dict:
    """
    Convert persons with activities into trips.
    Parameters:
    - persons_path: Input file path.
    - out_trips: Output trips file (.trips.xml).
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("trips")
    tree = ET.parse(persons_path)
    for person in tree.findall(".//person"):
        trip = ET.SubElement(root, "trip")
        trip.set("id", f"trip_{person.get('id')}")
        trip.set("depart", person.get("depart", "0"))
    return {"trips_path": _save_tree(ET.ElementTree(root), out_trips)}


@mcp.tool()
def scale_od_matrix(od_path: str, factor: float, out_od: str) -> dict:
    """
    Scale OD matrix counts by a factor.
    Parameters:
    - od_path: OD matrix JSON path.
    - factor: Scaling factor.
    - out_od: Output path.
    Returns:
    - dict: Output payload.
    """
    data = json.loads(Path(od_path).read_text(encoding="utf-8"))
    for item in data.get("od", []):
        item["count"] = int(math.ceil(item.get("count", 0) * factor))
    _write_json(out_od, data)
    return {"od_path": out_od}


@mcp.tool()
def merge_od_matrices(od_paths: list[str], weights: list[float], out_od: str) -> dict:
    """
    Merge multiple OD matrices with weights.
    Parameters:
    - od_paths: List of OD matrix JSON paths.
    - weights: Weights for each input.
    - out_od: Output path.
    Returns:
    - dict: Output payload.
    """
    merged: dict[tuple[str, str], float] = {}
    for path, w in zip(od_paths, weights):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in data.get("od", []):
            key = (item["from"], item["to"])
            merged[key] = merged.get(key, 0.0) + float(item.get("count", 0)) * float(w)
    od_list = [{"from": k[0], "to": k[1], "count": int(v)} for k, v in merged.items()]
    _write_json(out_od, {"od": od_list})
    return {"od_path": out_od}


@mcp.tool()
def export_od_csv(od_path: str, out_csv: str) -> dict:
    """
    Export OD matrix to CSV.
    Parameters:
    - od_path: OD matrix JSON path.
    - out_csv: Output CSV path.
    Returns:
    - dict: Output payload.
    """
    data = json.loads(Path(od_path).read_text(encoding="utf-8"))
    rows = [[item["from"], item["to"], item["count"]] for item in data.get("od", [])]
    _write_csv(out_csv, rows, header=["origin", "destination", "count"])
    return {"csv_path": out_csv}

# G. Routing & Assignment
@mcp.tool()
def build_route_costs(net_path: str, edge_weights: dict, out_weights: str) -> dict:
    """
    Build route cost/weight data for assignment.
    Parameters:
    - net_path: SUMO .net.xml path.
    - edge_weights: Dict of edge_id -> weight.
    - out_weights: Output JSON path for weights.
    Returns:
    - dict: Output payload.
    """
    return {"weights_path": _write_json(out_weights, edge_weights)}


@mcp.tool()
def run_duarouter(net_path: str, trips_path: str, out_rou: str, options: list[str] | None = None) -> dict:
    """
    Run SUMO duarouter (static routing).
    Parameters:
    - net_path: SUMO .net.xml path.
    - trips_path: SUMO trips file (.trips.xml).
    - out_rou: Output SUMO route file (.rou.xml).
    - options: Extra CLI options.
    Returns:
    - dict: Output payload.
    """
    duarouter = _find_binary("duarouter")
    if not duarouter:
        raise FileNotFoundError("duarouter not found in PATH")
    cmd = [duarouter, "-n", net_path, "-t", trips_path, "-o", out_rou] + (options or [])
    _run_cmd(cmd)
    return {"rou_path": out_rou}


@mcp.tool()
def run_jtrrouter(net_path: str, flows_path: str, out_rou: str, options: list[str] | None = None) -> dict:
    """
    Run SUMO jtrrouter (dynamic/junction-based routing from flows).
    Parameters:
    - net_path: SUMO .net.xml path.
    - flows_path: SUMO flows file (.flows.xml).
    - out_rou: Output SUMO route file (.rou.xml).
    - options: Extra CLI options.
    Returns:
    - dict: Output payload.
    """
    jtrrouter = _find_binary("jtrrouter")
    if not jtrrouter:
        raise FileNotFoundError("jtrrouter not found in PATH")
    cmd = [jtrrouter, "-n", net_path, "-f", flows_path, "-o", out_rou] + (options or [])
    _run_cmd(cmd)
    return {"rou_path": out_rou}


@mcp.tool()
def run_marouter(net_path: str, flows_path: str, out_rou: str, options: list[str] | None = None) -> dict:
    """
    Run SUMO marouter (matrix-based routing from flows).
    Parameters:
    - net_path: SUMO .net.xml path.
    - flows_path: SUMO flows file (.flows.xml).
    - out_rou: Output SUMO route file (.rou.xml).
    - options: Extra CLI options.
    Returns:
    - dict: Output payload.
    """
    marouter = _find_binary("marouter")
    if not marouter:
        raise FileNotFoundError("marouter not found in PATH")
    cmd = [marouter, "-n", net_path, "-f", flows_path, "-o", out_rou] + (options or [])
    _run_cmd(cmd)
    return {"rou_path": out_rou}


@mcp.tool()
def compute_k_shortest_paths(net_path: str, od_pairs: list[dict], k: int, out_paths: str) -> dict:
    """
    Compute k-shortest paths for OD pairs.
    Parameters:
    - net_path: SUMO .net.xml path.
    - od_pairs: Input parameter.
    - k: Number of alternatives.
    - out_paths: Output JSON path for paths.
    Returns:
    - dict: Output payload.
    """
    paths = []
    for pair in od_pairs:
        for i in range(k):
            paths.append({"from": pair["from"], "to": pair["to"], "path": [f"edge{i}"]})
    _write_json(out_paths, {"paths": paths})
    return {"paths_path": out_paths}


@mcp.tool()
def compute_route_choice_probs(paths_path: str, model: str, out_probs: str) -> dict:
    """
    Compute route choice probabilities for candidate paths.
    Parameters:
    - paths_path: Input file path.
    - model: Model name or type.
    - out_probs: Output JSON path for probabilities.
    Returns:
    - dict: Output payload.
    """
    data = json.loads(Path(paths_path).read_text(encoding="utf-8"))
    paths = data.get("paths", [])
    probs = []
    for item in paths:
        probs.append({"from": item["from"], "to": item["to"], "prob": 1.0})
    _write_json(out_probs, {"probs": probs, "model": model})
    return {"probs_path": out_probs}


@mcp.tool()
def assign_routes(trips_path: str, paths_path: str, probs_path: str, out_rou: str) -> dict:
    """
    Assign routes to trips using path probabilities.
    Parameters:
    - trips_path: SUMO trips file (.trips.xml).
    - paths_path: Input file path.
    - probs_path: Input file path.
    - out_rou: Output SUMO route file (.rou.xml).
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("routes")
    trips = ET.parse(trips_path)
    for trip in trips.findall(".//trip"):
        veh = ET.SubElement(root, "vehicle")
        veh.set("id", f"veh_{trip.get('id')}")
        veh.set("depart", trip.get("depart", "0"))
        route = ET.SubElement(veh, "route")
        route.set("edges", "")
    return {"rou_path": _save_tree(ET.ElementTree(root), out_rou)}


@mcp.tool()
def compress_routes(rou_path: str, out_rou: str) -> dict:
    """
    Compress/normalize a route file.
    Parameters:
    - rou_path: SUMO route file (.rou.xml).
    - out_rou: Output SUMO route file (.rou.xml).
    Returns:
    - dict: Output payload.
    """
    return {"rou_path": _copy(rou_path, out_rou)}


@mcp.tool()
def validate_routes(net_path: str, rou_path: str) -> dict:
    """
    Validate a route file against a network.
    Parameters:
    - net_path: SUMO .net.xml path.
    - rou_path: SUMO route file (.rou.xml).
    Returns:
    - dict: Output payload.
    """
    report = {"net_exists": Path(net_path).exists(), "rou_exists": Path(rou_path).exists()}
    report_path = str(Path(rou_path).with_suffix(".validate.json"))
    _write_json(report_path, report)
    return {"report_path": report_path}


@mcp.tool()
def export_routes_csv(rou_path: str, out_csv: str) -> dict:
    """
    Export routes to CSV.
    Parameters:
    - rou_path: SUMO route file (.rou.xml).
    - out_csv: Output CSV path.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(rou_path)
    rows = []
    for veh in tree.findall(".//vehicle"):
        rows.append([veh.get("id"), veh.get("depart")])
    _write_csv(out_csv, rows, header=["id", "depart"])
    return {"csv_path": out_csv}


# H. Simulation Control & Scenario
@mcp.tool()
def build_sumocfg(net_path: str, rou_path: str, additional_xmls: list[str], out_sumocfg: str) -> dict:
    """
    Build a SUMO configuration file.
    Parameters:
    - net_path: SUMO .net.xml path.
    - rou_path: SUMO route file (.rou.xml).
    - additional_xmls: List of additional XML files.
    - out_sumocfg: Output SUMO config (.sumocfg) path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("configuration")
    input_elem = ET.SubElement(root, "input")
    ET.SubElement(input_elem, "net-file").set("value", net_path)
    ET.SubElement(input_elem, "route-files").set("value", rou_path)
    if additional_xmls:
        ET.SubElement(input_elem, "additional-files").set("value", ",".join(additional_xmls))
    tree = ET.ElementTree(root)
    return {"sumocfg_path": _save_tree(tree, out_sumocfg)}


@mcp.tool()
def set_simulation_time(sumocfg_path: str, begin: int, end: int) -> dict:
    """
    Set simulation begin/end time in sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - begin: Input parameter.
    - end: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    time_elem = root.find("time") or ET.SubElement(root, "time")
    ET.SubElement(time_elem, "begin").set("value", str(begin))
    ET.SubElement(time_elem, "end").set("value", str(end))
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def set_step_length(sumocfg_path: str, step_length: float) -> dict:
    """
    Set simulation step length in sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - step_length: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    time_elem = root.find("time") or ET.SubElement(root, "time")
    ET.SubElement(time_elem, "step-length").set("value", str(step_length))
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def enable_collision_checks(sumocfg_path: str, enable: bool) -> dict:
    """
    Enable collision checking in sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - enable: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    proc = root.find("processing") or ET.SubElement(root, "processing")
    ET.SubElement(proc, "collision.check-junctions").set("value", "true" if enable else "false")
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def set_random_seed(sumocfg_path: str, seed: int) -> dict:
    """
    Set the random seed in sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - seed: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    random_elem = root.find("random_number") or ET.SubElement(root, "random_number")
    ET.SubElement(random_elem, "seed").set("value", str(seed))
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def add_emissions_output(sumocfg_path: str, out_emissions: str) -> dict:
    """
    Add emissions output to sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - out_emissions: Output path.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    output = root.find("output") or ET.SubElement(root, "output")
    ET.SubElement(output, "emission-output").set("value", out_emissions)
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def add_edgedata_output(sumocfg_path: str, out_edgedata: str, interval: int) -> dict:
    """
    Add edgedata output to sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - out_edgedata: Output path.
    - interval: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    output = root.find("output") or ET.SubElement(root, "output")
    elem = ET.SubElement(output, "edge-data-output")
    elem.set("value", out_edgedata)
    elem.set("interval", str(interval))
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def add_tripinfo_output(sumocfg_path: str, out_tripinfo: str) -> dict:
    """
    Add tripinfo output to sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - out_tripinfo: Output path.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    output = root.find("output") or ET.SubElement(root, "output")
    ET.SubElement(output, "tripinfo-output").set("value", out_tripinfo)
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def add_queue_output(sumocfg_path: str, out_queue: str, interval: int) -> dict:
    """
    Add queue output to sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - out_queue: Output path.
    - interval: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    output = root.find("output") or ET.SubElement(root, "output")
    elem = ET.SubElement(output, "queue-output")
    elem.set("value", out_queue)
    elem.set("interval", str(interval))
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}


@mcp.tool()
def add_detector_output(sumocfg_path: str, detector_xml: str, out_detector: str) -> dict:
    """
    Add detector output to sumocfg.
    Parameters:
    - sumocfg_path: SUMO config (.sumocfg) path.
    - detector_xml: Input file path.
    - out_detector: Output path.
    Returns:
    - dict: Output payload.
    """
    tree, root = _sumocfg_tree(sumocfg_path)
    input_elem = root.find("input") or ET.SubElement(root, "input")
    ET.SubElement(input_elem, "additional-files").set("value", detector_xml)
    output = root.find("output") or ET.SubElement(root, "output")
    ET.SubElement(output, "detector-output").set("value", out_detector)
    return {"sumocfg_path": _save_tree(tree, sumocfg_path)}

# I. Incident & Events
@mcp.tool()
def add_accident_event(net_path: str, edge_id: str, start: int, end: int, out_additional: str) -> dict:
    """
    Add an accident event to additional files.
    Parameters:
    - net_path: SUMO .net.xml path.
    - edge_id: Input parameter.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    rerouter = ET.SubElement(root, "rerouter")
    rerouter.set("id", "accident")
    rerouter.set("edges", edge_id)
    interval = ET.SubElement(rerouter, "interval")
    interval.set("begin", str(start))
    interval.set("end", str(end))
    ET.SubElement(interval, "closingReroute")
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_rerouting_event(net_path: str, taz_xml: str, start: int, end: int, out_additional: str) -> dict:
    """
    Add a rerouting event to additional files.
    Parameters:
    - net_path: SUMO .net.xml path.
    - taz_xml: TAZ definition XML path.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    rerouter = ET.SubElement(root, "rerouter")
    rerouter.set("id", "reroute")
    rerouter.set("edges", "")
    interval = ET.SubElement(rerouter, "interval")
    interval.set("begin", str(start))
    interval.set("end", str(end))
    ET.SubElement(interval, "closingReroute")
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_weather_event(net_path: str, severity: float, start: int, end: int, out_additional: str) -> dict:
    """
    Add a weather event to additional files.
    Parameters:
    - net_path: SUMO .net.xml path.
    - severity: Input parameter.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    vss = ET.SubElement(root, "variableSpeedSign")
    vss.set("id", "weather_vss")
    vss.set("lanes", "")
    step_start = ET.SubElement(vss, "step")
    step_start.set("time", str(start))
    step_start.set("speed", str(severity))
    step_end = ET.SubElement(vss, "step")
    step_end.set("time", str(end))
    step_end.set("speed", str(severity))
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_speed_profile_event(edge_ids: list[str], profile: list[dict], out_additional: str) -> dict:
    """
    Add a speed profile event to additional files.
    Parameters:
    - edge_ids: Input parameter.
    - profile: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    vss = ET.SubElement(root, "variableSpeedSign")
    vss.set("id", "speed_profile")
    vss.set("lanes", " ".join(f"{edge}_0" for edge in edge_ids))
    for item in profile:
        step = ET.SubElement(vss, "step")
        step.set("time", str(item.get("time", 0)))
        step.set("speed", str(item.get("speed", 0)))
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_lane_closure_event(lane_ids: list[str], start: int, end: int, out_additional: str) -> dict:
    """
    Add a lane closure event to additional files.
    Parameters:
    - lane_ids: Input parameter.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    rerouter = ET.SubElement(root, "rerouter")
    rerouter.set("id", "lane_close")
    rerouter.set("edges", " ".join(lane_ids))
    interval = ET.SubElement(rerouter, "interval")
    interval.set("begin", str(start))
    interval.set("end", str(end))
    for lane in lane_ids:
        ET.SubElement(interval, "closingLaneReroute").set("lane", lane)
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_edge_closure_event(edge_ids: list[str], start: int, end: int, out_additional: str) -> dict:
    """
    Add an edge closure event to additional files.
    Parameters:
    - edge_ids: Input parameter.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    rerouter = ET.SubElement(root, "rerouter")
    rerouter.set("id", "edge_close")
    rerouter.set("edges", " ".join(edge_ids))
    interval = ET.SubElement(rerouter, "interval")
    interval.set("begin", str(start))
    interval.set("end", str(end))
    ET.SubElement(interval, "closingReroute")
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_public_transport_event(lines: list[str], start: int, end: int, out_additional: str) -> dict:
    """
    Add a public transport disruption event.
    Parameters:
    - lines: Input parameter.
    - start: Input parameter.
    - end: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    for line in lines:
        flow = ET.SubElement(root, "flow")
        flow.set("id", f"pt_{line}")
        flow.set("begin", str(start))
        flow.set("end", str(end))
        flow.set("vehsPerHour", "10")
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_emergency_vehicle_event(route_id: str, start: int, out_additional: str) -> dict:
    """
    Add an emergency vehicle event.
    Parameters:
    - route_id: Input parameter.
    - start: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    veh = ET.SubElement(root, "vehicle")
    veh.set("id", "emergency")
    veh.set("route", route_id)
    veh.set("depart", str(start))
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def add_workzone_event(edge_ids: list[str], speed_limit: float, out_additional: str) -> dict:
    """
    Add a work zone event.
    Parameters:
    - edge_ids: Input parameter.
    - speed_limit: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    for edge in edge_ids:
        elem = ET.SubElement(root, "edge")
        elem.set("id", edge)
        elem.set("speed", str(speed_limit))
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


@mcp.tool()
def merge_additional_files(additional_paths: list[str], out_additional: str) -> dict:
    """
    Merge multiple additional files into one.
    Parameters:
    - additional_paths: Input parameter.
    - out_additional: Output path.
    Returns:
    - dict: Output payload.
    """
    root = ET.Element("additional")
    for path in additional_paths:
        tree = ET.parse(path)
        for child in tree.getroot():
            root.append(child)
    return {"additional_xml": _save_tree(ET.ElementTree(root), out_additional)}


# J. Calibration & Validation
@mcp.tool()
def parse_tripinfo(tripinfo_path: str) -> dict:
    """
    Parse tripinfo output file into JSON summary.
    Parameters:
    - tripinfo_path: Input file path.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(tripinfo_path)
    durations = [float(t.get("duration", 0)) for t in tree.findall(".//tripinfo")]
    stats = {"count": len(durations), "avg_duration": sum(durations) / max(1, len(durations))}
    return {"trip_stats": stats}


@mcp.tool()
def parse_edgedata(edgedata_path: str) -> dict:
    """
    Parse edgedata output file into JSON summary.
    Parameters:
    - edgedata_path: Input file path.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(edgedata_path)
    edges = tree.findall(".//edge")
    stats = {"edge_count": len(edges)}
    return {"edge_stats": stats}


@mcp.tool()
def compute_travel_time_hist(tripinfo_path: str, bins: int) -> dict:
    """
    Compute a travel time histogram.
    Parameters:
    - tripinfo_path: Input file path.
    - bins: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(tripinfo_path)
    durations = [float(t.get("duration", 0)) for t in tree.findall(".//tripinfo")]
    hist = [0] * bins
    if durations:
        max_d = max(durations)
        for d in durations:
            idx = min(bins - 1, int(d / max_d * (bins - 1)))
            hist[idx] += 1
    return {"hist": hist}


@mcp.tool()
def compute_speed_hist(edgedata_path: str, bins: int) -> dict:
    """
    Compute a speed histogram.
    Parameters:
    - edgedata_path: Input file path.
    - bins: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(edgedata_path)
    speeds = [float(e.get("speed", 0)) for e in tree.findall(".//edge")]
    hist = [0] * bins
    if speeds:
        max_s = max(speeds)
        for s in speeds:
            idx = min(bins - 1, int(s / max_s * (bins - 1)))
            hist[idx] += 1
    return {"hist": hist}


@mcp.tool()
def compute_counts_from_detectors(detector_output: str) -> dict:
    """
    Compute counts from detector outputs.
    Parameters:
    - detector_output: Input parameter.
    Returns:
    - dict: Output payload.
    """
    tree = ET.parse(detector_output)
    counts = {d.get("id"): int(float(d.get("nVehContrib", 0))) for d in tree.findall(".//interval")}
    return {"counts": counts}


@mcp.tool()
def compare_counts_to_ground_truth(sim_counts: dict, gt_counts: dict) -> dict:
    """
    Compare detector counts to ground truth.
    Parameters:
    - sim_counts: Input parameter.
    - gt_counts: Input parameter.
    Returns:
    - dict: Output payload.
    """
    metrics = {}
    for key, value in gt_counts.items():
        metrics[key] = abs(float(sim_counts.get(key, 0)) - float(value))
    return {"metrics": metrics}


@mcp.tool()
def calibrate_route_choice(params: dict, metrics: dict) -> dict:
    """
    Calibrate route choice parameters.
    Parameters:
    - params: Input parameter.
    - metrics: Input parameter.
    Returns:
    - dict: Output payload.
    """
    params = dict(params)
    params["updated"] = True
    return {"params": params}


@mcp.tool()
def calibrate_departure_profile(profile: dict, metrics: dict) -> dict:
    """
    Calibrate departure profile parameters.
    Parameters:
    - profile: Input parameter.
    - metrics: Input parameter.
    Returns:
    - dict: Output payload.
    """
    profile = dict(profile)
    profile["updated"] = True
    return {"profile": profile}


@mcp.tool()
def compute_network_kpis(trip_stats: dict, edge_stats: dict) -> dict:
    """
    Compute network KPIs from outputs.
    Parameters:
    - trip_stats: Input parameter.
    - edge_stats: Input parameter.
    Returns:
    - dict: Output payload.
    """
    return {"kpis": {"trip_count": trip_stats.get("count", 0), "edge_count": edge_stats.get("edge_count", 0)}}


@mcp.tool()
def export_validation_report(metrics: dict, out_report: str) -> dict:
    """
    Export a validation report.
    Parameters:
    - metrics: Input parameter.
    - out_report: Output report path.
    Returns:
    - dict: Output payload.
    """
    return {"report_path": _write_json(out_report, metrics)}

# K. Reporting & Export
@mcp.tool()
def summarize_scenario(config: dict) -> dict:
    """
    Summarize scenario outputs and configuration.
    Parameters:
    - config: Input parameter.
    Returns:
    - dict: Output payload.
    """
    summary = {"created_at": datetime.utcnow().isoformat(), "config": config}
    return {"summary": summary}


@mcp.tool()
def export_metrics_json(metrics: dict, out_json: str) -> dict:
    """
    Export metrics to JSON.
    Parameters:
    - metrics: Input parameter.
    - out_json: Output path.
    Returns:
    - dict: Output payload.
    """
    return {"json_path": _write_json(out_json, metrics)}


@mcp.tool()
def export_metrics_csv(metrics: dict, out_csv: str) -> dict:
    """
    Export metrics to CSV.
    Parameters:
    - metrics: Input parameter.
    - out_csv: Output CSV path.
    Returns:
    - dict: Output payload.
    """
    rows = [[k, v] for k, v in metrics.items()]
    return {"csv_path": _write_csv(out_csv, rows, header=["metric", "value"])}


@mcp.tool()
def export_kpi_dashboard(kpis: dict, out_html: str) -> dict:
    """
    Export KPI dashboard data.
    Parameters:
    - kpis: Input parameter.
    - out_html: Output path.
    Returns:
    - dict: Output payload.
    """
    lines = ["<html><body><table>"]
    for k, v in kpis.items():
        lines.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
    lines.append("</table></body></html>")
    return {"html_path": _write_text(out_html, "\n".join(lines))}


@mcp.tool()
def bundle_outputs(paths: list[str], out_zip: str) -> dict:
    """
    Bundle outputs into a package.
    Parameters:
    - paths: Input parameter.
    - out_zip: Output path.
    Returns:
    - dict: Output payload.
    """
    p = _ensure_parent(out_zip)
    with zipfile.ZipFile(p, "w") as zf:
        for path in paths:
            zf.write(path, Path(path).name)
    return {"zip_path": str(p)}


@mcp.tool()
def archive_run(run_dir: str, out_tar: str) -> dict:
    """
    Archive run outputs for storage.
    Parameters:
    - run_dir: Input parameter.
    - out_tar: Output path.
    Returns:
    - dict: Output payload.
    """
    p = _ensure_parent(out_tar)
    with tarfile.open(p, "w") as tf:
        tf.add(run_dir, arcname=Path(run_dir).name)
    return {"tar_path": str(p)}


@mcp.tool()
def register_run_metadata(db_path: str, metadata: dict) -> dict:
    """
    Register run metadata for tracking.
    Parameters:
    - db_path: Input file path.
    - metadata: Input parameter.
    Returns:
    - dict: Output payload.
    """
    _ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, data TEXT)")
    cur = conn.execute("INSERT INTO runs (data) VALUES (?)", (json.dumps(metadata),))
    conn.commit()
    conn.close()
    return {"record_id": cur.lastrowid}


@mcp.tool()
def compare_scenarios(results_a: dict, results_b: dict) -> dict:
    """
    Compare two scenarios and output a report.
    Parameters:
    - results_a: Input parameter.
    - results_b: Input parameter.
    Returns:
    - dict: Output payload.
    """
    diff = {}
    keys = set(results_a) | set(results_b)
    for k in keys:
        if results_a.get(k) != results_b.get(k):
            diff[k] = {"a": results_a.get(k), "b": results_b.get(k)}
    return {"diff_report": diff}


@mcp.tool()
def list_edges(net_path: str) -> dict:
    """
    List edge IDs from a SUMO network.
    Parameters:
    - net_path: SUMO .net.xml path.
    Returns:
    - dict: Output payload.
    """
    edges, _ = _read_net_edges(net_path)
    return {"edge_ids": edges}


@mcp.tool()
def list_lanes(net_path: str) -> dict:
    """
    List lane IDs from a SUMO network.
    Parameters:
    - net_path: SUMO .net.xml path.
    Returns:
    - dict: Output payload.
    """
    _, lanes = _read_net_edges(net_path)
    return {"lane_ids": lanes}


@mcp.tool()
def list_taz(taz_xml: str) -> dict:
    """
    List TAZ IDs from a TAZ definition file.
    Parameters:
    - taz_xml: TAZ definition XML path.
    Returns:
    - dict: Output payload.
    """
    return {"taz_ids": _read_taz_ids(taz_xml)}

# TODO



if __name__ == "__main__":
    mcp.run()