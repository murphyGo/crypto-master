"""File-based loader for ``TradingProfile`` definitions.

Profiles live under ``trading_profiles/`` as YAML or JSON files.
Each file's stem is the profile name. The loader parses the file,
validates it against ``TradingProfile``, and returns a typed object.

Related Requirements:
- NFR-010: Extensibility — new profiles by adding files
- FR-005: Technique+profile combinations
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.logger import get_logger
from src.trading.profiles import TradingProfile

logger = get_logger("crypto_master.trading.profile_loader")


DEFAULT_PROFILES_DIR = Path("trading_profiles")

_YAML_SUFFIXES = {".yaml", ".yml"}
_JSON_SUFFIXES = {".json"}
_SUPPORTED_SUFFIXES = _YAML_SUFFIXES | _JSON_SUFFIXES


class ProfileLoaderError(Exception):
    """Base exception for profile loader errors."""

    pass


class ProfileNotFoundError(ProfileLoaderError):
    """Raised when a profile cannot be located on disk."""

    pass


class ProfileValidationError(ProfileLoaderError):
    """Raised when a profile file fails parsing or validation."""

    pass


class ProfileLoader:
    """Loads ``TradingProfile`` objects from a directory.

    Supports YAML (``.yaml`` / ``.yml``) and JSON (``.json``) files.
    The file stem is the profile's canonical name. A single directory
    should not contain multiple files with the same stem in different
    formats — first match wins in that case.

    Attributes:
        profiles_dir: Directory to scan for profile files.
    """

    def __init__(self, profiles_dir: Path | None = None) -> None:
        """Initialize the loader.

        Args:
            profiles_dir: Directory containing profile files.
                Defaults to ``trading_profiles/`` resolved relative
                to the current working directory.
        """
        self.profiles_dir = profiles_dir or DEFAULT_PROFILES_DIR

    def list_profiles(self) -> list[str]:
        """List all profile names found in the directory.

        Returns:
            Sorted list of profile names (file stems). Empty if the
            directory does not exist.
        """
        if not self.profiles_dir.exists():
            return []

        names: set[str] = set()
        for path in self.profiles_dir.iterdir():
            if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES:
                names.add(path.stem)
        return sorted(names)

    def load_profile(self, name: str) -> TradingProfile:
        """Load a single profile by name.

        Searches for ``{name}.yaml``, ``{name}.yml``, ``{name}.json``
        in that order.

        Args:
            name: Profile name (file stem).

        Returns:
            The parsed ``TradingProfile``.

        Raises:
            ProfileNotFoundError: If no matching file exists.
            ProfileValidationError: If the file is malformed or fails
                schema validation.
        """
        for suffix in (".yaml", ".yml", ".json"):
            path = self.profiles_dir / f"{name}{suffix}"
            if path.exists():
                return self._load_from_path(path, fallback_name=name)

        raise ProfileNotFoundError(
            f"Profile '{name}' not found in {self.profiles_dir}"
        )

    def load_profile_from_file(self, path: Path) -> TradingProfile:
        """Load a profile directly from an explicit file path.

        Args:
            path: Path to the profile file.

        Returns:
            The parsed ``TradingProfile``.

        Raises:
            ProfileNotFoundError: If the file does not exist.
            ProfileValidationError: On parse or schema errors.
        """
        if not path.exists():
            raise ProfileNotFoundError(f"Profile file not found: {path}")
        return self._load_from_path(path, fallback_name=path.stem)

    def load_all_profiles(self) -> dict[str, TradingProfile]:
        """Load every profile in the directory.

        Errors on individual files are logged and the file is
        skipped — one bad file should not prevent loading the rest.

        Returns:
            Dict of profile name -> ``TradingProfile``.
        """
        result: dict[str, TradingProfile] = {}
        for name in self.list_profiles():
            try:
                result[name] = self.load_profile(name)
            except ProfileLoaderError as e:
                logger.error(f"Skipping profile '{name}': {e}")
        return result

    def _load_from_path(
        self, path: Path, fallback_name: str
    ) -> TradingProfile:
        """Parse and validate a profile file.

        Args:
            path: File to read.
            fallback_name: Name to assign if the file omits ``name``.

        Returns:
            The parsed profile.

        Raises:
            ProfileValidationError: On parse or schema errors.
        """
        suffix = path.suffix.lower()
        try:
            with open(path, encoding="utf-8") as f:
                if suffix in _YAML_SUFFIXES:
                    data = yaml.safe_load(f)
                elif suffix in _JSON_SUFFIXES:
                    data = json.load(f)
                else:
                    raise ProfileValidationError(
                        f"Unsupported profile file extension: {path.suffix}"
                    )
        except (OSError, yaml.YAMLError, json.JSONDecodeError) as e:
            raise ProfileValidationError(
                f"Failed to parse {path}: {e}"
            ) from e

        if data is None:
            raise ProfileValidationError(f"Profile file is empty: {path}")
        if not isinstance(data, dict):
            raise ProfileValidationError(
                f"Profile file must be a mapping, got {type(data).__name__}: {path}"
            )

        # Default name to file stem if omitted
        data.setdefault("name", fallback_name)

        try:
            profile = TradingProfile(**data)
        except Exception as e:
            raise ProfileValidationError(
                f"Invalid profile in {path}: {e}"
            ) from e

        logger.debug(f"Loaded profile '{profile.name}' from {path}")
        return profile
