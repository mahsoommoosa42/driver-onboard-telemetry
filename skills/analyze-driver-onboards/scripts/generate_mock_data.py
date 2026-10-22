#!/usr/bin/env python3
"""Generate explicitly synthetic, export-shaped CSVs; not files produced by vendor software."""
import bisect
import csv
import json
import math
from pathlib import Path

DEST = Path(__file__).resolve().parents[1]/"assets/mock-data"
DIST = [0, 500, 1000, 1500, 2000]
REF = [0, 20, 45, 70, 100]
CMP = [0, 21, 44, 72, 103]

def position(t, anchors):
    i = min(bisect.bisect_right(anchors,t)-1, len(anchors)-2)
    v = (DIST[i+1]-DIST[i])/(anchors[i+1]-anchors[i])
    return DIST[i]+(t-anchors[i])*v, v

def generate(dest=DEST):
    dest.mkdir(parents=True, exist_ok=True)
    for fmt, name, times, hz in (
        ("motec-i2-csv","motec_reference",REF,20),
        ("motec-i2-csv","motec_comparison",CMP,20),
        ("racechrono-csv","racechrono_reference",REF,1),
        ("racechrono-csv","racechrono_comparison",CMP,1)):
        motec = fmt == "motec-i2-csv"
        meta = [["Format","MoTeC CSV File" if motec else "3"],
                ["Source","SYNTHETIC export-shaped fixture; not vendor-generated"],
                ["Session","Mock circuit; not a real driver or track"],[]]
        header = ["Time","Distance","Ground Speed","Throttle Pos","Brake Pressure","Gear"] if motec else [
            "timestamp","elapsed time","distance","speed","latitude","longitude"]
        units = ["s","m","km/h","%","bar","count"] if motec else ["s","s","m","m/s","deg","deg"]
        rows = meta+[header,units]
        if not motec:
            rows += [["","","","GPS","GPS","GPS"],["","","","","",""]]
        data_row = len(rows)
        for step in range(int(times[-1]*hz)+1):
            t = step/hz
            dist, speed = position(t,times)
            braking = max(0,1-abs(t-17)/2)
            if motec:
                values = [t,dist,speed*3.6,100*(1-braking),60*braking,4]
            else:
                angle = 2*math.pi*dist/2000
                values = [1700000000+t,t,dist,speed,10+.003*math.sin(angle),20+.003*math.cos(angle)]
            rows.append([f"{v:.9f}" for v in values])
        with (dest/(name+".csv")).open("w",newline="") as f:
            csv.writer(f,quoting=csv.QUOTE_ALL).writerows(rows)
        indices = {"time_s":0,"distance_m":1,"speed_mps":2,"throttle_pct":3,"brake_pressure_bar":4,"gear":5} if motec else {
            "time_s":1,"distance_m":2,"speed_mps":3,"latitude_deg":4,"longitude_deg":5}
        mapping={"format":fmt,"synthetic":True,"scope":"one-contiguous-lap",
                 "source_time_bounds_s":[0,times[-1]],"header_row":4,"units_row":5,"data_row":data_row,
                 "channels":{k:{"column":i,"name":header[i],"unit":units[i]} for k,i in indices.items()}}
        (dest/(name+".mapping.json")).write_text(json.dumps(mapping,indent=2)+"\n")
    (dest/"ground-truth.json").write_text(json.dumps({
        "synthetic":True,"provenance":"Generated locally by generate_mock_data.py; no vendor export or real driving data.",
        "distance_m":DIST,"reference_elapsed_s":REF,"comparison_elapsed_s":CMP,
        "segment_loss_s":[1,-2,3,1],"total_loss_s":3,
        "alignment":"Both fixtures are generated against the same exact track coordinate.",
        "limitation":"Export-shaped mocks test declared mappings and analysis math, not native .ld/.rcz or every vendor CSV revision."
    },indent=2)+"\n")

if __name__ == "__main__":
    generate()
    print(DEST)
