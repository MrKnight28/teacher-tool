"""Outside services, one module each. Every request to a provider lives here; the rest of the app calls these functions.

http.py: the shared request helpers. openrouter.py: text and vision (pay per token). openai.py and gemini.py: speech
(openai is paid, gemini is free on its free tier). claude_cli.py: the Claude Pro/Max subscription through Claude Code.
"""
