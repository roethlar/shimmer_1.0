import os

try:
    from openai import OpenAI
except Exception as e:
    print("FATAL: openai SDK not installed. Install `openai`.")
    print(f"Details: {e}")
    raise SystemExit(1)


def list_models():
    """Lists available models from the OpenAI API (or compatible endpoint).

    Respects OPENAI_BASE_URL if set, otherwise uses the default api.openai.com.
    Prints one model id per line.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("FATAL: OPENAI_API_KEY environment variable not set.")
        print("Please set your API key to run this script.")
        raise SystemExit(1)

    try:
        base = os.environ.get("OPENAI_BASE_URL")  # optional override
        client = OpenAI(base_url=base) if base else OpenAI()
        print("Available OpenAI models:")
        print("---")
        # The API returns a list; we print ids. No filtering due to limited metadata.
        for m in client.models.list().data:
            mid = getattr(m, "id", None) or getattr(m, "model", None) or str(m)
            if mid:
                print(mid)
        print("---")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    list_models()

