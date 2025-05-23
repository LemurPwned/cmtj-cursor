# from anthropic import AnthropicVertex
from openai import OpenAI
import os
import logging
import json
from datetime import datetime

# Configure logging
log_directory = os.getenv("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(
    log_directory, f"llm_calls_{datetime.now().strftime('%Y%m%d')}.log"
)

# Set up logger
logger = logging.getLogger("llm_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

# Simple cache configuration
cache_file = "llm_cache.json"


# Learn more about calling the LLM: https://the-pocket.github.io/PocketFlow/utility_function/llm.html
def call_llm(prompt: str, use_cache: bool = True) -> str:
    # Log the prompt
    logger.info(f"PROMPT: {prompt}")

    # Check cache if enabled
    if use_cache:
        # Load cache from disk
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cache = json.load(f)
            except:
                logger.warning(f"Failed to load cache, starting with empty cache")

        # Return from cache if exists
        if prompt in cache:
            logger.info(f"Cache hit for prompt: {prompt[:50]}...")
            return cache[prompt]

    # Call the LLM if not in cache or cache disabled
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    MODEL_DEFAULTS = {
        "model": "o4-mini",  # 200,000 token context window
        "reasoning": {
            "effort": "low",
            "summary": "auto",
        },  # Automatically summarise the reasoning process. Can also choose "detailed" or "none"
    }
    response = client.responses.create(
        input=prompt,
        **MODEL_DEFAULTS,
    )
    response_text = response.output_text

    # Log the response
    logger.info(f"RESPONSE: {response_text}")

    # Update cache if enabled
    if use_cache:
        # Load cache again to avoid overwrites
        cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cache = json.load(f)
            except:
                pass

        # Add to cache and save
        cache[prompt] = response_text
        try:
            with open(cache_file, "w") as f:
                json.dump(cache, f)
            logger.info(f"Added to cache")
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
