
import google.generativeai as genai
import os


def list_models():
    """Lists the available models from the Google Generative AI API."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FATAL: GOOGLE_API_KEY environment variable not set.")
        print("Please set your API key to run this script.")
        exit(1)

    try:
        genai.configure(api_key=api_key)
        print("Available Gemini models that support content generation:")
        print("---")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name)
        print("---")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    list_models()
