import runpy
from unittest.mock import AsyncMock, patch


def test_main_world_cup_runs_world_cup_pipeline():
    with (
        patch("src.pipeline.run_pipeline", new_callable=AsyncMock) as mock_run_pipeline,
        patch("src.config.get_config", return_value={"config": "value"}),
    ):
        runpy.run_path("main_world_cup.py", run_name="__main__")

    mock_run_pipeline.assert_awaited_once_with(
        mode="world_cup",
        config={"config": "value"},
    )
