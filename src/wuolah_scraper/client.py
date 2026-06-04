from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from .auth import (
    apply_auth_to_session,
    load_auth_material,
    refresh_access_token,
    token_is_fresh,
)
from .next_data import parse_next_data_from_html, save_json, safe_slug


class WuolahClient:
    def __init__(
        self,
        base_url: str,
        api_base_url: str,
        auth_cfg: dict[str, Any] | None,
        crawl_cfg: dict[str, Any] | None,
        raw_dir: str | Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_base_url = api_base_url.rstrip('/')
        self.crawl_cfg = crawl_cfg or {}
        self.timeout = int(self.crawl_cfg.get('request_timeout', 30))
        self.sleep_seconds = float(self.crawl_cfg.get('sleep_seconds', 0.15))
        self.user_agent = str((auth_cfg or {}).get('user_agent') or 'Mozilla/5.0')
        self.raw_dir = Path(raw_dir) if raw_dir else None

        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json, text/html;q=0.9,*/*;q=0.8',
            'User-Agent': self.user_agent,
        })
        self.auth_material = load_auth_material(auth_cfg)
        apply_auth_to_session(self.session, self.auth_material)

    def _sleep(self) -> None:
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)

    def _ensure_access_token(self, force_refresh: bool = False) -> None:
        refresh_token = self.auth_material.refresh_token
        access_token = self.auth_material.access_token
        if not refresh_token:
            return
        if not force_refresh and token_is_fresh(access_token):
            return
        refreshed = refresh_access_token(self.api_base_url, refresh_token, self.user_agent)
        self.auth_material.access_token = str(refreshed.get('accessToken') or '')
        self.auth_material.refresh_token = str(refreshed.get('refreshToken') or refresh_token)
        if self.auth_material.access_token:
            self.session.headers['Authorization'] = f"Bearer {self.auth_material.access_token}"

    def _build_url(self, path_or_url: str, api: bool = True) -> str:
        if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
            return path_or_url
        base = self.api_base_url if api else self.base_url
        return urljoin(base + '/', path_or_url.lstrip('/'))

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        api: bool = True,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_refresh_retry: bool = True,
    ) -> requests.Response:
        if api:
            self._ensure_access_token()
        url = self._build_url(path_or_url, api=api)
        response = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code == 401 and api and allow_refresh_retry and self.auth_material.refresh_token:
            self._ensure_access_token(force_refresh=True)
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.timeout,
            )
        response.raise_for_status()
        self._sleep()
        return response

    def get_json(self, path_or_url: str, *, api: bool = True, params: dict[str, Any] | None = None) -> Any:
        response = self.request('GET', path_or_url, api=api, params=params)
        return response.json()

    def get_text(self, path_or_url: str, *, api: bool = False, params: dict[str, Any] | None = None) -> str:
        response = self.request('GET', path_or_url, api=api, params=params)
        return response.text

    def fetch_next_data(self, page_path_or_url: str, *, raw_name: str | None = None) -> dict[str, Any]:
        html = self.get_text(page_path_or_url, api=False)
        next_data = parse_next_data_from_html(html)
        if self.raw_dir is not None:
            name = raw_name or safe_slug(page_path_or_url)
            save_json(self.raw_dir / f'{name}.json', next_data)
        return next_data

    def list_universities(self) -> list[dict[str, Any]]:
        next_data = self.fetch_next_data('/', raw_name='home')
        seen: dict[int, dict[str, Any]] = {}
        queries = next_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        for query in queries:
            data = query.get('state', {}).get('data')
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('items')
            else:
                items = None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                if {'id', 'slug', 'name'}.issubset(item.keys()) and 'logoUrl' in item:
                    try:
                        seen[int(item['id'])] = item
                    except Exception:
                        continue
        return sorted(seen.values(), key=lambda x: (x.get('name') or '').lower())

    def get_university_detail(self, id_or_slug: str | int) -> dict[str, Any]:
        return self.get_json(f'/v2/structure/university/{id_or_slug}')

    def get_center_detail(self, id_or_slug: str | int) -> dict[str, Any]:
        return self.get_json(f'/v2/structure/center/{id_or_slug}')

    def get_community_detail(self, id_or_slug: str | int) -> dict[str, Any]:
        return self.get_json(f'/v2/structure/community/{id_or_slug}')

    def get_subject_detail(self, id_or_slug: str | int) -> dict[str, Any]:
        return self.get_json(f'/v2/structure/subject/{id_or_slug}')

    def get_community_subject(
        self,
        community_id_or_slug: str | int,
        subject_id_or_slug: str | int,
        *,
        course: int | None = None,
        skip_enabled_filter: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            'populate[0]': 'subject',
            'populate[1]': 'community',
        }
        if course is not None:
            params['filter[course]'] = course
        params['filter[skipEnabledFilter]'] = str(bool(skip_enabled_filter)).lower()
        return self.get_json(
            f'/v2/communities/{community_id_or_slug}/subjects/{subject_id_or_slug}',
            params=params,
        )

    def get_me(self) -> dict[str, Any]:
        return self.get_json('/v2/me')

    def get_document(self, document_id: int, *, populate: bool = True) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if populate:
            populate_values = ['user', 'community', 'community.center', 'community.university', 'study', 'subject']
            for idx, value in enumerate(populate_values):
                params[f'populate[{idx}]'] = value
        return self.get_json(f'/v2/documents/{document_id}', params=params)

    def request_official_download(
        self,
        document_id: int,
        *,
        machine_id: str,
        with_coins: bool = False,
        captcha_code: str | None = None,
        referral_code: str | None = None,
        no_ads_token: str | None = None,
        user_targetings_snapshot_id: str | None = None,
        qr_data: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'machineId': machine_id,
            'userTargetingsSnapshotId': user_targetings_snapshot_id,
            'adblockDetected': False,
            'fileId': document_id,
            'captchaCode': captcha_code,
            'noAdsWithCoins': with_coins,
            'noAdsToken': no_ads_token,
            'ads': [],
            'referralCode': referral_code,
            'qrData': qr_data,
        }
        response = self.request('POST', '/v2/download', api=True, json_body=payload)
        return response.json()

    def download_url_to_file(self, url: str, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(url, stream=True, timeout=self.timeout) as response:
            response.raise_for_status()
            with path.open('wb') as fh:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
        self._sleep()
        return path

    def iter_documents(
        self,
        *,
        community_id: int,
        subject_id: int | None = None,
        course: int | None = None,
        sort: str = '-numDownloads',
        page_size: int = 100,
        max_pages: int = 0,
        category: str | None = None,
        creator_user_id: int | None = None,
    ):
        page = 0
        while True:
            if max_pages and page >= max_pages:
                return
            params: dict[str, Any] = {
                'sort': sort,
                'pagination[page]': page,
                'pagination[pageSize]': page_size,
                'pagination[withCount]': 'false',
                'populate[0]': 'community',
                'populate[1]': 'user',
            }
            params['filter[communityId]'] = community_id
            if subject_id is not None:
                params['filter[subjectId]'] = subject_id
            if course is not None:
                params['filter[course]'] = course
            if category:
                params['filter[category]'] = category
            if creator_user_id is not None:
                params['filter[userId]'] = creator_user_id

            payload = self.get_json('/v2/documents', params=params)
            items = payload.get('data', []) if isinstance(payload, dict) else []
            if not items:
                return
            for item in items:
                yield item
            if len(items) < page_size:
                return
            page += 1
