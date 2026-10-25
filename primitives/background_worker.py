"""One bounded search slice; only the server may commit its result."""
import json
import os
from pathlib import Path
import sys

from .dataset import Dataset
from .evolution import SearchConfig
from .library import Library, write_json
from .runner import search


def main():
    if os.name != "nt":
        os.nice(15)
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = search(Dataset.from_dict(job["dataset"]), SearchConfig(**job["config"]),
                    Library(job["library"]), save=False, time_budget=0.6)
    write_json(Path(sys.argv[2]), result)


if __name__ == "__main__":
    main()
