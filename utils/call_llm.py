# from anthropic import AnthropicVertex
import json
import os
from datetime import datetime

from loguru import logger
from openai import OpenAI

# Configure logging
log_directory = os.getenv("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(log_directory, f"llm_calls_{datetime.now().strftime('%Y%m%d')}.log")
logger.add(log_file, level="DEBUG")

# Simple cache configuration
cache_file = "llm_cache.json"


# Learn more about calling the LLM: https://the-pocket.github.io/PocketFlow/utility_function/llm.html
def call_llm(prompt: str, use_cache: bool = True, model: str = "o4-mini") -> str:
    # Log the prompt
    # logger.debug(f"PROMPT: {prompt}")

    # Check cache if enabled
    if use_cache:
        # Load cache from disk
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")
                logger.warning("Failed to load cache, starting with empty cache")

        # Create cache key that includes the model to avoid cross-model cache hits
        cache_key = f"{model}:{prompt}"
        # Return from cache if exists
        if cache_key in cache:
            logger.info(f"Cache hit for prompt: {prompt[:50]}... with model: {model}")
            return cache[cache_key]

    # Call the LLM if not in cache or cache disabled
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Determine model configuration based on the selected model
    if model.startswith("o4"):
        # OpenAI o4 models use the responses API
        MODEL_DEFAULTS = {
            "model": model,
            "reasoning": {
                "effort": "low",
                "summary": "auto",
            },
        }
        response = client.responses.create(
            input=prompt,
            **MODEL_DEFAULTS,
        )
        response_text = response.output_text
    else:
        # Other models use the chat completions API
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        response_text = response.choices[0].message.content

    # Log the response
    logger.debug(f"RESPONSE: {response_text}")

    # Update cache if enabled
    if use_cache:
        # Load cache again to avoid overwrites
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache = json.load(f)
            except Exception:
                pass

        # Add to cache and save with model-specific key
        cache_key = f"{model}:{prompt}"
        cache[cache_key] = response_text
        try:
            with open(cache_file, "w") as f:
                json.dump(cache, f)
            logger.info(f"Added to cache with model: {model}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    return response_text


def clear_cache() -> None:
    """Clear the cache file if it exists."""
    if os.path.exists(cache_file):
        os.remove(cache_file)
        logger.info("Cache cleared")


if __name__ == "__main__":
    test_prompt = "Hello, how are you?"

    # First call - should hit the API
    print("Making first call...")
    response1 = call_llm(test_prompt, use_cache=False)
    print(f"Response: {response1}")

    # Second call - should hit cache
    print("\nMaking second call with same prompt...")
    response2 = call_llm(test_prompt, use_cache=True)
    print(f"Response: {response2}")
