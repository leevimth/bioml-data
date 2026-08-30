"""Symlink-safe filesystem primitives for artifact cache boundaries."""

import os
import stat
from collections.abc import Generator
from contextlib import contextmanager
from enum import StrEnum, unique
from pathlib import Path
from typing import BinaryIO, final, override


@unique
class ArtifactPathFailure(StrEnum):
    """Internal path failure classification for public error translation."""

    SYMLINK = "symlink"
    IO = "io"


@final
class ArtifactPathIntegrityError(Exception):
    """Raised when a cache path is aliased or cannot be opened safely."""

    __slots__ = ("failure", "path")

    failure: ArtifactPathFailure
    path: Path

    def __init__(self, path: Path, failure: ArtifactPathFailure) -> None:
        super().__init__(path, failure)
        self.path = path
        self.failure = failure

    @override
    def __str__(self) -> str:
        return f"unsafe artifact path {self.path}: {self.failure}"


def ensure_no_symlink_components(path: Path) -> None:
    """Reject symlinks in every existing component of a lexical absolute path."""
    absolute = path.absolute()
    for component in (*reversed(absolute.parents), absolute):
        try:
            status = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ArtifactPathIntegrityError(
                path=component,
                failure=ArtifactPathFailure.IO,
            ) from error
        if stat.S_ISLNK(status.st_mode):
            raise ArtifactPathIntegrityError(
                path=component,
                failure=ArtifactPathFailure.SYMLINK,
            )


@contextmanager
def open_binary_nofollow(path: Path) -> Generator[BinaryIO]:
    """Open a regular file through pinned, non-symlink directory descriptors."""
    ensure_no_symlink_components(path)
    parent_descriptor = _open_directory_nofollow(path.absolute().parent)
    try:
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW,
            dir_fd=parent_descriptor,
        )
    except OSError as error:
        raise ArtifactPathIntegrityError(
            path=path,
            failure=ArtifactPathFailure.IO,
        ) from error
    finally:
        os.close(parent_descriptor)
    try:
        with os.fdopen(descriptor, "rb") as source:
            yield source
    except OSError as error:
        raise ArtifactPathIntegrityError(
            path=path,
            failure=ArtifactPathFailure.IO,
        ) from error


def publish_directory_nofollow(source: Path, destination: Path) -> None:
    """Atomically publish a directory through pinned parent descriptors."""
    ensure_no_symlink_components(source)
    ensure_no_symlink_components(destination.parent)
    source_parent = _open_directory_nofollow(source.absolute().parent)
    try:
        destination_parent = _open_directory_nofollow(
            destination.absolute().parent,
        )
    except ArtifactPathIntegrityError:
        os.close(source_parent)
        raise
    try:
        os.rename(
            source.name,
            destination.name,
            src_dir_fd=source_parent,
            dst_dir_fd=destination_parent,
        )
    except FileExistsError:
        raise
    except OSError as error:
        raise ArtifactPathIntegrityError(
            path=destination,
            failure=ArtifactPathFailure.IO,
        ) from error
    finally:
        os.close(destination_parent)
        os.close(source_parent)


def _open_directory_nofollow(path: Path) -> int:
    absolute = path.absolute()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as error:
        raise ArtifactPathIntegrityError(
            path=path,
            failure=ArtifactPathFailure.IO,
        ) from error
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as error:
        os.close(descriptor)
        raise ArtifactPathIntegrityError(
            path=path,
            failure=ArtifactPathFailure.IO,
        ) from error
    return descriptor
