"""Read NFTR character maps and advances without modifying game assets.

Usage: python -m ie123kit._legado.nftr_metrics path/to/FONT12.NFTR
NFTR map keys in the IE1 assets are Shift-JIS codes, not Unicode code points.
"""
import json
import sys
from pathlib import Path

from ie123kit.nucleo.fuentes.nftr import *  # noqa: F401,F403


def main():
    metrics = read_metrics(Path(sys.argv[1]).read_bytes())
    result = {}
    for ch in 'aimntW?':
        wide = chr(ord(ch)+0xfee0)
        code = int.from_bytes(wide.encode('shift_jis'), 'big')
        result[ch] = {'ascii': metrics.get(ord(ch)), 'fullwidth': metrics.get(code)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
