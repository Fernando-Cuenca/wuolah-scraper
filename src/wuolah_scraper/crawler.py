from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .client import WuolahClient
from .next_data import find_queries
from .storage import Storage

CATEGORY_VALUES = [
    'apuntes',
    'examenes',
    'ejercicios',
    'practicas',
    'trabajos',
    'test',
    'pec',
    'otros',
]


@dataclass
class CrawlFilters:
    university_slug: str | None = None
    community_slug: str | None = None
    subject_slug: str | None = None
    study_type_slug: str | None = None
    center_slug: str | None = None
    course: int | None = None
    category: str | None = None
    creator_user_id: int | None = None
    keyword: str | None = None
    sort: str = '-numDownloads'
    page_size: int = 100
    max_pages: int = 0
    fetch_document_details: bool = True
    all_universities: bool = False


class WuolahCrawler:
    def __init__(self, client: WuolahClient, storage: Storage, crawl_cfg: dict[str, Any] | None = None) -> None:
        self.client = client
        self.storage = storage
        self.crawl_cfg = crawl_cfg or {}
        self.summary = {
            'universities_seen': 0,
            'universities_stored': 0,
            'centers_stored': 0,
            'communities_stored': 0,
            'subjects_stored': 0,
            'documents_stored': 0,
            'document_details_fetched': 0,
            'community_preview_artifacts_stored': 0,
            'notes': [],
        }

    def _note(self, text: str) -> None:
        self.summary['notes'].append(text)

    def _document_matches(self, doc: dict[str, Any], filters: CrawlFilters) -> bool:
        if filters.category and (doc.get('category') or '').lower() != filters.category.lower():
            return False
        if filters.creator_user_id is not None and int(doc.get('userId') or 0) != int(filters.creator_user_id):
            return False
        if filters.keyword:
            needle = filters.keyword.lower()
            haystack = ' '.join([
                str(doc.get('name') or ''),
                str(doc.get('slug') or ''),
                str(doc.get('teacher') or ''),
                str(doc.get('comments') or ''),
            ]).lower()
            if needle not in haystack:
                return False
        return True

    def crawl(self, filters: CrawlFilters) -> dict[str, Any]:
        if filters.all_universities:
            universities = self.client.list_universities()
            self.summary['universities_seen'] = len(universities)
            for university in universities:
                self.crawl_university(str(university['slug']), filters)
        elif filters.university_slug:
            self.crawl_university(filters.university_slug, filters)
        elif filters.community_slug:
            self.crawl_community(filters.community_slug, filters)
        else:
            raise ValueError('Necesitas --university-slug, --community-slug o --all-universities')

        self.storage.commit()
        self.summary['db_counts'] = self.storage.counts()
        return self.summary

    def crawl_university(self, university_slug: str, filters: CrawlFilters) -> None:
        next_data = self.client.fetch_next_data(f'/university/{university_slug}', raw_name=f'university__{university_slug}')
        queries = next_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])

        university = None
        centers: list[dict[str, Any]] = []
        communities: list[dict[str, Any]] = []

        for query in queries:
            query_key = query.get('queryKey') or []
            if not query_key or not isinstance(query_key[0], dict):
                continue
            head = query_key[0]
            data = query.get('state', {}).get('data')
            if head.get('id') == 'find-university-by-id-or-slug' and isinstance(data, dict):
                university = data
            elif head.get('id') == 'find-centers-by-university-id' and isinstance(data, dict):
                for page in data.get('pages', []):
                    for item in page.get('items', []):
                        entity = item.get('entity') if isinstance(item, dict) else None
                        if isinstance(entity, dict):
                            centers.append(entity)
            elif head.get('id') == 'structure' and head.get('scope') == 'community' and isinstance(data, dict):
                study_type_filter = ((head.get('query') or {}).get('filter') or {}).get('studyType') or []
                study_type_id = study_type_filter[0] if study_type_filter else None
                for page in data.get('pages', []):
                    for item in page.get('items', []):
                        if isinstance(item, dict):
                            enriched = dict(item)
                            enriched['_study_type_id_from_query'] = study_type_id
                            communities.append(enriched)

        if university:
            self.storage.upsert_university(university)
            self.summary['universities_stored'] += 1
        for center in centers:
            self.storage.upsert_center(center)
            self.summary['centers_stored'] += 1
        for community in communities:
            segmentations = community.get('segmentations') or {}
            st_item = (segmentations.get('studyType') or {}).get('item') if isinstance(segmentations, dict) else None
            st_slug = st_item.get('slug') if isinstance(st_item, dict) else None
            if filters.study_type_slug and st_slug != filters.study_type_slug:
                continue
            center_item = (segmentations.get('center') or {}).get('item') if isinstance(segmentations, dict) else None
            center_slug = center_item.get('slug') if isinstance(center_item, dict) else None
            if filters.center_slug and center_slug != filters.center_slug:
                continue
            self.storage.upsert_community(
                community,
                study_type_id=community.get('_study_type_id_from_query'),
                study_type_slug=st_slug,
            )
            self.summary['communities_stored'] += 1

        self.storage.commit()
        selected_communities = communities
        if filters.community_slug:
            selected_communities = [c for c in communities if c.get('slug') == filters.community_slug]
        for community in selected_communities:
            slug = community.get('slug')
            if not slug:
                continue
            self.crawl_community(str(slug), filters)

    def crawl_community(self, community_slug: str, filters: CrawlFilters) -> None:
        next_data = self.client.fetch_next_data(f'/{community_slug}', raw_name=f'community__{community_slug.replace("/", "__")}')
        queries = next_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])

        community_detail = None
        subjects: list[dict[str, Any]] = []
        preview_artifacts: list[dict[str, Any]] = []

        for query in queries:
            query_key = query.get('queryKey') or []
            if not query_key or not isinstance(query_key[0], dict):
                continue
            head = query_key[0]
            data = query.get('state', {}).get('data')
            if head.get('id') == 'communities' and head.get('scope') == 'community' and head.get('entity') == 'detail' and isinstance(data, dict):
                community_detail = data
            elif head.get('id') == 'community-subjects' and isinstance(data, list):
                subjects.extend([item for item in data if isinstance(item, dict)])
            elif head.get('id') == 'find-community-artifacts' and isinstance(data, dict):
                for page in data.get('pages', []):
                    preview_artifacts.extend([item for item in page.get('items', []) if isinstance(item, dict)])

        if community_detail:
            self.storage.upsert_community(community_detail)
            self.summary['communities_stored'] += 1

        for artifact in preview_artifacts:
            self.storage.upsert_community_artifact(artifact)
            self.summary['community_preview_artifacts_stored'] += 1

        for subject in subjects:
            self.storage.upsert_subject(subject)
            self.summary['subjects_stored'] += 1

        self.storage.commit()

        if community_detail is None:
            community_detail = self.client.get_community_detail(community_slug)
            self.storage.upsert_community(community_detail)
            self.storage.commit()

        community_id = int(community_detail.get('id'))
        chosen_subjects = subjects
        if filters.subject_slug:
            chosen_subjects = [s for s in subjects if s.get('slug') == filters.subject_slug]
            if not chosen_subjects:
                self._note(f'Subject {filters.subject_slug} not found in dehydratedState for {community_slug}; will attempt via API.')
                chosen_subjects = [{'slug': filters.subject_slug, 'communityId': community_id, 'course': filters.course}]

        for subject in chosen_subjects:
            subject_slug = subject.get('slug')
            if not subject_slug:
                continue
            course = filters.course if filters.course is not None else subject.get('course')
            self.crawl_subject(
                community_slug=community_slug,
                community_id=community_id,
                subject_slug=str(subject_slug),
                course=course,
                filters=filters,
            )

    def crawl_subject(
        self,
        *,
        community_slug: str,
        community_id: int,
        subject_slug: str,
        course: int | None,
        filters: CrawlFilters,
    ) -> None:
        community_subject = self.client.get_community_subject(community_id, subject_slug, course=course)
        if isinstance(community_subject, dict):
            self.storage.upsert_subject(community_subject)
            self.summary['subjects_stored'] += 1
        self.storage.commit()

        subject_id = int((community_subject.get('subjectId') or (community_subject.get('subject') or {}).get('id')))
        community_subject_id = community_subject.get('id')

        for doc in self.client.iter_documents(
            community_id=community_id,
            subject_id=subject_id,
            course=course,
            sort=filters.sort,
            page_size=filters.page_size,
            max_pages=filters.max_pages,
            category=filters.category,
            creator_user_id=filters.creator_user_id,
        ):
            if community_subject_id and not doc.get('communitySubjectId'):
                doc['communitySubjectId'] = community_subject_id
            if not self._document_matches(doc, filters):
                continue
            record = doc
            if filters.fetch_document_details:
                try:
                    detailed = self.client.get_document(int(doc['id']))
                    if isinstance(detailed, dict) and detailed:
                        record = detailed
                        self.summary['document_details_fetched'] += 1
                except Exception as exc:
                    self._note(f'Failed to fetch document detail for {doc.get("id")}: {exc}')
            self.storage.upsert_document(record)
            self.summary['documents_stored'] += 1

        self.storage.commit()
        self._note(
            f'Subject crawl complete: community={community_slug} subject={subject_slug} course={course} category={filters.category or "*"}'
        )

    def summary_json(self) -> str:
        return json.dumps(self.summary, ensure_ascii=False, indent=2)
