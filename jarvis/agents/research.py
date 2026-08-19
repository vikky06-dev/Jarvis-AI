"""Research agent — performs web research and compiles reports.

Performs:
- Web searches using Google
- Reads and extracts information from web pages
- Compiles structured research reports
- Saves reports as text files
"""

import urllib.parse
import time
from datetime import datetime
from pathlib import Path

from config import settings
from core import state as core_state
from control.browser import _get_driver, navigate, search_google, read_page
from files.manager import create_file, search_file
import pyautogui


def _search_and_extract(query: str, num_results: int = 3) -> list[dict]:
    """Perform a Google search and extract information from results."""
    results = []

    try:
        # Perform search
        d = _get_driver()
        d.get(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        time.sleep(2)

        # Extract search results
        from selenium.webdriver.common.by import By
        try:
            # Find all result containers
            result_containers = d.find_elements(By.CSS_SELECTOR, ".g")

            for i, container in enumerate(result_containers[:num_results]):
                try:
                    # Extract title
                    title_element = container.find_element(By.CSS_SELECTOR, "h3")
                    title = title_element.text

                    # Extract URL
                    link_element = container.find_element(By.CSS_SELECTOR, "a")
                    url = link_element.get_attribute("href")

                    # Extract snippet
                    snippet_element = container.find_element(By.CSS_SELECTOR, ".VwiC3b, .s3v9rd")
                    snippet = snippet_element.text

                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
                except Exception:
                    # Skip this result if we can't extract data
                    continue

        except Exception:
            pass

    except Exception as e:
        print(f"[research] Search failed: {e}")

    return results


def _read_webpage(url: str) -> str:
    """Read content from a webpage."""
    try:
        d = _get_driver()
        d.get(url)
        time.sleep(2)

        # Try to get the main content
        from selenium.webdriver.common.by import By
        try:
            # Try common content selectors
            selectors = [
                "article",
                ".content",
                "#content",
                ".post-content",
                ".entry-content",
                "main",
                ".main-content"
            ]

            for selector in selectors:
                try:
                    element = d.find_element(By.CSS_SELECTOR, selector)
                    return element.text[:1000]  # Limit to first 1000 chars
                except NoSuchElementException:
                    continue

            # Fallback to body text
            body = d.find_element(By.TAG_NAME, "body")
            return body.text[:1000]
        except Exception:
            return "Could not extract webpage content"

    except Exception as e:
        return f"Failed to read webpage: {str(e)}"


def research_topic(topic: str) -> str:
    """Research a topic and return a structured report."""
    try:
        # Search for the topic
        search_results = _search_and_extract(topic, num_results=5)

        if not search_results:
            return f"I couldn't find any information about {topic}"

        # Read content from top results
        detailed_info = []
        for result in search_results[:3]:  # Top 3 results
            content = _read_webpage(result["url"])
            detailed_info.append({
                "title": result["title"],
                "url": result["url"],
                "content": content
            })

        # Generate report
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"""RESEARCH REPORT: {topic}
========================================
Date: {timestamp}

SUMMARY OF FINDINGS
------------------
"""

        for i, info in enumerate(detailed_info, 1):
            report += f"{i}. {info['title']}\n"
            report += f"   Source: {info['url']}\n"
            report += f"   Summary: {info['content'][:200]}...\n\n"

        report += """DETAILED INFORMATION
-------------------
"""

        for i, info in enumerate(detailed_info, 1):
            report += f"{i}. {info['title']}\n"
            report += f"   Source: {info['url']}\n"
            report += f"   Content:\n{info['content']}\n\n"

        report += f"""END OF REPORT
========================================
Research conducted using web search and content extraction.
"""

        return report

    except Exception as e:
        return f"Research failed: {str(e)}"


def save_research_report(topic: str, file_path: str = None) -> str:
    """Research a topic and save the report to a file."""
    # Perform research
    report = research_topic(topic)

    if report.startswith("I couldn't find") or report.startswith("Research failed"):
        return report

    # Determine file path
    if not file_path:
        # Auto-generate filename from topic
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_topic = safe_topic.replace(' ', '_')
        if not safe_topic:
            safe_topic = "research_report"
        file_path = f"{safe_topic}.txt"

    # Ensure .txt extension
    if not file_path.lower().endswith('.txt'):
        file_path += '.txt'

    try:
        # Create the file
        result = create_file(file_path, "Documents")
        if "Created file" in result:
            # Write the report to the file
            from agents import notepad
            notepad.open_file(file_path)
            time.sleep(1)
            notepad.write_text(report)
            notepad.save_file()
            return f"Research report saved as {file_path}"
        else:
            return f"Failed to create file: {result}"
    except Exception as e:
        return f"Failed to save research report: {str(e)}"


if __name__ == "__main__":
    # For testing
    print("Research agent loaded")