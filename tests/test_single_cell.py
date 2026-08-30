"""Canonical single-cell schema boundary tests."""

import pytest

from bioml_data._single_cell import MatrixShape, SparseCountMatrix, SparseFormat
from bioml_data._single_cell_errors import (
    InvalidSparseMatrixError,
    SparseMatrixViolation,
)


def test_csr_rejects_duplicate_row_column_coordinates() -> None:
    # Given: structurally aligned CSR arrays repeating one column within a row.

    # When: the canonical sparse matrix boundary parses the arrays.
    with pytest.raises(InvalidSparseMatrixError) as captured:
        _ = SparseCountMatrix(
            format=SparseFormat.CSR,
            shape=MatrixShape(observations=1, features=2),
            values=(2, 3),
            column_indices=(0, 0),
            row_offsets=(0, 2),
        )

    # Then: duplicate coordinates are rejected explicitly.
    assert captured.value.violation is SparseMatrixViolation.DUPLICATE_COORDINATE
