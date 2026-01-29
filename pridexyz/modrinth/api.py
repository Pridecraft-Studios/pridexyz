from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator, IO, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from pridexyz.logger import get_logger
from pridexyz.modrinth.types import NewProject, DictKV, NewVersion, GalleryImage, ProjectUpdate


class ModrinthAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


def cut_game_versions_until(cutoff_version: str, versions: List[DictKV]) -> List[DictKV]:
    result: List[DictKV] = []
    for version in versions:
        result.append(version)
        if version.get("version") == cutoff_version:
            break
    return result


class ModrinthAPI:
    def __init__(self, token: str, api_url: str = "https://api.modrinth.com", user_agent: str = "requests/2.32.5",
                 enable_debug_logging = False) -> None:
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token, "User-Agent": user_agent})
        self._ratelimit_lock = threading.Lock()
        self._ratelimit_limit = 300
        self._ratelimit_remaining = 300
        self._ratelimit_reset = 0
        self._ratelimit_last_checked = time.time()
        self.logger = get_logger(str(self.__hash__()))
        self.enable_debug_logging = enable_debug_logging

    def _log_debug(self, message: str, **kwargs) -> None:
        if self.enable_debug_logging:
            self.logger.debug(message, **kwargs)

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(self.session.headers)

        s.headers["Connection"] = "close"

        retry = Retry(total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504], )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
        s.mount("https://", adapter)

        return s

    def _update_ratelimit(self, response: requests.Response):
        with self._ratelimit_lock:
            try:
                limit = int(response.headers.get("X-Ratelimit-Limit", self._ratelimit_limit))
                remaining = int(response.headers.get("X-Ratelimit-Remaining", self._ratelimit_remaining))
                reset = int(response.headers.get("X-Ratelimit-Reset", 0))
            except Exception:
                limit = self._ratelimit_limit
                remaining = self._ratelimit_remaining
                reset = 0

            self._log_debug(f"[RL] Updated rate limit: limit={limit}, remaining={remaining}, reset={reset}")

            self._ratelimit_limit = limit
            self._ratelimit_remaining = remaining
            self._ratelimit_reset = reset
            self._ratelimit_last_checked = time.time()

    def _respect_ratelimit(self):
        self._log_debug(f"[RL] Checking rate limit: remaining={self._ratelimit_remaining}, "
                          f"reset={self._ratelimit_reset}")

        with self._ratelimit_lock:
            if self._ratelimit_remaining > 0:
                self._log_debug("[RL] Enough remaining; continuing")
                return

            sleep_time = self._ratelimit_reset
            self.logger.warning(f"[RL] Ratelimited! Sleeping {sleep_time} seconds")

            self._ratelimit_remaining = self._ratelimit_limit
            self._ratelimit_reset = 0

        if sleep_time > 0:
            time.sleep(sleep_time)
            self._log_debug("[RL] Finished sleep")

    def _request(self, method: str, endpoint: str, api_version: int = 2, **kwargs) -> Any:
        url = f"{self.api_url}/v{api_version}{endpoint}"
        self._log_debug(f"[REQ] {method} {url} START kwargs={kwargs.keys()}")

        # Thread-local session
        session = getattr(threading.current_thread(), "_modrinth_session", None)
        if session is None:
            session = self._make_session()
            setattr(threading.current_thread(), "_modrinth_session", session)
            self._log_debug("[REQ] Created new per-thread session")

        # Rate limit check
        self._log_debug("[REQ] Checking rate limit before request")
        self._respect_ratelimit()

        response = None
        try:
            self._log_debug(f"[REQ] Sending request {method} {url}")
            response = session.request(method, url, **kwargs)

            self._log_debug(f"[REQ] Got response status={response.status_code}, "
                              f"length={len(response.content)}")
            self._log_debug(f"[REQ] Response headers: {dict(response.headers)}")

            # Update ratelimit
            self._update_ratelimit(response)

            response.raise_for_status()
            self._log_debug("[REQ] Request successful; returning JSON")
            return response.json() if response.text else {}

        except requests.HTTPError as e:
            if response is not None:
                self.logger.error(f"[REQ] HTTP error {response.status_code}: {response.text[:500]}")
            else:
                self.logger.error(f"[REQ] HTTP error without response: {e}")

            try:
                error_json = response.json()
            except Exception:
                error_json = {"error": response.text if response else "No response"}

            raise ModrinthAPIError(str(e), status_code=response.status_code if response else None,
                response=error_json) from e

        except Exception as e:
            self.logger.exception(f"[REQ] Unexpected exception during request: {e}")
            raise

    @staticmethod
    def _to_dict(obj: Any) -> Dict[str, Any]:
        return {key: value for key, value in obj.__dict__.items() if value is not None}

    @staticmethod
    def _open_files(paths: List[Path]) -> Iterator[Dict[str, IO[bytes]]]:
        with ExitStack() as stack:
            files = {f"file{idx}": stack.enter_context(p.open("rb")) for idx, p in enumerate(paths)}
            yield files

    def create_project(self, project: NewProject, icon_path: Optional[Path] = None) -> DictKV:
        payload = self._to_dict(project)
        if "donation_urls" in payload:
            payload["donation_urls"] = [du.__dict__ for du in payload["donation_urls"]]

        if icon_path:
            with icon_path.open("rb") as icon_file:
                return self._request("POST", "/project", data={"data": json.dumps(payload)}, files={"icon": icon_file})
        return self._request("POST", "/project", data={"data": json.dumps(payload)})

    def get_project(self, id_or_slug: str) -> DictKV:
        return self._request("GET", f"/project/{id_or_slug}")

    def get_version(self, version_id: str) -> DictKV:
        return self._request("GET", f"/version/{version_id}")

    def get_organization_projects(self, organization_id: str) -> DictKV:
        return self._request("GET", f"/organization/{organization_id}/projects", 3)

    def modify_project(self, id_or_slug: str, update: ProjectUpdate) -> None:
        payload = self._to_dict(update)
        self._request("PATCH", f"/project/{id_or_slug}", json=payload)

    def change_project_icon(self, id_or_slug: str, icon_path: Path, ext: str) -> None:
        with icon_path.open("rb") as icon_file:
            self._request("PATCH", f"/project/{id_or_slug}/icon", params={"ext": ext}, data=icon_file)

    def create_version(self, version: NewVersion, file_paths: List[Path], primary_file: Optional[str] = None) -> DictKV:
        with ExitStack() as stack:
            files = {f"file{idx}": stack.enter_context(path.open("rb")) for idx, path in enumerate(file_paths)}
            payload: DictKV = {**version.__dict__, "file_parts": list(files.keys()), }
            if primary_file:
                payload["primary_file"] = primary_file

            return self._request("POST", "/version", data={"data": json.dumps(payload)}, files=files)

    def modify_version(self, version_id: str, update: VersionUpdate) -> None:
        payload = self._to_dict(update)
        self._request("PATCH", f"/version/{version_id}", json=payload)

    def add_gallery_image(self, id_or_slug: str, image: GalleryImage) -> None:
        params: DictKV = {"ext": image.ext, "featured": str(image.featured).lower()}
        if image.title:
            params["title"] = image.title
        if image.description:
            params["description"] = image.description
        if image.ordering is not None:
            params["ordering"] = image.ordering

        with image.image_path.open("rb") as img_file:
            self._request("POST", f"/project/{id_or_slug}/gallery", params=params, data=img_file)

    def delete_gallery_image(self, id_or_slug: str, image_url: str) -> None:
        self._request("DELETE", f"/project/{id_or_slug}/gallery", params={"url": image_url})

    def delete_version(self, version_id: str) -> None:
        self._request("DELETE", f"/version/{version_id}")

    def get_game_versions(self) -> List[DictKV]:
        return self._request("GET", "/tag/game_version")

    def get_loaders(self) -> List[DictKV]:
        return self._request("GET", "/tag/loader")

    def get_game_versions_until(self, cutoff_version: str) -> List[DictKV]:
        versions = self.get_game_versions()
        result: List[DictKV] = []
        for version in versions:
            result.append(version)
            if version.get("version") == cutoff_version:
                break
        return result

    @classmethod
    def parallel_requests(cls, requests_list: List[Callable[[], Any]], max_parallel: int = 6) -> List[Any]:
        """Execute API calls in parallel, safely. Rate limiting is handled inside _request."""
        results = [None] * len(requests_list)

        def wrapper(fn: Callable[[], Any]):
            try:
                return fn()
            except Exception as e:
                return e

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_index = {executor.submit(wrapper, fn): i for i, fn in enumerate(requests_list)}

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()

        for r in results:
            if isinstance(r, Exception):
                raise r

        return results

    def get_project_versions(self, id_or_slug):
        return self._request("GET", f"/project/{id_or_slug}/version")
