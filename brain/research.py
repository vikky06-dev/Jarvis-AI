"""Research module: information gathering and documentation.

Uses the browser to search the web, extracts content from results,
and summarizes findings. Results are saved to a file in the user's
Documents folder.
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path

from config import settings


def search_web(query: str) -> str:
    """Search Google and return the top result snippets."""
    from control.browser import _get_driver, navigate
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver = _get_driver()
    url = "https://www.google.com/search?q=" + re.sub(r'\s', '+', query)
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
    except Exception:
        pass

    snippets = []
    try:
        # Google search results are in divs with class "BNeawe" or similar
        result_divs = driver.find_elements(
            By.XPATH, '//div[@data-fa-i] | //div[contains(@class, "BNeawe")]/span'
        )
        for div in result_divs[:5]:
            text = div.text.strip()
            if text and len(text) > 10:
                snippets.append(text)
    except Exception:
        pass

    if snippets:
        return f"Here's what I found for '{query}': " + "; ".join(snippets[:3])
    return f"I couldn't find specific results for '{query}'"


def summarize_topic(topic: str) -> str:
    """Research a topic: search the web, collect snippets, and return a summary.

    If Ollama is available, uses LLM summarization; otherwise returns raw snippets.
    """
    from brain.interpreter import _llm_parse
    from brain.memory import memory

    # First, search the web
    search_result = search_web(topic)

    # Check if we have LLM available for summarization
    try:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)

        # Recall any prior research on this topic from memory
        prior = memory.recall_relevant(topic, top_k=3)
        context = f"Prior knowledge: {prior}\n\nSearch results: {search_result}"

        resp = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a research assistant. Summarize the following search results "
                    "into a concise, informative summary. Include the most important facts."
                )},
                {"role": "user", "content": f"Topic: {topic}\n\n{context}"},
            ],
            options={"temperature": 0.3, "num_predict": 500},
        )
        summary = resp["message"]["content"].strip()

        # Store the research in long-term memory
        memory.store_fact(f"Research: {topic} — {summary[:500]}")

        return summary
    except Exception:
        # No LLM — return raw search results
        memory.store_fact(f"Research: {topic} — {search_result[:500]}")
        return search_result


def save_research(topic: str, filename: str = None) -> str:
    """Research a topic and save the result to a text file in Documents."""
    summary = summarize_topic(topic)

    # Default filename from topic
    if not filename:
        safe = re.sub(r'[^\w\s-]', '', topic).strip().lower()[:40]
        filename = re.sub(r'[\s]+', '_', safe) + "_notes.txt"
    if not filename.endswith(".txt"):
        filename += ".txt"

    docs = Path.home() / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    filepath = docs / filename
    filepath.write_text(
        f"Topic: {topic}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 60}\n\n"
        f"{summary}\n",
        encoding="utf-8",
    )

    from brain.memory import memory
    memory.store_fact(f"Saved research: {topic} -> {filepath}")

    return f"Research saved to {filepath.name}"


def find_info(query: str) -> str:
    """Quick lookup: search and return a one-line answer."""
    from brain.interpreter import _llm_parse

    search_result = search_web(query)
    try:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)
        resp = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": (
                    "Answer the user's question in one concise sentence using the "
                    "search results. If no relevant info, say you couldn't find it."
                )},
                {"role": "user", "content": f"Q: {query}\n\nResults: {search_result}"},
            ],
            options={"temperature": 0.0, "num_predict": 200},
        )
        return resp["message"]["content"].strip()
    except Exception:
        return search_result


if __name__ == "__main__":
    print(research_web("what is quantum computing")[:200])


# Re-export for test compatibility
def research_web(query: str) -> str:
    """Alias for search_web used in tests."""
    return search_web(query)
