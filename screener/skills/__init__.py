"""The skill library. Every .py file in this folder (not starting with _) is a skill.

To add a skill: copy _template.py, rename it, fill in find(). New skills start in
PRACTICE mode - the Guard bot only lets them go live once they prove themselves.
"""
import importlib
import json
import os
import pkgutil

from .. import config as C


def load_skills():
    tuned = {}
    if os.path.exists(C.TUNED_FILE):
        tuned = json.load(open(C.TUNED_FILE))
    skills = []
    for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if m.name.startswith("_"):
            continue
        sk = dict(importlib.import_module(f"{__name__}.{m.name}").SKILL)
        sk["params"] = {**sk["params"], **tuned.get(sk["name"], {})}
        skills.append(sk)
    return skills
