import os
import json
import html
import time
import datetime
import requests
from google import genai
from google.genai.errors import APIError

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

CANDIDATE_PROFILE = """
Candidate: Gabriel Koomson
Education: Dual Major in B.S. Computer Science & Economics at Trinity College (Expected May 2027) | Study abroad coursework in ML/Databases at NYU Paris.

Technical Skills:
- Languages: Python, JavaScript/TypeScript (React, Next.js), C/C++, C# (.NET 8), Java, SQL, Bash, CUDA, OpenCL, Kotlin, Swift.
- Frameworks & Backends: FastAPI, Flask, Spring Boot, LangChain, Next.js, MSTest, Jest, SQLAlchemy.
- Cloud & Infrastructure: AWS (S3, Lambda, Aurora PostgreSQL, Secrets Manager), Azure DevOps, Docker, Kubernetes (GKE), Redis, RabbitMQ, Harbor Registry, GitHub Actions CI/CD.
- Databases & Storage: PostgreSQL, SQL Server 2022, MongoDB, ChromaDB (Vector Search), Redis.
- Core Domains: Agentic AI / LLM workflows (LangChain, Claude Code), Distributed Systems, Cloud-Native Microservices, High-Performance/Low-Level Systems, Asynchronous Orchestration, Real-Time Messaging (WebSockets, Queues).

Hands-On Experience & Proof of Work:
- AI Agents & Testing Automation: Engineered custom agentic tooling transforming Azure DevOps test plans into 100+/sprint automated test scenarios at TicketNetwork; built RAG-powered assistants with LangChain & Redis caching.
- Distributed & Real-Time Cloud Systems: Built and containerized 'BantamGo' (FastAPI, Redis, RabbitMQ, WebSockets, GKE) handling 1,000+ real-time updates/sec and multi-stage CI/CD deployments.
- Enterprise Cloud Migrations & Integrations: Validated S3/Lambda execution pipelines, Aurora PostgreSQL sync to on-prem SQL Server, and integrated third-party platforms (Stripe, Uber Direct).
- Async Systems & Open Source: Debugged and architected mock harnesses and async test coverage matrices for complex asynchronous Python workflows (ChromaDB, SQLAlchemy 2.0).

Target Startup Sectors & Roles:
- High-Fit Sectors: AI Agents & Developer Tooling, Cloud-Native Infrastructure & Microservices, Data Systems / Vector Orchestration, Fintech / API Integrations, Real-Time Systems.
- Target Roles: Software Engineering Intern / Early-Stage Founding Engineer / Full-Stack & Backend Systems Engineer.
"""

def fetch_existing_notion_records():
    """Queries Notion to get all existing company names and HN links to avoid duplicates."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        print("Warning: Notion credentials missing, skipping duplicate check.")
        return set(), set()

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY.strip()}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    existing_titles = set()
    existing_urls = set()
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
            
        try:
            res = requests.post(
                f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
                headers=headers,
                json=payload
            )
            
            if res.status_code != 200:
                print(f"Warning: Could not fetch existing Notion records: {res.text}")
                break
                
            data = res.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                
                # Extract Title
                title_list = props.get("Company", {}).get("title", [])
                if title_list:
                    title_text = title_list[0].get("text", {}).get("content", "").strip().lower()
                    existing_titles.add(title_text[:40])
                
                # Extract URL
                url = props.get("HN Link", {}).get("url")
                if url:
                    existing_urls.add(url.strip().lower())
                    
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
            
        except Exception as e:
            print(f"Error querying Notion database for duplicates: {e}")
            break
            
    return existing_titles, existing_urls

def fetch_launch_hn(days_back=14):
    """Fetches recent 'Launch HN:' posts via Algolia."""
    cutoff = int((datetime.datetime.now() - datetime.timedelta(days=days_back)).timestamp())
    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": "Launch HN:",
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff}",
        "hitsPerPage": 20
    }
    results = []
    try:
        data = requests.get(url, params=params).json()
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            if "Launch HN:" in title:
                results.append({
                    "source": "Launch HN",
                    "title": html.unescape(title.replace("Launch HN: ", "").strip()),
                    "author": hit.get("author", "Founder"),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "text": html.unescape(hit.get("story_text") or hit.get("comment_text") or title)
                })
    except Exception as e:
        print(f"Error in fetch_launch_hn: {e}")
    return results

def fetch_who_is_hiring():
    """Fetches top-level job postings from the LATEST monthly 'Ask HN: Who is hiring?' thread."""
    # Use search_by_date to guarantee we get the current month's thread
    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": "Ask HN: Who is hiring?",
        "tags": "story,author_whoishiring",
        "hitsPerPage": 1
    }
    results = []
    try:
        res = requests.get(url, params=params).json()
        hits = res.get("hits", [])
        if not hits:
            return []

        latest_thread = hits[0]
        thread_id = latest_thread.get("objectID")
        thread_title = latest_thread.get("title", "")
        print(f"Scanning latest thread: '{thread_title}' (ID: {thread_id})...")

        # Pull top comments from this thread
        comments_url = "https://hn.algolia.com/api/v1/search"
        comment_params = {
            "tags": f"comment,story_{thread_id}",
            "hitsPerPage": 15
        }
        comment_data = requests.get(comments_url, params=comment_params).json()
        
        for c in comment_data.get("hits", []):
            raw_text = c.get("comment_text", "")
            if len(raw_text) < 120:
                continue
            
            clean_text = html.unescape(raw_text)
            first_line = clean_text.split("<p>")[0].replace("&#x2F;", "/").replace("&amp;", "&").strip()
            
            # Filter out non-hiring chatter / replies
            lower_first = first_line.lower()
            if any(skip_word in lower_first for skip_word in ["interested", "thanks", "h1b", "promo", "range", "mods", "how to"]):
                continue
            
            # Legitimate company hiring comments generally contain "|" or "-" in the header
            if "|" not in first_line and " - " not in first_line:
                continue

            company_title = first_line[:80].strip()
            
            results.append({
                "source": "Who is Hiring",
                "title": company_title,
                "author": c.get("author", "Hiring Team"),
                "url": f"https://news.ycombinator.com/item?id={c.get('objectID')}",
                "text": clean_text[:1500]
            })
    except Exception as e:
        print(f"Error in fetch_who_is_hiring: {e}")
    return results

def fetch_funding_announcements(days_back=14):
    """Searches HN for recent funded startup announcements beyond YC."""
    cutoff = int((datetime.datetime.now() - datetime.timedelta(days=days_back)).timestamp())
    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": "seed round OR Series A OR raised OR seed funding",
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff}",
        "hitsPerPage": 10
    }
    results = []
    try:
        data = requests.get(url, params=params).json()
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            if any(term in title.lower() for term in ["raised", "series a", "seed round", "$"]):
                results.append({
                    "source": "Funding News",
                    "title": html.unescape(title),
                    "author": hit.get("author", "Founder"),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "text": html.unescape(hit.get("story_text") or title)
                })
    except Exception as e:
        print(f"Error in fetch_funding_announcements: {e}")
    return results

def is_candidate_potentially_relevant(item):
    """Quick heuristic filter to avoid unnecessary API calls on obvious mismatches."""
    text = (item["title"] + " " + item["text"]).lower()

    # Must have hiring or venture signals
    has_hiring = any(word in text for word in ["hiring", "engineer", "developer", "founding", "role", "team"])
    has_venture = any(word in text for word in ["raised", "series", "seed", "funded", "$", "million", "venture"])

    # Avoid clear non-matches
    bad_keywords = ["freelance", "visa", "non-tech", "sales only", "marketing", "bc2b", "b2b sales"]
    has_bad_signals = any(word in text for word in bad_keywords)

    return (has_hiring or has_venture) and not has_bad_signals

def evaluate_opportunity(client, item, max_retries=3):
    """Evaluates fit with rate-limit handling and backoff."""
    prompt = f"""
Candidate Background:
{CANDIDATE_PROFILE}

Opportunity Source: {item['source']}
Headline/Title: {item['title']}
Context/Post:
{item['text']}

Task:
1. Determine if this company is a high-growth/venture-funded startup actively building or hiring.
2. Rate Gabriel's match from 1-10 based on his skills in Python, TS/Next.js, C++, Cloud/K8s, Agents, and Real-Time Systems.
3. If fit >= 7, propose a concrete 2-hour demo project and a 1-sentence cold outreach email hook.

Respond strictly in valid JSON format:
{{
  "score": <number 1-10>,
  "funding_or_hiring_signal": "<e.g., Active Hiring / Seed Stage / Series A>",
  "fit_reason": "<1-2 sentences on why this aligns with Gabriel's tech stack>",
  "demo_idea": "<A practical micro-demo scoped strictly to 2-3 hours>",
  "email_hook": "<1-2 sentence compelling cold email hook to the founder/engineering lead>"
}}
"""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except APIError as e:
            if "429" in str(e) or "503" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_seconds = (attempt + 1) * 10
                print(f"Rate limited on '{item['title'][:30]}'. Waiting {wait_seconds}s before retry ({attempt+1}/{max_retries})...")
                time.sleep(wait_seconds)
            else:
                print(f"API Error evaluating {item['title']}: {e}")
                return None
        except Exception as e:
            print(f"Error evaluating {item['title']}: {e}")
            return None
    return None

def create_notion_page(item, analysis):
    """Adds a formatted row and CRM page into Notion."""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY.strip()}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    today = datetime.date.today().isoformat()
    raw_score = analysis.get("score", 0)
    
    try:
        score_val = float(raw_score)
    except (ValueError, TypeError):
        score_val = 0.0
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Company": {
                "title": [{"text": {"content": item["title"][:100]}}]
            },
            "Score": {
                "number": score_val
            },
            "Status": {
                "select": {"name": "New Lead"}
            },
            "Founder": {
                "rich_text": [{"text": {"content": f"@{item['author']}"}}]
            },
            "HN Link": {
                "url": item["url"]
            },
            "Date Added": {
                "date": {"start": today}
            }
        },
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": f"Source: {item['source']} | Signal: {analysis.get('funding_or_hiring_signal', 'Active Venture')}"}}],
                    "icon": {"emoji": "🚀"}
                }
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "💡 2-Hour Demo Concept"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": analysis.get("demo_idea", "")}}]}
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "✉️ Cold Outreach Pitch Hook"}}]}
            },
            {
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": analysis.get("email_hook", "")}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Match Context: {analysis.get('fit_reason', '')}"}}]}
            }
        ]
    }
    
    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    if res.status_code == 200:
        print(f"Successfully added [{item['source']}] {item['title'][:40]}... to Notion.")
    else:
        print(f"Failed to add {item['title'][:30]}: {res.text}")

def main():
    print("Checking Notion for existing leads to prevent duplicates...")
    existing_titles, existing_urls = fetch_existing_notion_records()
    print(f"Found {len(existing_titles)} existing companies in Notion tracker.")

    print("Aggregating opportunities across multiple startup feeds...")
    all_leads = []
    
    print("-> Fetching Launch HN...")
    all_leads.extend(fetch_launch_hn(days_back=14))
    
    print("-> Fetching Ask HN: Who is hiring?...")
    all_leads.extend(fetch_who_is_hiring())
    
    print("-> Fetching recent funding announcements...")
    all_leads.extend(fetch_funding_announcements(days_back=14))
    
    print(f"Total discovered leads: {len(all_leads)}")
    
    if not all_leads:
        print("No leads found across feeds.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    seen_in_this_batch = set()
    new_leads_processed = 0
    
    for lead in all_leads:
        title_clean = lead["title"].strip().lower()
        title_key = title_clean[:40]
        url_key = lead["url"].strip().lower()

        # 1. Deduplicate against existing Notion records
        if title_key in existing_titles or url_key in existing_urls:
            continue

        # 2. Deduplicate within current run
        if title_key in seen_in_this_batch:
            continue
        seen_in_this_batch.add(title_key)

        # 3. Pre-filter to avoid API calls on obvious mismatches
        if not is_candidate_potentially_relevant(lead):
            continue

        analysis = evaluate_opportunity(client, lead)

        try:
            score = float(analysis.get("score", 0)) if analysis else 0
        except (ValueError, TypeError):
            score = 0

        if analysis and score >= 7:
            print(f"High match ({score}/10): {lead['title'][:50]}")
            create_notion_page(lead, analysis)
            existing_titles.add(title_key)
            existing_urls.add(url_key)
            new_leads_processed += 1

        # Pacing to stay comfortably within free-tier rate limits
        time.sleep(10)

    print(f"Done. Added {new_leads_processed} new opportunities to Notion.")

if __name__ == "__main__":
    main()