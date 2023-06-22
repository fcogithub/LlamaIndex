"""Async utils."""
import asyncio
from typing import Any, Coroutine, List
import nest_asyncio


def run_async_tasks(
    tasks: List[Coroutine],
    show_progress: bool = False,
    progress_bar_desc: str = "Running async tasks",
) -> List[Any]:
    """Run a list of async tasks."""

    # jupyter notebooks already have an event loop running
    # we need to reuse it instead of creating a new one
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()

    tasks_to_execute: List[Any] = tasks
    if show_progress:
        try:
            from tqdm.asyncio import tqdm

            async def _tqdm_gather() -> List[Any]:
                return await tqdm.gather(*tasks_to_execute, desc=progress_bar_desc)

            tqdm_outputs: List[Any] = loop.run_until_complete(_tqdm_gather())
            return tqdm_outputs
        # run the operation w/o tqdm on hitting a fatal
        # may occur in some environments where tqdm.asyncio
        # is not supported
        except Exception:
            pass

    async def _gather() -> List[Any]:
        return await asyncio.gather(*tasks_to_execute)

    outputs: List[Any] = loop.run_until_complete(_gather())
    return outputs
