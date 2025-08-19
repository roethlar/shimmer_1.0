import os


def list_models():
    """Lists available models from the Anthropic API.

    Requires ANTHROPIC_API_KEY. Prints one model id per line.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("FATAL: ANTHROPIC_API_KEY environment variable not set.")
        print("Please set your API key to run this script.")
        raise SystemExit(1)

    try:
        import anthropic  # type: ignore
    except Exception as e:
        print("FATAL: anthropic SDK not installed. Install `anthropic`. ")
        print(f"Details: {e}")
        raise SystemExit(1)

    try:
        client = anthropic.Anthropic()
        print("Available Anthropic models:")
        print("---")
        # SDK returns a .data list with model resources
        for m in client.models.list().data:
            mid = getattr(m, "id", None) or str(m)
            if mid:
                print(mid)
        print("---")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    list_models()

