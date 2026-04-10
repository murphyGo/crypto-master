"""Tests for the ProfileLoader."""

import json
from pathlib import Path

import pytest

from src.trading.profile_loader import (
    ProfileLoader,
    ProfileNotFoundError,
    ProfileValidationError,
)
from src.trading.profiles import TradingProfile


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def profiles_dir(tmp_path: Path) -> Path:
    """An empty profiles directory under tmp_path."""
    d = tmp_path / "trading_profiles"
    d.mkdir()
    return d


@pytest.fixture
def loader(profiles_dir: Path) -> ProfileLoader:
    """ProfileLoader pointed at a tmp_path directory."""
    return ProfileLoader(profiles_dir=profiles_dir)


def write_yaml(path: Path, body: str) -> None:
    path.write_text(body)


# =============================================================================
# list_profiles
# =============================================================================


class TestListProfiles:
    """Tests for ProfileLoader.list_profiles."""

    def test_empty_directory(self, loader: ProfileLoader) -> None:
        """Empty dir returns []."""
        assert loader.list_profiles() == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Missing dir returns [] (no error)."""
        loader = ProfileLoader(profiles_dir=tmp_path / "nope")
        assert loader.list_profiles() == []

    def test_lists_yaml_and_json(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """YAML and JSON profiles both show up, sorted."""
        write_yaml(
            profiles_dir / "alpha.yaml",
            "name: alpha\nrisk_percent: 1.0\n",
        )
        (profiles_dir / "beta.json").write_text(
            json.dumps({"name": "beta", "risk_percent": 2.0})
        )
        write_yaml(
            profiles_dir / "gamma.yml",
            "name: gamma\nrisk_percent: 1.5\n",
        )
        assert loader.list_profiles() == ["alpha", "beta", "gamma"]

    def test_ignores_unknown_extensions(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Non-YAML/JSON files are skipped."""
        (profiles_dir / "readme.txt").write_text("not a profile")
        (profiles_dir / "valid.yaml").write_text(
            "name: valid\nrisk_percent: 1.0\n"
        )
        assert loader.list_profiles() == ["valid"]


# =============================================================================
# load_profile
# =============================================================================


class TestLoadProfile:
    """Tests for ProfileLoader.load_profile."""

    def test_load_yaml(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """A well-formed YAML profile loads successfully."""
        write_yaml(
            profiles_dir / "moderate.yaml",
            """
name: moderate
version: "1.0.0"
description: test
risk_percent: 1.0
max_leverage: 10
default_leverage: 5
max_position_size_percent: 10.0
min_risk_reward_ratio: 1.5
min_confidence: 0.6
order_type: market
require_confirmation: true
            """.strip(),
        )
        profile = loader.load_profile("moderate")
        assert isinstance(profile, TradingProfile)
        assert profile.name == "moderate"
        assert profile.risk_percent == 1.0
        assert profile.max_leverage == 10
        assert profile.default_leverage == 5
        assert profile.order_type == "market"

    def test_load_json(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """A well-formed JSON profile loads successfully."""
        (profiles_dir / "aggressive.json").write_text(
            json.dumps(
                {
                    "name": "aggressive",
                    "risk_percent": 2.0,
                    "max_leverage": 25,
                    "default_leverage": 10,
                    "max_position_size_percent": 20.0,
                    "min_risk_reward_ratio": 1.2,
                    "min_confidence": 0.5,
                    "order_type": "market",
                }
            )
        )
        profile = loader.load_profile("aggressive")
        assert profile.name == "aggressive"
        assert profile.max_leverage == 25

    def test_yaml_takes_precedence_over_json(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """If both YAML and JSON exist, YAML wins (searched first)."""
        write_yaml(
            profiles_dir / "dup.yaml",
            "name: dup\nrisk_percent: 1.0\n",
        )
        (profiles_dir / "dup.json").write_text(
            json.dumps({"name": "dup", "risk_percent": 9.0})
        )
        profile = loader.load_profile("dup")
        assert profile.risk_percent == 1.0

    def test_name_defaulted_to_file_stem(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Missing 'name' in the file defaults to the file stem."""
        write_yaml(
            profiles_dir / "stemmed.yaml",
            "risk_percent: 1.0\n",
        )
        profile = loader.load_profile("stemmed")
        assert profile.name == "stemmed"

    def test_missing_profile_raises(
        self, loader: ProfileLoader
    ) -> None:
        """Requesting a non-existent profile raises ProfileNotFoundError."""
        with pytest.raises(ProfileNotFoundError):
            loader.load_profile("missing")

    def test_invalid_yaml_raises_validation(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Malformed YAML becomes ProfileValidationError."""
        write_yaml(profiles_dir / "broken.yaml", "not: [valid: yaml")
        with pytest.raises(ProfileValidationError):
            loader.load_profile("broken")

    def test_invalid_schema_raises_validation(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Fields that fail Pydantic validation become ProfileValidationError."""
        write_yaml(
            profiles_dir / "bad.yaml",
            "name: bad\nrisk_percent: -5\n",
        )
        with pytest.raises(ProfileValidationError):
            loader.load_profile("bad")

    def test_empty_file_raises_validation(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Empty file is not a valid profile."""
        (profiles_dir / "empty.yaml").write_text("")
        with pytest.raises(ProfileValidationError, match="empty"):
            loader.load_profile("empty")

    def test_non_mapping_raises_validation(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """A YAML list at the top level is not valid."""
        write_yaml(profiles_dir / "list.yaml", "- item1\n- item2\n")
        with pytest.raises(ProfileValidationError, match="mapping"):
            loader.load_profile("list")


# =============================================================================
# load_profile_from_file
# =============================================================================


class TestLoadProfileFromFile:
    """Tests for direct-file loading."""

    def test_load_from_explicit_path(
        self, loader: ProfileLoader, tmp_path: Path
    ) -> None:
        """Loads a file at an arbitrary path."""
        path = tmp_path / "somewhere" / "custom.yaml"
        path.parent.mkdir()
        path.write_text("name: custom\nrisk_percent: 1.0\n")
        profile = loader.load_profile_from_file(path)
        assert profile.name == "custom"

    def test_missing_file_raises(
        self, loader: ProfileLoader, tmp_path: Path
    ) -> None:
        with pytest.raises(ProfileNotFoundError):
            loader.load_profile_from_file(tmp_path / "missing.yaml")


# =============================================================================
# load_all_profiles
# =============================================================================


class TestLoadAllProfiles:
    """Tests for bulk loading."""

    def test_loads_all(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """Every well-formed file is loaded into the result dict."""
        write_yaml(
            profiles_dir / "a.yaml",
            "name: a\nrisk_percent: 0.5\n",
        )
        write_yaml(
            profiles_dir / "b.yaml",
            "name: b\nrisk_percent: 1.5\n",
        )
        result = loader.load_all_profiles()
        assert set(result.keys()) == {"a", "b"}
        assert result["a"].risk_percent == 0.5
        assert result["b"].risk_percent == 1.5

    def test_skips_bad_files(
        self, loader: ProfileLoader, profiles_dir: Path
    ) -> None:
        """One bad file doesn't block the rest."""
        write_yaml(
            profiles_dir / "good.yaml",
            "name: good\nrisk_percent: 1.0\n",
        )
        write_yaml(profiles_dir / "bad.yaml", "name: bad\nrisk_percent: -1\n")
        result = loader.load_all_profiles()
        assert "good" in result
        assert "bad" not in result


# =============================================================================
# Integration: sample profiles on disk
# =============================================================================


class TestBundledProfiles:
    """Smoke tests for the repo's bundled trading_profiles/ files."""

    def test_bundled_profiles_load(self) -> None:
        """All bundled profiles load and validate cleanly."""
        repo_root = Path(__file__).resolve().parent.parent
        loader = ProfileLoader(profiles_dir=repo_root / "trading_profiles")
        profiles = loader.load_all_profiles()
        expected = {"conservative", "moderate", "aggressive", "scalping"}
        assert expected.issubset(profiles.keys())

        # Relative risk ordering: conservative < moderate < aggressive
        assert profiles["conservative"].risk_percent < profiles["moderate"].risk_percent
        assert profiles["moderate"].risk_percent < profiles["aggressive"].risk_percent
        # Conservative tightest R/R requirement
        assert (
            profiles["conservative"].min_risk_reward_ratio
            >= profiles["moderate"].min_risk_reward_ratio
        )
