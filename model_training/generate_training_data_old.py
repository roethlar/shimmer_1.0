import subprocess
import os
import json
import openai
import google.generativeai as genai
import argparse

# --- Configuration ---
PROMPTS_FILE = "prompts.txt"
TRAINING_FILE = "training_data.jsonl"

# --- LLM Configuration ---
# Supported providers: "openai", "google"
LLM_PROVIDER = "google"
LLM_MODEL = "models/gemini-1.5-pro-latest"

# --- System Prompts ---
EN2SH_SYSTEM_PROMPT = """You are a protocol agent. Your ONLY task is to convert an English request into a single-line Shimmer text message that complies with Shimmer Specification v1.0.

**RULES:**
- The output MUST be a single line.
- The output format MUST be exactly: <routing><action><metadata><temporal><deliverables>→<vector>
- **Routing:** The <routing> part MUST be exactly two characters (e.g., 'AB', 'XY').
- **Action:** You MUST include an <action> code (e.g., 'p' for plan, 'a' for acknowledge).
- **Separator:** You MUST use the literal Unicode arrow '→' (U+2192), not its code point 'u2192'.
- The vector MUST have 5 dimensions.
- DO NOT output markdown, explanations, or any text other than the Shimmer string.

**Example of CORRECT output for an acknowledgement:**
XYa f07→[0.0,0.2,0.0,0.5,0.9]

Now, convert the user's input."""

SH2EN_SYSTEM_PROMPT = """You are a protocol agent. Read a Shimmer text container and vector, and produce a concise English gloss in a compact JSON object. The keys must be: routing, action, metadata, deadline_seconds, deliverables, vector_gloss, and one_paragraph_summary. Do NOT add explanations or markdown."""

def get_google_completion(user_prompt, system_prompt):
    if not os.getenv("GOOGLE_API_KEY"): exit("FATAL: GOOGLE_API_KEY not set.")
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        config = genai.types.GenerationConfig(temperature=0.1)
        model = genai.GenerativeModel(LLM_MODEL, system_instruction=system_prompt, generation_config=config)
        response = model.generate_content(user_prompt)
        return response.text.strip()
    except Exception as e:
        exit(f"FATAL: Google API error: {e}")

def get_openai_completion(user_prompt, system_prompt):
    if not os.getenv("OPENAI_API_KEY"): exit("FATAL: OPENAI_API_KEY not set.")
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_completion_tokens=200
        )
        return response.choices[0].message.content.strip()
    except openai.APIError as e:
        exit(f"FATAL: OpenAI API error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Generate Shimmer training data.")
    parser.add_argument("--test", action="store_true", help="Run with only the first prompt.")
    args = parser.parse_args()

    if not os.path.exists(PROMPTS_FILE): exit(f"Error: '{PROMPTS_FILE}' not found.")
    with open(PROMPTS_FILE, "r") as f:
        prompts = [line.strip() for line in f if line.strip()]
    
    if args.test:
        print("--- Running in Test Mode (one prompt) ---")
        prompts = prompts[:1]

    print(f"Found {len(prompts)} prompts. Using provider '{LLM_PROVIDER}' with model '{LLM_MODEL}'.")

    translations = []
    for i, prompt in enumerate(prompts):
        print(f"  Translating prompt {i+1}/{len(prompts)}...")
        if LLM_PROVIDER == "google":
            shimmer = get_google_completion(prompt, EN2SH_SYSTEM_PROMPT)
        else: # openai
            shimmer = get_openai_completion(prompt, EN2SH_SYSTEM_PROMPT)
        
        if shimmer and "u2192" in shimmer:
            shimmer = shimmer.replace("u2192", "→")
        translations.append(shimmer)

    glosses = []
    for i, shimmer in enumerate(translations):
        print(f"  Generating gloss {i+1}/{len(translations)}...")
        if LLM_PROVIDER == "google":
            gloss_str = get_google_completion(shimmer, SH2EN_SYSTEM_PROMPT)
        else: # openai
            gloss_str = get_openai_completion(shimmer, SH2EN_SYSTEM_PROMPT)
        
        if gloss_str and gloss_str.startswith("```json"):
            gloss_str = gloss_str.strip("```json\n").strip("`")
        
        try:
            gloss_json = json.loads(gloss_str)
            glosses.append(gloss_json)
        except (json.JSONDecodeError, TypeError):
            glosses.append({"error": "failed to parse gloss", "raw_output": gloss_str})

    with open(TRAINING_FILE, "w") as f:
        for prompt, shimmer in zip(prompts, translations):
            f.write(json.dumps({"messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": shimmer}]}) + "\n")
        for shimmer, gloss in zip(translations, glosses):
            f.write(json.dumps({"messages": [{"role": "user", "content": shimmer}, {"role": "assistant", "content": json.dumps(gloss)}]})) + "\n")

    print("\n---")
    print("✅ Success!")
    if args.test:
        print("Test run successful. You can now run the script without the --test flag.")
    else:
        print(f"Training data generated in '{TRAINING_FILE}'.")

if __name__ == "__main__":
    main()