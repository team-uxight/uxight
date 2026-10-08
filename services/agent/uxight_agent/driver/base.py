from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..schemas import Action


@dataclass(frozen=True)
class ActionResult:
    """act()의 수행 결과. 실패해도 예외 대신 ok=False와 error를 돌려준다."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class Observation:
    """observe()가 돌려주는 현재 페이지 상태.

    dom은 LLM에게 보여줄 텍스트, element_map은 ID → 요소 정보.
    SoM 방식 드라이버는 이 클래스를 확장해 스크린샷 등을 추가한다.
    """

    url: str
    title: str
    dom: str
    element_map: dict[int, dict] = field(default_factory=dict)


class Driver(ABC):
    """Persona Agent가 대상 페이지에 접근하는 유일한 통로.

    Walking Skeleton은 DOM 방식(DomDriver)을 쓰지만, 실제 구현에서는
    스크린샷(SoM) 방식이나 DOM + SoM 하이브리드로 교체할 수 있어야 한다.
    """

    @abstractmethod
    async def start(self, url: str) -> None:
        """브라우저를 띄우고 시작 URL로 이동한다. 실패하면 예외를 던진다."""

    @abstractmethod
    async def observe(self) -> Observation:
        """현재 페이지를 관찰하고 요소마다 ID를 부여해 element_map을 만든다."""

    @abstractmethod
    async def act(self, action: Action) -> ActionResult:
        """결정된 행동을 수행한다. 어떤 실패도 예외 대신 ActionResult로 돌려준다."""

    @abstractmethod
    async def close(self) -> None:
        """브라우저 자원을 정리한다."""

    async def __aenter__(self) -> "Driver":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()
