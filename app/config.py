"""Explicit development policy; these values are not approved product rules."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoPolicy:
    points_per_experience: int = 1
    max_upload_bytes: int = 5 * 1024 * 1024
    session_hours: int = 24 * 7
    secure_cookies: bool = False
    rule_version: str = 'local-demo-v1'

    def __post_init__(self):
        if self.points_per_experience <= 0 or self.max_upload_bytes <= 0 or self.session_hours <= 0:
            raise ValueError('Development policy values must be positive')
