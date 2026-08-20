
import os
import json
import datetime
import requests
from google import genai

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

def fetch_launch_hn(days_back=14):
    """Fetches recent 'Launch HN:' posts via Algolia."""
    cutoff = int((datetime.datetime.now() - datetime.timedelta(days=days_back)).timestamp())
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": "Launch HN:",
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff}",
        "hitsPerPage": 30
    }
    results = []
    try:
        data = requests.get(url, params=params).json()
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            if "Launch HN:" in title:
                results.append({
                    "source": "Launch HN",
                    "title": title.replace("Launch HN: ", "").strip(),
                    "author": hit.get("author", "Founder"),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "text": hit.get("story_text") or hit.get("comment_text") or title
                })
    except Exception as e:
        print(f"Error in fetch_launch_hn: {e}")
    return results

def fetch_who_is_hiring():
    """Fetches top-level job postings from the latest monthly 'Ask HN: Who is hiring?' thread."""
    url = "https://hn.algolia.com/api/v1/search"
    # Find the latest Who is Hiring thread
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
        
        thread_id = hits[0].get("objectID")
        print(f"Scanning Who is Hiring thread (ID: {thread_id})...")
        
        # Pull top comments from this thread
        comments_url = "https://hn.algolia.com/api/v1/search"
        comment_params = {
            "tags": f"comment,story_{thread_id}",
            "hitsPerPage": 50
        }
        comment_data = requests.get(comments_url, params=comment_params).json()
        
        for c in comment_data.get("hits", []):
            text = c.get("comment_text", "")
            if len(text) < 100:
                continue
            
            # The first line of Who is Hiring comments usually contains: "Company | Role | Location | Stack"
            first_line = text.split("<p>")[0].replace("&#x2F;", "/").replace("&amp;", "&")
            company_title = first_line[:80].strip()
            
            results.append({
                "source": "Who is Hiring",
                "title": company_title,
                "author": c.get("author", "Hiring Team"),
                "url": f"https://news.ycombinator.com/item?id={c.get('objectID')}",
                "text": text[:1500]
            })
    except Exception as e:
        print(f"Error in fetch_who_is_hiring: {e}")
    return results

def fetch_funding_announcements(days_back=21):
    """Searches HN for recent funded startup announcements beyond YC."""
    cutoff = int((datetime.datetime.now() - datetime.timedelta(days=days_back)).timestamp())
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": "seed round OR Series A OR raised OR seed funding",
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff}",
        "hitsPerPage": 25
    }
    results = []
    try:
        data = requests.get(url, params=params).json()
        for hit in data.get("hits", []):
            title = hit.get("title", "")
            # Filter out generic articles / big tech news
            if any(term in title.lower() for term in ["raised", "series a", "seed round", "$"]):
                results.append({
                    "source": "Funding News",
                    "title": title,
                    "author": hit.get("author", "Founder"),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "text": hit.get("story_text") or title
                })
    except Exception as e:
        print(f"Error in fetch_funding_announcements: {e}")
    return results

def evaluate_opportunity(client, item):
    """Evaluates fit, checks funding/hiring signals, and generates outreach."""
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

Respond strictly in valid JSON:
{{
  "score": <number 1-10>,
  "funding_or_hiring_signal": "<e.g., Active Hiring / Seed Stage / Series A>",
  "fit_reason": "<1-2 sentences on why this aligns with Gabriel's tech stack>",
  "demo_idea": "<A practical micro-demo scoped strictly to 2-3 hours>",
  "email_hook": "<1-2 sentence compelling cold email hook to the founder/engineering lead>"
}}
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error evaluating {item['title']}: {e}")
        return None

def create_notion_page(item, analysis):
    """Adds a formatted row and CRM page into Notion."""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY.strip()}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    today = datetime.date.today().isoformat()
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Company": {
                "title": [{"text": {"content": item["title"][:100]}}]
            },
            "Score": {
                "number": int(analysis.get("score", 0))
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
    print("Aggregating opportunities across multiple startup feeds...")
    
    all_leads = []
    
    # 1. Recent YC Launches
    print("-> Fetching Launch HN...")
    all_leads.extend(fetch_launch_hn(days_back=14))
    
    # 2. Direct Hiring Threads
    print("-> Fetching Ask HN: Who is hiring?...")
    all_leads.extend(fetch_who_is_hiring())
    
    # 3. Funded Startup Announcements
    print("-> Fetching recent funding announcements...")
    all_leads.extend(fetch_funding_announcements(days_back=21))
    
    print(f"Total opportunities discovered across feeds: {len(all_leads)}")
    
    if not all_leads:
        print("No leads found across feeds.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Deduplicate by title to prevent duplicates
    seen_titles = set()
    
    for lead in all_leads:
        title_key = lead["title"][:40].lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        
        analysis = evaluate_opportunity(client, lead)
        if analysis and analysis.get("score", 0) >= 8:  # Strict filter for high signal
            print(f"High match ({analysis.get('score')}/10): {lead['title'][:50]}")
            create_notion_page(lead, analysis)

if __name__ == "__main__":
    main()