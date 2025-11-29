"""Simple Groq test script.

Usage:
  export GROQ_API_KEY=...
  export GROQ_API_URL=https://api.groq.com/openai/v1
  python3 scripts/groq_test.py
"""
import os
import json

def main():
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    GROQ_API_URL = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1")

    if not GROQ_API_KEY:
        print("Please set GROQ_API_KEY in your environment")
        raise SystemExit(2)

    prompt = "Explain the importance of fast language models"

    try:
        # Try official OpenAI Python SDK if installed
        from openai import OpenAI
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_API_URL)
        resp = client.responses.create(model="openai/gpt-oss-20b", input=prompt)
        # Try to extract output_text
        out = getattr(resp, "output_text", None)
        if out is None:
            # if it's a dict-like
            try:
                d = dict(resp)
                out = d.get("output_text") or d.get("output") or json.dumps(d)
            except Exception:
                out = str(resp)
        print(out)
    except Exception:
        # Fallback to requests
        import requests

        endpoint = GROQ_API_URL.rstrip("/") + "/responses"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": "openai/gpt-oss-20b", "input": prompt}
        r = requests.post(endpoint, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        out = data.get("output_text") or data.get("output") or data.get("result") or json.dumps(data)
        print(out)


if __name__ == '__main__':
    main()
