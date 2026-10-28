from dataclasses import dataclass, replace
from typing import Final, Protocol

DEMO_SAFE_SETTING: Final = "demo_safe"
DEMO_SAFE_SAM_SETTING: Final = "demo_safe_sam"
ON: Final = "1"
OFF: Final = "0"


class SettingStore(Protocol):
    def get_setting(self, key: str) -> str | None: ...

    def set_setting(self, key: str, value: str) -> None: ...


@dataclass(frozen=True)
class DemoSafeMode:
    is_on: bool = False
    is_sam_reanchor_on: bool = True

    @property
    def allows_spark(self) -> bool:
        return not self.is_on

    @property
    def allows_image(self) -> bool:
        return not self.is_on

    @property
    def allows_voice(self) -> bool:
        return not self.is_on

    @property
    def allows_sam_recovery(self) -> bool:
        return not self.is_on

    @property
    def allows_sam_reanchor(self) -> bool:
        return not self.is_on or self.is_sam_reanchor_on

    @classmethod
    def load(cls, store: SettingStore) -> "DemoSafeMode":
        return cls(
            is_on=store.get_setting(DEMO_SAFE_SETTING) == ON,
            is_sam_reanchor_on=store.get_setting(DEMO_SAFE_SAM_SETTING) != OFF,
        )

    def with_on(self, is_on: bool) -> "DemoSafeMode":
        return replace(self, is_on=is_on)

    def with_sam_reanchor(self, is_on: bool) -> "DemoSafeMode":
        return replace(self, is_sam_reanchor_on=is_on)

    def save(self, store: SettingStore) -> None:
        store.set_setting(DEMO_SAFE_SETTING, ON if self.is_on else OFF)
        store.set_setting(DEMO_SAFE_SAM_SETTING, ON if self.is_sam_reanchor_on else OFF)
