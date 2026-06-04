from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass
class RunContext:
    run_id: str
    started_at: str


class Storage:
    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir)
        self.outputs_dir = self.project_dir / 'outputs'
        self.raw_dir = self.outputs_dir / 'raw_pages'
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.outputs_dir / 'wuolah.sqlite'
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            '''
            CREATE TABLE IF NOT EXISTS universities (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE,
                name TEXT,
                short_name TEXT,
                verified INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS centers (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE,
                name TEXT,
                university_id INTEGER,
                city_id INTEGER,
                verified INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE,
                name TEXT,
                status TEXT,
                university_id INTEGER,
                center_id INTEGER,
                study_type_id INTEGER,
                study_type_slug TEXT,
                study_id INTEGER,
                num_users INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subjects (
                community_subject_id INTEGER PRIMARY KEY,
                subject_id INTEGER,
                community_id INTEGER,
                slug TEXT,
                name TEXT,
                course INTEGER,
                num_files INTEGER,
                num_artifacts INTEGER,
                verified INTEGER,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE,
                name TEXT,
                category TEXT,
                community_id INTEGER,
                subject_id INTEGER,
                community_subject_id INTEGER,
                course INTEGER,
                user_id INTEGER,
                num_pages INTEGER,
                num_downloads INTEGER,
                file_type TEXT,
                size INTEGER,
                is_downloadable INTEGER,
                file_url TEXT,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS community_artifacts (
                id TEXT PRIMARY KEY,
                entity_id INTEGER,
                entity_type TEXT,
                entity_subtype TEXT,
                community_id INTEGER,
                subject_id INTEGER,
                course INTEGER,
                owner_id INTEGER,
                title TEXT,
                slug TEXT,
                raw_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                filters_json TEXT NOT NULL,
                summary_json TEXT
            );
            '''
        )
        self.conn.commit()

    def start_run(self, filters: dict[str, Any]) -> RunContext:
        started_at = _utc_now()
        run_id = started_at.replace(':', '-').replace('+00:00', 'Z')
        self.conn.execute(
            'INSERT OR REPLACE INTO runs (run_id, started_at, filters_json) VALUES (?, ?, ?)',
            (run_id, started_at, _json(filters)),
        )
        self.conn.commit()
        return RunContext(run_id=run_id, started_at=started_at)

    def finish_run(self, run: RunContext, summary: dict[str, Any]) -> None:
        finished_at = _utc_now()
        self.conn.execute(
            'UPDATE runs SET finished_at = ?, summary_json = ? WHERE run_id = ?',
            (finished_at, _json(summary), run.run_id),
        )
        self.conn.commit()
        summary_path = self.outputs_dir / 'last_run_summary.json'
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    def upsert_university(self, row: dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO universities
            (id, slug, name, short_name, verified, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row.get('id'), row.get('slug'), row.get('name'), row.get('shortName'),
                int(bool(row.get('verified'))), _json(row), _utc_now(),
            ),
        )

    def upsert_center(self, row: dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO centers
            (id, slug, name, university_id, city_id, verified, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row.get('id'), row.get('slug'), row.get('name'), row.get('universityId'),
                row.get('cityId'), int(bool(row.get('verified'))), _json(row), _utc_now(),
            ),
        )

    def upsert_community(self, row: dict[str, Any], *, study_type_id: int | None = None, study_type_slug: str | None = None) -> None:
        segmentations = row.get('segmentations') or {}
        center_id = ((segmentations.get('center') or {}).get('id') if isinstance(segmentations, dict) else None)
        university_id = ((segmentations.get('university') or {}).get('id') if isinstance(segmentations, dict) else None)
        study_id = ((segmentations.get('study') or {}).get('id') if isinstance(segmentations, dict) else None)
        if study_type_id is None:
            study_type_id = ((segmentations.get('studyType') or {}).get('id') if isinstance(segmentations, dict) else None)
        if study_type_slug is None:
            st_item = (segmentations.get('studyType') or {}).get('item') if isinstance(segmentations, dict) else None
            if isinstance(st_item, dict):
                study_type_slug = st_item.get('slug')
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO communities
            (id, slug, name, status, university_id, center_id, study_type_id, study_type_slug, study_id, num_users, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row.get('id'), row.get('slug'), row.get('name'), row.get('status'),
                university_id, center_id, study_type_id, study_type_slug, study_id,
                row.get('numUsers'), _json(row), _utc_now(),
            ),
        )

    def upsert_subject(self, row: dict[str, Any]) -> None:
        subject = row.get('subject') or {}
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO subjects
            (community_subject_id, subject_id, community_id, slug, name, course, num_files, num_artifacts, verified, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row.get('id'), row.get('subjectId') or subject.get('id'), row.get('communityId'),
                row.get('slug') or subject.get('slug'), row.get('name') or subject.get('name'),
                row.get('course'), row.get('numFiles'), row.get('numArtifacts'),
                int(bool(row.get('verified') or row.get('isVerified'))), _json(row), _utc_now(),
            ),
        )

    def upsert_document(self, row: dict[str, Any]) -> None:
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO documents
            (id, slug, name, category, community_id, subject_id, community_subject_id, course, user_id, num_pages, num_downloads, file_type, size, is_downloadable, file_url, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row.get('id'), row.get('slug'), row.get('name'), row.get('category'),
                row.get('communityId'), row.get('subjectId'), row.get('communitySubjectId'),
                row.get('course'), row.get('userId'), row.get('numPages'), row.get('numDownloads'),
                row.get('fileType'), row.get('size'), int(bool(row.get('isDownloadable'))),
                row.get('fileUrl') or '', _json(row), _utc_now(),
            ),
        )

    def upsert_community_artifact(self, row: dict[str, Any]) -> None:
        artifact_id = str(row.get('id'))
        if not artifact_id:
            return
        self.conn.execute(
            '''
            INSERT OR REPLACE INTO community_artifacts
            (id, entity_id, entity_type, entity_subtype, community_id, subject_id, course, owner_id, title, slug, raw_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                artifact_id, row.get('entityId'), row.get('entityType'), row.get('entitySubtype'),
                row.get('communityId'), row.get('subjectId'), row.get('course'), row.get('ownerId'),
                row.get('title') or row.get('name'), row.get('slug'), _json(row), _utc_now(),
            ),
        )

    def commit(self) -> None:
        self.conn.commit()

    def counts(self) -> dict[str, int]:
        tables = ['universities', 'centers', 'communities', 'subjects', 'documents', 'community_artifacts', 'runs']
        out: dict[str, int] = {}
        for table in tables:
            out[table] = int(self.conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
        return out

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
