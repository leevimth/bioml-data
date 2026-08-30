"""Public package smoke tests."""

from importlib.metadata import version

import bioml_data


def test_public_version_matches_installed_metadata() -> None:
    # Given: bioml-data is installed in the test environment.
    installed_version = version("bioml-data")

    # When: a consumer imports the package version.
    public_version = bioml_data.__version__

    # Then: the public value identifies the installed distribution.
    assert public_version == installed_version
