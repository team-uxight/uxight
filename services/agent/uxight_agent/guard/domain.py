"""도메인 이탈 차단 (GACA-152, agent-safety §2 #2 도메인 허용 목록).

허용 도메인 = 회차의 allowed_domains 스냅샷 + 대상 URL. '호스트:포트' 가 정확히 같아야 한다
(하위 도메인 · 다른 포트는 밖이다). allowed_domains 값에 포트가 없으면 80 · 443 을 허용한다.
http · https 가 아닌 주소(javascript: · mailto: 등)는 모두 밖으로 본다.

막는 곳은 세 겹이다.
1. 클릭 전: 링크 목적지(브라우저가 풀어 쓴 element_map 의 url)를 본다 — PersonaAgent.
2. 이동 요청: 허용 밖으로 가는 top-level 이동 요청을 브라우저에서 끊는다 — DomDriver(route).
   스크립트 · 폼 제출 · 누르는 순간 바뀐 링크처럼 클릭 전에 목적지를 알 수 없는 이동도 막힌다.
   새 창(target=_blank · window.open 등)의 이동은 주소와 상관없이 끊는다 (GACA-223).
3. 행동 뒤: 그래도 허용 밖 주소에 와 있으면(리다이렉트 등) 행동 전 주소로 되돌린다 — DomDriver.
"""

from urllib.parse import urlsplit

from ..driver.base import Observation
from ..schemas import Action

DEFAULT_PORTS = {"http": 80, "https": 443}
# 로그 · 감사 로그에 남기는 목적지 길이 상한
MAX_DESTINATION_LENGTH = 200


def host_key(url: str) -> str | None:
    """http(s) 주소의 '호스트:포트'. 포트를 안 적었으면 스킴의 기본 포트. 그 밖의 주소는 None.

    로컬 파일(file:, 시험 fixture)은 통째로 한 출처 "file:" 로 본다 — 대상 URL 이 file: 일 때만
    허용되고, http(s) 대상에서 file: 주소로는 가지 못한다.
    """
    parts = urlsplit(url)
    if parts.scheme == "file":
        return "file:"
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname:
        return None
    try:
        port = parts.port or DEFAULT_PORTS[parts.scheme]
    except ValueError:  # 숫자가 아닌 포트
        return None
    return f"{parts.hostname}:{port}"


def allowed_hosts(target_url: str, allowed_domains: list[str]) -> frozenset[str]:
    keys: set[str] = set()
    for domain in allowed_domains:
        domain = domain.strip().lower()
        if not domain:
            continue
        if ":" in domain:  # 포트까지 적은 값
            keys.add(domain)
        else:
            keys |= {f"{domain}:{port}" for port in DEFAULT_PORTS.values()}
    target = host_key(target_url)
    if target:
        keys.add(target)
    return frozenset(keys)


def is_allowed(url: str, hosts: frozenset[str]) -> bool:
    key = host_key(url)
    return key is not None and key in hosts


def blocked_destination(
    action: Action, observation: Observation, hosts: frozenset[str]
) -> str | None:
    """click 할 요소가 허용 밖으로 가는 링크면 그 목적지 URL, 아니면 None."""
    if action.kind != "click":
        return None
    url = (observation.element_map.get(action.element_id) or {}).get("url")
    if not url:
        return None  # 링크가 아닌 요소 — 이동하면 2 · 3 단계가 막는다
    return None if is_allowed(url, hosts) else url


def safe_destination(url: str) -> str:
    """로그에 남길 목적지. 쿼리 · 조각(토큰이 들어 있을 수 있다)을 빼고 길이를 자른다."""
    parts = urlsplit(url)
    return parts._replace(query="", fragment="").geturl()[:MAX_DESTINATION_LENGTH]
