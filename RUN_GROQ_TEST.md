Run this Groq/OpenAI-compatible test script (Node ESM)

1. Install Node dependencies (use node 18+):

```bash
npm install openai
```

2. Export your Groq API key in the environment:

```bash
export GROQ_API_KEY="your_groq_key_here"
```

3. Run the script:

```bash
node groq_test.mjs
```

Notes:
- The Groq service is OpenAI-compatible but model names and response shapes may differ. If you get a `model_not_found` error, check your Groq Console for available models and replace `model` in `groq_test.mjs`.
- The script prints the full response and attempts to print the most common text fields.
