from typing import List
from pathlib import Path
from prompting.caller import load_openai_caller, ChatHistory, InferenceConfig
from slist import Slist
import asyncio
import nest_asyncio
import json
nest_asyncio.apply()



async def evaluate_step_openai(steps: List[str], system_prompt: str, user_prompt: str, model_name: str = "gpt-4o-mini"):
    """
    Uses API call to evaluate if a step is successful or not
    """
    cache_path = Path("cache")
    cache_path.mkdir(parents=True, exist_ok=True)

    caller = load_openai_caller(cache_path=cache_path)
    prompts = [
        ChatHistory.from_system(system_prompt)
        .add_user(user_prompt.format(step=step))
        for step in steps
    ]
    config = InferenceConfig(model=model_name, temperature=0.0, max_tokens=2048)
    results = await Slist(prompts).par_map_async(
        lambda prompt: caller.call(prompt, config),
        max_par=50,
        tqdm=True,
    )
    result_strings = [result.first_response for result in results]
    return result_strings

def call_evaluate_steps(steps, system_prompt: str, user_prompt: str, model_name: str = "gpt-4o-mini"):
    try:
        try:
            results = asyncio.get_event_loop().run_until_complete(
                evaluate_step_openai(steps, system_prompt, user_prompt, model_name=model_name)
            )
        except RuntimeError:
            results = asyncio.run(evaluate_step_openai(steps))
    except Exception as e:
        print(f"[Warning] evaluate_step_openai failed: {e}")
        results = ["" for _ in steps]

    return results

def extract_status_codes(item):
    statuses = []
    item = json.loads(item)
    item = item.get("spans", [])
    def recurse_spans(spans):
        for span in spans:
            statuses.append({
                "status_code": span.get("status_code"),
                "status_message": span.get("status_message")
            })
            # recurse into child spans
            child_spans = span.get("child_spans", [])
            if child_spans:
                recurse_spans(child_spans)

    recurse_spans(item)
    return statuses

def extract_output_values(trace):
    results = []

    def recurse(span):
        if isinstance(span, dict):
            if "output.value" in span:
                results.append(str(span["output.value"]))
            for v in span.values():
                recurse(v)
        elif isinstance(span, list):
            for item in span:
                recurse(item)

    recurse(trace)
    return results
