"""Run the whole pipeline: extract -> transform/validate -> load -> EDA.

    python run_all.py                 # everything (needs internet)
    python run_all.py --skip-extract  # reuse the JSON already in raw/
"""
import argparse

import eda
import export_web_data
import extract
import load
import transform


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--skip-extract", action="store_true",
                   help="use existing raw/*.json instead of calling the APIs")
    args = p.parse_args()

    if not args.skip_extract:
        print("=== 1/5 EXTRACT ===")
        extract.main()
    print("\n=== 2/5 TRANSFORM + VALIDATE ===")
    transform.main()
    print("\n=== 3/5 LOAD ===")
    load.main()
    print("\n=== 4/5 EDA ===")
    eda.main()
    print("\n=== 5/5 WEBSITE DATA ===")
    export_web_data.main()


if __name__ == "__main__":
    main()
