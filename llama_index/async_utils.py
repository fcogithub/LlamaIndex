"""Async utils."""
import asyncio
from itertools import zip_longest
from typing import Any, Coroutine, Iterable, List, Awaitable, Callable, TypeVar

T = TypeVar('T')
AsyncCallable = Callable[..., Awaitable[T]]

def run_async_tasks(
    tasks: List[Coroutine],
    show_progress: bool = False,
    progress_bar_desc: str = "Running async tasks",
) -> List[Any]:
    """Run a list of async tasks."""

    tasks_to_execute: List[Any] = tasks
    if show_progress:
        try:
            import nest_asyncio
            from tqdm.asyncio import tqdm

            # jupyter notebooks already have an event loop running
            # we need to reuse it instead of creating a new one
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()

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

    outputs: List[Any] = asyncio.run(_gather())
    return outputs


def chunks(iterable: Iterable, size: int) -> Iterable:
    args = [iter(iterable)] * size
    return zip_longest(*args, fillvalue=None)


async def batch_gather(
    tasks: List[Coroutine], batch_size: int = 10, verbose: bool = False
) -> List[Any]:
    output: List[Any] = []
    for task_chunk in chunks(tasks, batch_size):
        output_chunk = await asyncio.gather(*task_chunk)
        output.extend(output_chunk)
        if verbose:
            print(f"Completed {len(output)} out of {len(tasks)} tasks")
    return output

def run_sync(awaitable: Awaitable[T]) -> T:
    """
    Run an awaitable synchronously.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(awaitable)


def patch_sync(func_async: AsyncCallable[T]) -> Callable[..., T]:
    """
    Given an async function, return a sync function that runs the async function.
    """
    def patched_sync(*args: Any, **kwargs: Any) -> T:
        return run_sync(func_async(*args, **kwargs))

    return patched_sync
