from playwright.sync_api import sync_playwright
from openai import OpenAI
import json
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- SCRAPER ----------
def scrape_sections(url):
    """Scrape headers and paragraphs from a wiki personality page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        content = page.query_selector("div.mw-parser-output")
        children = content.query_selector_all("h2, h3, p")

        sections = {}
        current_header = None
        buffer = []

        for child in children:
            tag = child.evaluate("el => el.tagName")
            text = child.inner_text().strip()

            if tag in ["H2", "H3"]:
                if current_header and buffer:
                    sections[current_header] = " ".join(buffer).strip()
                current_header = text.replace("[edit]", "").strip()
                buffer = []
            elif tag == "P" and current_header:
                buffer.append(text)

        if current_header and buffer:
            sections[current_header] = " ".join(buffer).strip()

        browser.close()
        return sections


# ---------- SUMMARIZER ----------
def summarize_personalities_and_relationships(name, raw_text):
    """Use GPT to summarize personality into traits + quirks."""
    prompt = f"""
    Summarize {name}'s personality based on the text below.
    1. Write a comprehensive paragraph describing {name}'s personality and relationships.
    2. Provide 2-3 nuances/quirks (unique habits, speech patterns, behaviors).

    Text:
    {raw_text}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def reduce_summary_one_trait(name, summary):
    """Use GPT to summarize personality into traits + quirks."""
    prompt = f"""
    Summarize {name}'s personality - {summary} based on the text below.
    Reduce it to strictly three words that completely describe the character.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ---------- MAIN PIPELINE ----------
if __name__ == "__main__":
    STRAW_HATS = {
        "Monkey D. Luffy": "https://onepiece.fandom.com/wiki/Monkey_D._Luffy/Personality",
        "Roronoa Zoro": "https://onepiece.fandom.com/wiki/Roronoa_Zoro/Personality_and_Relationships",
        "Usopp": "https://onepiece.fandom.com/wiki/Usopp/Personality_and_Relationships",
        "Nami": "https://onepiece.fandom.com/wiki/Nami/Personality_and_Relationships",
        "Sanji": "https://onepiece.fandom.com/wiki/Sanji/Personality",
        "Tony Tony Chopper": "https://onepiece.fandom.com/wiki/Tony_Tony_Chopper/Personality_and_Relationships",
        "Nico Robin": "https://onepiece.fandom.com/wiki/Nico_Robin/Personality_and_Relationships",
        "Franky": "https://onepiece.fandom.com/wiki/Franky/Personality_and_Relationships",
        "Brook": "https://onepiece.fandom.com/wiki/Brook/Personality_and_Relationships",
        "Jinbe": "https://onepiece.fandom.com/wiki/Jinbe/Personality_and_Relationships",
    }

    crew_data = []

    for name, url in STRAW_HATS.items():
        print(f"\n🔎 Scraping {name}...")
        sections = scrape_sections(url)

        if not sections:
            print(f"⚠️ No sections found for {name}")
            continue

        # join all sections as raw text
        personality_text = "\n".join(sections.values())

        print(f"✍ Summarizing {name}...")
        summary = summarize_personalities_and_relationships(name, personality_text)
        print("Character traits")
        trait = reduce_summary_one_trait(name, summary)
        crew_data.append({
            "name": name,
            "url": url,
            "raw_text": personality_text,
            "summary": summary,
            "trait": trait
        })

    # Save JSON
    with open("strawhat_personalities.json", "w", encoding="utf-8") as f:
        json.dump(crew_data, f, indent=2, ensure_ascii=False)

    # Save Markdown
    with open("strawhat_personalities.md", "w", encoding="utf-8") as f:
        for c in crew_data:
            f.write(f"# {c['name']}\n")
            f.write(f"**Source:** {c['url']}\n\n")
            f.write(c['summary'] + "\n\n---\n\n")

    print("✅ Done! Personalities saved to JSON + Markdown.")
