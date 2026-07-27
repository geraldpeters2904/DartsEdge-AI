from __future__ import annotations

import argparse
from pathlib import Path

from app.collector.folder_preview import (
    CollectorFolderPreviewService,
)


def preview_command(args):
    service = CollectorFolderPreviewService()

    preview = service.preview(
        folder=Path(args.folder),
        provider=args.provider,
    )

    print()
    print("=" * 50)
    print("DartsEdge Collector Preview")
    print("=" * 50)
    print()

    print(f"Folder   : {preview.folder}")
    print(f"Provider : {preview.provider}")
    print()

    print("Files Found")
    print("-" * 20)

    for entity_type, path in preview.discovered_files.items():
        print(f"✓ {path.name}")

    if preview.missing_files:
        print()
        print("Missing")
        print("-" * 20)
        for filename in preview.missing_files:
            print(f"• {filename}")

    print()
    print("Import Summary")
    print("-" * 20)

    totals = preview.to_dict()["totals"]

    print(f"Received   : {totals['received']}")
    print(f"Valid      : {totals['valid']}")
    print(f"Rejected   : {totals['rejected']}")
    print(f"Duplicates : {totals['duplicates']}")
    print()

    print(f"Quality Score : {preview.session.quality_score:.1f}%")
    print()

    print(
        "READY TO COMMIT"
        if preview.ready_to_commit
        else "NOT READY"
    )


def main():
    parser = argparse.ArgumentParser(
        prog="dartsedge-collector"
    )

    sub = parser.add_subparsers(dest="command")

    preview = sub.add_parser("preview")
    preview.add_argument("--folder", required=True)
    preview.add_argument("--provider", required=True)
    preview.set_defaults(func=preview_command)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
