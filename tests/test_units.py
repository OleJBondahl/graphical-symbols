from symdef.units import DEFAULT_MODULE_MM, GRID_DIVISION, on_grid, snap


def test_constants():
    assert DEFAULT_MODULE_MM == 2.5
    assert GRID_DIVISION == 0.125


def test_snap_rounds_to_nearest_eighth():
    assert snap(0.1) == 0.125
    assert snap(0.06) == 0.0
    assert snap(-0.3) == -0.25
    assert snap(1.0) == 1.0


def test_on_grid():
    assert on_grid(0.375)
    assert on_grid(-2.0)
    assert not on_grid(0.3)
    assert on_grid(0.3, tol=0.1)
