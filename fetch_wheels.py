# -*- coding: utf-8 -*-
"""在 pip 被代理拦截时，直接用 urllib 抓 wheel 到本地目录。"""
import os
import re
import sys
import urllib.parse
import urllib.request

INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple/{name}/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wheels")

OK_TAGS = (
    "cp313-cp313-win_amd64",
    "cp313-abi3-win_amd64",
    "py3-none-any",
    "py2.py3-none-any",
    "py3-none-win_amd64",
)


def ver_key(v):
    parts = re.split(r"[.\-_]", v)
    out = []
    for p in parts:
        out.append((0, int(p)) if p.isdigit() else (1, p))
    return out


def pick_wheels(name):
    url = INDEX.format(name=name)
    req = urllib.request.Request(url, headers={"User-Agent": "pip/24.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

    cands = []
    for m in re.finditer(r'href="([^"]+\.whl)(?:#[^"]*)?"', html):
        link = m.group(1)
        fname = link.rsplit("/", 1)[-1]
        if not fname.lower().startswith(name.replace("-", "_").lower().replace(".", "_")):
            if not fname.lower().startswith(name.lower()):
                continue
        stem = fname[:-4]
        bits = stem.split("-")
        if len(bits) < 3:
            continue
        version = bits[1]
        tag = "-".join(bits[2:])
        if any(t in tag for t in OK_TAGS):
            cands.append((ver_key(version), version, link, fname))
    if not cands:
        print(f"  !! {name}: 没有匹配的 wheel")
        return []
    cands.sort(key=lambda x: x[0])
    best_ver = cands[-1][1]
    return [(v, l, f) for _, v, l, f in cands if v == best_ver]


def main(names):
    os.makedirs(OUT, exist_ok=True)
    for name in names:
        for ver, link, fname in pick_wheels(name):
            dest = os.path.join(OUT, fname)
            if os.path.exists(dest):
                print(f"  = {fname}（已存在）")
                continue
            link = urllib.parse.urljoin(INDEX.format(name=name), link)
            print(f"  + {fname}  ({ver})")
            req = urllib.request.Request(link, headers={"User-Agent": "pip/24.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                f.write(r.read())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
