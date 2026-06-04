from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .client import WuolahClient
from .crawler import CATEGORY_VALUES, CrawlFilters, WuolahCrawler
from .storage import Storage


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path).expanduser()
    return json.loads(p.read_text(encoding='utf-8'))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Wuolah metadata scraper')
    parser.add_argument('--config', default='config.json', help='Path to config JSON')

    sub = parser.add_subparsers(dest='command', required=True)

    auth_check = sub.add_parser('auth-check', help='Validate configured auth material against /v2/me')
    auth_check.add_argument('--config', dest='config_override')

    official_download = sub.add_parser('official-download', help='Use Wuolah official /v2/download flow with authenticated session')
    official_download.add_argument('--config', dest='config_override')
    official_download.add_argument('--document-id', type=int, action='append', dest='document_ids', help='Document ID to download; can be repeated')
    official_download.add_argument('--results-json', help='Path to a search results JSON file with a top-level results[] list')
    official_download.add_argument('--output-dir', help='Destination directory for downloaded files')
    official_download.add_argument('--with-coins', action='store_true', help='Request noAdsWithCoins=true in the official endpoint')
    official_download.add_argument('--referral-code')
    official_download.add_argument('--limit', type=int, default=0, help='Optional max number of files to process from results-json (0 = all)')
    official_download.add_argument('--force', action='store_true', help='Overwrite existing files instead of skipping them')

    universities = sub.add_parser('universities', help='List public universities discovered from homepage')
    universities.add_argument('--config', dest='config_override')

    crawl = sub.add_parser('crawl', help='Crawl Wuolah metadata with filters')
    crawl.add_argument('--config', dest='config_override')
    crawl.add_argument('--university-slug')
    crawl.add_argument('--community-slug')
    crawl.add_argument('--subject-slug')
    crawl.add_argument('--study-type-slug')
    crawl.add_argument('--center-slug')
    crawl.add_argument('--course', type=int)
    crawl.add_argument('--category', choices=CATEGORY_VALUES)
    crawl.add_argument('--creator-user-id', type=int)
    crawl.add_argument('--keyword')
    crawl.add_argument('--sort', default='-numDownloads')
    crawl.add_argument('--page-size', type=int, default=100)
    crawl.add_argument('--max-pages', type=int, default=0, help='0 = no explicit page limit')
    crawl.add_argument('--no-document-details', action='store_true')
    crawl.add_argument('--all-universities', action='store_true')

    db_counts = sub.add_parser('db-counts', help='Show sqlite table counts')
    db_counts.add_argument('--config', dest='config_override')

    clean_pdf = sub.add_parser('clean-pdf', help='Remove Wuolah ad/filler pages from a downloaded PDF')
    clean_pdf.add_argument('pdf', help='Input PDF path')
    clean_pdf.add_argument('-o', '--output', help='Output path (default: <name>.cleaned.pdf)')
    clean_pdf.add_argument('--dry-run', action='store_true', help='Show analysis without writing')
    clean_pdf.add_argument('--aggressive', action='store_true', help='Also remove copyright-only filler pages')
    return parser


def make_client_and_storage(config_path: str | Path) -> tuple[dict[str, Any], WuolahClient, Storage]:
    project_dir = Path(config_path).expanduser().resolve().parent
    config = load_config(config_path)
    storage = Storage(project_dir)
    client = WuolahClient(
        base_url=str(config.get('base_url') or 'https://wuolah.com'),
        api_base_url=str(config.get('api_base_url') or 'https://api.wuolah.com'),
        auth_cfg=config.get('auth') or {},
        crawl_cfg=config.get('crawl') or {},
        raw_dir=storage.raw_dir,
    )
    return config, client, storage


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', '_', (name or '').strip())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')
    return cleaned or 'download.bin'


def _get_or_create_machine_id(outputs_dir: Path) -> str:
    machine_id_path = outputs_dir / 'machine_id.txt'
    if machine_id_path.exists():
        value = machine_id_path.read_text(encoding='utf-8', errors='replace').strip()
        if value:
            return value
    value = str(uuid.uuid4())
    machine_id_path.write_text(value, encoding='utf-8')
    return value


def _load_download_targets(args: argparse.Namespace) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[int] = set()

    for document_id in args.document_ids or []:
        if document_id in seen:
            continue
        seen.add(document_id)
        targets.append({'id': document_id})

    if args.results_json:
        payload = json.loads(Path(args.results_json).expanduser().read_text(encoding='utf-8'))
        results = payload.get('results', []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            raise ValueError('results-json must contain a top-level results[] list')
        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                document_id = int(item['id'])
            except Exception:
                continue
            if document_id in seen:
                continue
            seen.add(document_id)
            target = {'id': document_id}
            if item.get('name'):
                target['name'] = str(item['name'])
            if item.get('url'):
                target['url'] = str(item['url'])
            targets.append(target)

    if args.limit and args.limit > 0:
        targets = targets[:args.limit]
    return targets


def cmd_universities(config_path: str | Path) -> int:
    _, client, storage = make_client_and_storage(config_path)
    try:
        universities = client.list_universities()
        for item in universities:
            print(f"{item.get('id')}\t{item.get('slug')}\t{item.get('name')}")
        return 0
    finally:
        storage.close()


def cmd_db_counts(config_path: str | Path) -> int:
    _, _, storage = make_client_and_storage(config_path)
    try:
        print(json.dumps(storage.counts(), ensure_ascii=False, indent=2))
        return 0
    finally:
        storage.close()


def cmd_auth_check(config_path: str | Path) -> int:
    config, client, storage = make_client_and_storage(config_path)
    try:
        auth_cfg = config.get('auth') or {}
        try:
            me = client.get_me()
        except Exception as exc:
            print(json.dumps({
                'ok': False,
                'error': str(exc),
                'auth_material': {
                    'cookie_header_configured': bool(str(auth_cfg.get('cookie_header') or '').strip()),
                    'cookie_file_configured': bool(str(auth_cfg.get('cookie_file') or '').strip()),
                    'cookie_file': str(auth_cfg.get('cookie_file') or ''),
                    'access_token_configured': bool(str(auth_cfg.get('access_token') or '').strip()),
                    'refresh_token_configured': bool(str(auth_cfg.get('refresh_token') or '').strip()),
                    'session_cookie_count': len(client.auth_material.cookies),
                },
            }, ensure_ascii=False, indent=2))
            return 1

        print(json.dumps({
            'ok': True,
            'auth_material': {
                'cookie_header_configured': bool(str(auth_cfg.get('cookie_header') or '').strip()),
                'cookie_file_configured': bool(str(auth_cfg.get('cookie_file') or '').strip()),
                'cookie_file': str(auth_cfg.get('cookie_file') or ''),
                'access_token_configured': bool(str(auth_cfg.get('access_token') or '').strip()),
                'refresh_token_configured': bool(str(auth_cfg.get('refresh_token') or '').strip()),
                'session_cookie_count': len(client.auth_material.cookies),
            },
            'me': me,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        storage.close()


def cmd_official_download(args: argparse.Namespace, config_path: str | Path) -> int:
    config, client, storage = make_client_and_storage(config_path)
    try:
        targets = _load_download_targets(args)
        if not targets:
            raise ValueError('Provide at least one --document-id or a --results-json file with results[]')

        auth_cfg = config.get('auth') or {}
        try:
            me = client.get_me()
        except Exception as exc:
            print(json.dumps({
                'ok': False,
                'error': str(exc),
                'auth_material': {
                    'cookie_header_configured': bool(str(auth_cfg.get('cookie_header') or '').strip()),
                    'cookie_file_configured': bool(str(auth_cfg.get('cookie_file') or '').strip()),
                    'cookie_file': str(auth_cfg.get('cookie_file') or ''),
                    'access_token_configured': bool(str(auth_cfg.get('access_token') or '').strip()),
                    'refresh_token_configured': bool(str(auth_cfg.get('refresh_token') or '').strip()),
                    'session_cookie_count': len(client.auth_material.cookies),
                },
            }, ensure_ascii=False, indent=2))
            return 1

        output_dir = Path(args.output_dir).expanduser() if args.output_dir else storage.outputs_dir / 'official-downloads'
        output_dir.mkdir(parents=True, exist_ok=True)
        machine_id = _get_or_create_machine_id(storage.outputs_dir)

        summary: dict[str, Any] = {
            'ok': True,
            'user_id': me.get('id') if isinstance(me, dict) else None,
            'machine_id_file': str(storage.outputs_dir / 'machine_id.txt'),
            'output_dir': str(output_dir),
            'with_coins': bool(args.with_coins),
            'requested': len(targets),
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
            'files': [],
        }

        for target in targets:
            document_id = int(target['id'])
            entry: dict[str, Any] = {'id': document_id}
            try:
                document = client.get_document(document_id)
                name = str(
                    target.get('name')
                    or document.get('name')
                    or document.get('uploadName')
                    or f'{document_id}.bin'
                )
                entry['name'] = name
                output_path = output_dir / _sanitize_filename(name)
                entry['path'] = str(output_path)

                if output_path.exists() and not args.force:
                    entry['status'] = 'skipped_exists'
                    entry['size'] = output_path.stat().st_size
                    summary['skipped'] += 1
                    summary['files'].append(entry)
                    continue

                download_payload = client.request_official_download(
                    document_id,
                    machine_id=machine_id,
                    with_coins=bool(args.with_coins),
                    referral_code=args.referral_code,
                )
                entry['download_payload'] = download_payload
                url = str((download_payload or {}).get('url') or '').strip()
                if not url:
                    raise RuntimeError(f'Official download response missing url: {download_payload!r}')
                client.download_url_to_file(url, output_path)
                entry['status'] = 'downloaded'
                entry['size'] = output_path.stat().st_size
                summary['downloaded'] += 1
            except Exception as exc:
                entry['status'] = 'failed'
                entry['error'] = str(exc)
                response = getattr(exc, 'response', None)
                if response is not None:
                    try:
                        entry['response_status'] = response.status_code
                        entry['response_body'] = response.text[:1000]
                    except Exception:
                        pass
                summary['failed'] += 1
                summary['ok'] = False
            summary['files'].append(entry)

        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary['failed'] == 0 else 1
    finally:
        storage.close()


def cmd_crawl(args: argparse.Namespace, config_path: str | Path) -> int:
    config, client, storage = make_client_and_storage(config_path)
    try:
        filters = CrawlFilters(
            university_slug=args.university_slug,
            community_slug=args.community_slug,
            subject_slug=args.subject_slug,
            study_type_slug=args.study_type_slug,
            center_slug=args.center_slug,
            course=args.course,
            category=args.category,
            creator_user_id=args.creator_user_id,
            keyword=args.keyword,
            sort=args.sort,
            page_size=args.page_size,
            max_pages=args.max_pages,
            fetch_document_details=not args.no_document_details and bool((config.get('crawl') or {}).get('fetch_document_details', True)),
            all_universities=args.all_universities,
        )
        crawler = WuolahCrawler(client, storage, config.get('crawl') or {})
        run = storage.start_run(asdict(filters))
        summary = crawler.crawl(filters)
        summary['run_id'] = run.run_id
        storage.finish_run(run, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nDB: {storage.db_path}")
        print(f"Raw pages: {storage.raw_dir}")
        print(f"Summary: {storage.outputs_dir / 'last_run_summary.json'}")
        return 0
    finally:
        storage.close()


def cmd_clean_pdf(args: argparse.Namespace) -> int:
    from .pdf_cleaner import clean_pdf, inspect_pdf
    from pathlib import Path

    src = Path(args.pdf)
    if not src.exists():
        print(json.dumps({"ok": False, "error": f"File not found: {src}"}, ensure_ascii=False))
        return 1

    if args.dry_run:
        results = inspect_pdf(src, aggressive=args.aggressive)
        for r in results:
            flag = "[AD]" if r["is_ad"] else "[OK]"
            print(f"Page {r['page']:>2} {flag} ({r['reason']:<24}) chars={r['chars']:>4} | {r['snippet'][:65]}")
        return 0

    dst = Path(args.output) if args.output else src.with_suffix(".cleaned.pdf")
    result = clean_pdf(src, dst, aggressive=args.aggressive, dry_run=False)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


def cmd_clean_pdf(args: argparse.Namespace) -> int:
    from .pdf_cleaner import clean_pdf, inspect_pdf
    from pathlib import Path

    src = Path(args.pdf)
    if not src.exists():
        print(json.dumps({"ok": False, "error": f"File not found: {src}"}, ensure_ascii=False))
        return 1

    if args.dry_run:
        result = clean_pdf(src, src.with_suffix(".dryrun.pdf"), dry_run=True)
        for r in result.get("redacted", []):
            print(f"Page {r['page']:>2}: would redact {r['rects']} ad-link rectangle(s)")
        return 0

    dst = Path(args.output) if args.output else src.with_suffix(".cleaned.pdf")
    result = clean_pdf(src, dst, dry_run=False)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config_path = getattr(args, 'config_override', None) or args.config
    if args.command == 'auth-check':
        raise SystemExit(cmd_auth_check(config_path))
    if args.command == 'official-download':
        raise SystemExit(cmd_official_download(args, config_path))
    if args.command == 'universities':
        raise SystemExit(cmd_universities(config_path))
    if args.command == 'db-counts':
        raise SystemExit(cmd_db_counts(config_path))
    if args.command == 'crawl':
        raise SystemExit(cmd_crawl(args, config_path))
    if args.command == 'clean-pdf':
        raise SystemExit(cmd_clean_pdf(args))
    raise SystemExit(2)
