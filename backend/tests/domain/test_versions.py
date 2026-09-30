from review_radar.domain.versions import (
    normalize_version,
    previous_version,
    sort_versions,
    version_key,
)


def test_version_key_pads_and_ignores_build_suffix() -> None:
    assert version_key("2.3") == (2, 3, 0)
    assert version_key("v2.3.1 (412)") == (2, 3, 1)
    assert version_key("beta") == ()


def test_sort_is_numeric_not_lexical() -> None:
    assert sort_versions(["2.10.0", "2.9.0", "2.9.0", "junk", "2.3.1"]) == [
        "2.3.1",
        "2.9.0",
        "2.10.0",
    ]


def test_previous_version() -> None:
    versions = ["2.1.0", "2.3.0", "2.2.0", "2.3.1"]
    assert previous_version(versions, "2.3.1") == "2.3.0"
    assert previous_version(versions, "2.1.0") is None


def test_normalize_version() -> None:
    assert normalize_version("2.3.1 (412)") == "2.3.1"
    assert normalize_version(None) is None
    assert normalize_version("n/a") is None
