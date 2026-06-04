"""PDF post-processor for Wuolah free downloads.

Removes ad elements by detecting hyperlinks that point to tracking/ad domains
(e.g. track.wlh.es) and redacting their bounding rectangles.

Operates on local files only; does not interact with Wuolah servers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Domains / patterns that identify ad/tracking links in Wuolah PDFs
_AD_PATTERNS = {
    "track.wlh.es",
    "utm_source=wuolah",
    "utm_medium=pdf",
    "utm_campaign=pdf-download",
    "tab=turbo",
    "listName=notes-ad",
    "adS=",
    "adU=",
    "adC=",
}


def _is_ad_link(uri: str | None) -> bool:
    if not uri:
        return False
    uri_l = uri.lower()
    return any(pat.lower() in uri_l for pat in _AD_PATTERNS)


def inspect_pdf(path: str | Path) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    results = []
    for i in range(len(doc)):
        page = doc[i]
        links = page.get_links()
        ad_links = [l for l in links if _is_ad_link(l.get("uri"))]
        normal = len(links) - len(ad_links)
        results.append({
            "page": i + 1,
            "links": len(links),
            "ad_links": len(ad_links),
            "normal_links": normal,
            "ad_uris": [l.get("uri", "") for l in ad_links][:3],
        })
    doc.close()
    return results


def clean_pdf(src: str | Path, dst: str | Path, *, dry_run: bool = False) -> dict:
    import fitz
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise FileNotFoundError(src)

    doc = fitz.open(src)
    redacted = []

    for i in range(len(doc)):
        page = doc[i]
        ad_rects = []
        for link in page.get_links():
            if _is_ad_link(link.get("uri")):
                rect = fitz.Rect(link.get("from"))
                if rect.is_empty or rect.is_infinite:
                    continue
                page.delete_link(link)
                # Only redact small rectangles (banners); large ones are likely
                # real content images that happen to have a tracking link on top.
                page_area = page.rect.width * page.rect.height
                link_area = rect.width * rect.height
                if link_area < page_area * 0.30:
                    page.add_redact_annot(rect + (-2, -2, 2, 2), fill=(1, 1, 1))
                    ad_rects.append(rect)

        if dry_run:
            if ad_rects:
                redacted.append({"page": i + 1, "rects": len(ad_rects)})
            continue

        for rect in ad_rects:
            page.add_redact_annot(rect + (-2, -2, 2, 2), fill=(1, 1, 1))
        if ad_rects:
            page.apply_redactions()
            redacted.append({"page": i + 1, "rects": len(ad_rects)})

    result = {
        "src": str(src),
        "dst": str(dst),
        "original_pages": len(doc),
        "redacted": redacted,
        "dry_run": dry_run,
    }

    if dry_run:
        doc.close()
        return result

    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dst)
    doc.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean Wuolah ad/tracking elements from a PDF")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Show per-page link analysis")
    inspect.add_argument("pdf", help="Input PDF path")
    inspect.add_argument("--json", action="store_true", help="Output as JSON")

    clean = sub.add_parser("clean", help="Redact ad-link elements and write cleaned PDF")
    clean.add_argument("pdf", help="Input PDF path")
    clean.add_argument("-o", "--output", help="Output path (default: <name>.cleaned.pdf)")
    clean.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")

    args = parser.parse_args(argv)

    if args.command == "inspect":
        results = inspect_pdf(args.pdf)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for r in results:
                flag = "[AD]" if r["ad_links"] else "[OK]"
                print(f"Page {r['page']:>2} {flag}  links={r['links']} ad={r['ad_links']} normal={r['normal_links']}")
        return 0

    if args.command == "clean":
        src = Path(args.pdf)
        dst = Path(args.output) if args.output else src.with_suffix(".cleaned.pdf")
        result = clean_pdf(src, dst, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
