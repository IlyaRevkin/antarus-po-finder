"""
FirmwareFinder — Domain Exceptions
=====================================
All business-rule violations are expressed as typed exceptions.
"""


class FirmwareFinderError(Exception):
    """Base exception for all domain errors."""


class VersionConflictError(FirmwareFinderError):
    """Raised when the uploaded version is not newer than existing."""
    def __init__(self, existing: str, attempted: str, rule_name: str):
        self.existing  = existing
        self.attempted = attempted
        self.rule_name = rule_name
        super().__init__(
            f'Версия {attempted} не новее существующей {existing} '
            f'для правила «{rule_name}»'
        )


class InvalidVersionError(FirmwareFinderError):
    """Raised when the version string does not match prefix.body[.date]."""
    def __init__(self, raw: str):
        self.raw = raw
        super().__init__(
            f'Неверный формат версии: «{raw}». '
            f'Ожидается формат prefix.тело[.YYMMDD], например 3.42.260414 или 4.35.6.260421'
        )


class DiskUnavailableError(FirmwareFinderError):
    """Raised when the WebDAV root is inaccessible."""
    def __init__(self, path: str):
        self.path = path
        super().__init__(f'Диск недоступен: {path}')


class RuleNotFoundError(FirmwareFinderError):
    """Raised when a rule lookup fails."""
    def __init__(self, name: str):
        super().__init__(f'Правило не найдено: «{name}»')


class FileOperationError(FirmwareFinderError):
    """Raised when a filesystem operation fails."""
