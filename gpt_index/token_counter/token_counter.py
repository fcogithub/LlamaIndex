"""Token counter function."""

from typing import Any, Callable, cast

from gpt_index.langchain_helpers.chain_wrapper import LLMPredictor


def llm_token_counter(method_name_str: str) -> Callable:
    """
    Use this as a decorator for methods in index/query classes that make calls to LLMs.

    At the moment, this decorator can only be used on class instance methods with a
    `_llm_predictor` attribute.

    Do not use this on abstract methods.

    For example, consider the class below:
        .. code-block:: python
            class GPTTreeIndexBuilder:
            ...
            @llm_token_counter("build_from_text")
            def build_from_text(self, documents: Sequence[BaseDocument]) -> IndexGraph:
                ...

    If you run `build_from_text()`, it will print the output in the form below:

    ```
    [build_from_text] Total token usage: <some-number> tokens
    ```
    """

    def wrap(f: Callable) -> Callable:
        def wrapped_llm_predict(_self: Any, *args: Any, **kwargs: Any) -> Any:
            llm_predictor = getattr(_self, "_llm_predictor", None)
            if llm_predictor is None:
                raise ValueError(
                    "Cannot use llm_token_counter on an instance without a _llm_predictor attribute."
                )
            llm_predictor = cast(LLMPredictor, llm_predictor)

            start_token_ct = llm_predictor.total_tokens_used
            f_return_val = f(_self, *args, **kwargs)
            net_tokens = llm_predictor.total_tokens_used - start_token_ct
            llm_predictor.last_token_usage = net_tokens
            print(f"> [{method_name_str}] Total token usage: {net_tokens} tokens")

            return f_return_val

        return wrapped_llm_predict

    return wrap
