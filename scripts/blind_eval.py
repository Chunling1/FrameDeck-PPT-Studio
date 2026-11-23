"""Mask the products of repeated independent runs, then summarize human votes."""
import argparse
import csv
import json
from pathlib import Path
import random
import shutil
from statistics import mean

GENRES={"科研汇报","领导简报","产品介绍"}
METRICS=["clarity","accuracy","hierarchy","consistency","editability"]


def prepare(source,out):
    rows=list(csv.DictReader(source.open(encoding="utf-8-sig")))
    expected={(g,str(i),v) for g in GENRES for i in range(1,4) for v in ("skill","studio")}
    if {(r["genre"],r["run"],r["method"]) for r in rows}!=expected or len(rows)!=18:
        raise ValueError("需三种题材、各三次独立运行，旧 Skill 与新程序均需交付")
    for r in rows:
        if not (source.parent/r["pptx"]).is_file():raise ValueError("缺少 PPTX："+r["pptx"])
    out.mkdir(parents=True,exist_ok=False);random.SystemRandom().shuffle(rows)
    votes=[]
    for i,r in enumerate(rows,1):
        tag=f"deck-{i:02}";r["blind_id"]=tag;shutil.copyfile(source.parent/r["pptx"],out/(tag+".pptx"))
        votes.append({"blind_id":tag,**{m:"" for m in METRICS},"reject":"","notes":""})
    with (out/"votes.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=votes[0]);w.writeheader();w.writerows(votes)
    (out.parent/(out.name+"-private-key.json")).write_text(json.dumps(rows,ensure_ascii=False),encoding="utf8")


def score(key,votes):
    mapping={r["blind_id"]:r for r in json.loads(key.read_text(encoding="utf8"))}
    rows=list(csv.DictReader(votes.open(encoding="utf-8-sig")))
    if len(rows)!=len(mapping) or {r["blind_id"] for r in rows}!=set(mapping):raise ValueError("评分不完整")
    results={"skill":[],"studio":[]}
    for r in rows:
        vals=[int(r[m]) for m in METRICS]
        if not all(1<=v<=5 for v in vals) or r["reject"] not in ("0","1"):raise ValueError("评分为 1–5，退稿为 0/1")
        meta=mapping[r["blind_id"]];results[meta["method"]].append((mean(vals),int(r["reject"]),float(meta["cost"]),float(meta["minutes"])))
    for method,records in results.items():
        means,rejects,costs,mins=zip(*records)
        print(method,json.dumps(dict(mean=mean(means),worst=min(means),rejects=sum(rejects),cost=sum(costs),minutes=sum(mins))))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["prepare","score"]);p.add_argument("first",type=Path);p.add_argument("second",type=Path);a=p.parse_args()
    (prepare if a.mode=="prepare" else score)(a.first,a.second)
