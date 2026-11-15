"""Developer-only profile import and comparison CLI.

Scientific data acquisition must be conducted through reviewed batch operations.
"""
from pathlib import Path
import argparse,json
from app.pipeline.core import import_profiles_json,search

def main():
    parser=argparse.ArgumentParser(description="PLANETREX manual research operations")
    actions=parser.add_subparsers(dest="command",required=True)
    imported=actions.add_parser("import");imported.add_argument("path")
    screened=actions.add_parser("compare");screened.add_argument("reference_id");screened.add_argument("--limit",type=int,default=50)
    args=parser.parse_args()
    if args.command=="import":print("Imported",import_profiles_json(Path(args.path)),"sourced profiles")
    elif args.command=="compare":print(json.dumps(search(args.reference_id,limit=args.limit),indent=2))

if __name__=="__main__":main()
