"""도메인 이탈 차단 (GACA-152, agent-safety §2 #2 도메인 허용 목록).

클릭하기 전에 그 요소가 링크면 목적지 도메인을 본다. 허용 도메인 밖이면 실행하지 않는다.
허용 도메인 = 회차의 allowed_domains 스냅샷 + 대상 URL 의 도메인. 호스트 이름이 정확히 같아야 한다
(하위 도메인도 따로 적어야 허용된다).
목적지는 브라우저가 풀어 쓴 URL(element_map 의 url)로 본다 — 역슬래시 · <base> 같은 것을
파이썬이 다르게 풀어 우회되지 않게.
"""

from urllib.parse import urlsplit

from ..driver.base import Observation
from ..schemas import Action


def allowed_hosts(target_url: str, allowed_domains: list[str]) -> frozenset[str]:
    hosts = {domain.strip().lower() for domain in allowed_domains if domain.strip()}
    target_host = urlsplit(target_url).hostname
    if target_host:
        hosts.add(target_host)
    return frozenset(hosts)


def blocked_destination(
    action: Action, observation: Observation, hosts: frozenset[str]
) -> str | None:
    """click 할 요소가 허용 도메인 밖으로 가는 링크면 그 목적지 URL, 아니면 None."""
    if action.kind != "click":
        return None
    element = observation.element_map.get(action.element_id) or {}
    url = element.get("url")
    if not url:
        return None  # 링크가 아닌 요소 (버튼 등)
    parts = urlsplit(url)
    if parts.scheme == "javascript":
        return None  # 같은 페이지의 스크립트를 부르는 링크 — 주소를 옮기지 않는다
    if parts.scheme in ("http", "https") and parts.hostname in hosts:
        return None
    return url  # 다른 도메인 · mailto · file 같은 다른 스킴
