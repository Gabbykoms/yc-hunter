import os
import json
import datetime
import requests
from google import genai

# --- CONFIGURATION ---
HN_API = "https://hacker-news.firebaseio.com/v0"
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

def fetch_recent_launches(days_back=14):
    """Fetches recent 'Launch HN:' posts via the Algolia HN Search API."""
    cutoff_timestamp = int((datetime.datetime.now() - datetime.timedelta(days=days_back)).timestamp())
    
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": "Launch HN:",
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff_timestamp}",
        "hitsPerPage": 50
    }
    
    try:
        response = requests.get(url, params=params).json()
        hits = response.get("hits", [])
        
        launches = []
        for hit in hits:
            title = hit.get("title", "")
            if "Launch HN:" in title:
                launches.append({
                    "id": hit.get("objectID"),
                    "title": title.replace("Launch HN: ", "").strip(),
                    "author": hit.get("author", "Founder"),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "text": hit.get("story_text") or hit.get("comment_text") or title
                })
        return launches
    except Exception as e:
        print(f"Error fetching from HN Algolia API: {e}")
        return []

def evaluate_startup(client, launch):
    """Evaluates launch alignment and structures output into JSON."""
    prompt = f"""
Candidate Background:
{CANDIDATE_PROFILE}

Startup: {launch['title']}
Founder Post:
{launch['text']}

Analyze this startup for candidate fit. Respond strictly in valid JSON format:
{{
  "score": <number 1-10>,
  "fit_reason": "<1-2 sentences on why this aligns with Gabriel's tech stack and experience>",
  "demo_idea": "<A practical micro-demo scoped strictly to 2-3 hours>",
  "email_hook": "<1-2 sentence compelling cold email hook to the founder>",
  "suggested_tech_to_showcase": "<comma-separated list of relevant skills from profile>"
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
        print(f"Error evaluating {launch['title']}: {e}")
        return None

def create_notion_page(launch, analysis):
    """Adds a structured page and CRM card into Notion."""
    if not NOTION_API_KEY:
        print("ERROR: NOTION_API_KEY is empty or None!")
        return
    else:
        # Prints something like: Key loaded: ntn_5948... (len: 50)
        print(f"Key loaded: {NOTION_API_KEY[:8]}... (len: {len(NOTION_API_KEY)})")
        
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    today = datetime.date.today().isoformat()
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Company": {
                "title": [{"text": {"content": launch["title"]}}]
            },
            "Score": {
                "number": int(analysis.get("score", 0))
            },
            "Status": {
                "select": {"name": "New Lead"}
            },
            "Founder": {
                "rich_text": [{"text": {"content": f"@{launch['author']}"}}]
            },
            "HN Link": {
                "url": launch["url"]
            },
            "Date Added": {
                "date": {"start": today}
            }
        },
        # Internal Page Content (Markdown Blocks)
        "children": [
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
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "✉️ Cold Email Pitch Hook"}}]}
            },
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": analysis.get("email_hook", "")}}],
                    "icon": {"emoji": "🎯"}
                }
            },
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": "Alignment & Tech to Highlight"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"Reason: {analysis.get('fit_reason', '')}\nShowcase: {analysis.get('suggested_tech_to_showcase', '')}"}}]}
            }
        ]
    }
    
    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    if res.status_code == 200:
        print(f"Successfully added {launch['title']} to Notion.")
    else:
        print(f"Failed to add {launch['title']}: {res.text}")







def main():
    print("Checking Hacker News for recent YC launches...")
    launches = fetch_recent_launches(days_back=7)
    print(f"Found {len(launches)} launches.")
    
    if not launches:
        print("No new launches found this week.")
        return
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    for launch in launches:
        analysis = evaluate_startup(client, launch)
        if analysis and analysis.get("score", 0) >= 7:
            print(f"High match found ({analysis.get('score')}/10): {launch['title']}")
            create_notion_page(launch, analysis)

if __name__ == "__main__":
    main()