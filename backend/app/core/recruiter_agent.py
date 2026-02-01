"""
LangGraph Recruiter Agent - GitHub Talent Discovery
Helps recruiters find talented developers based on GitHub activity

WORKFLOW:
ENTRY → parse_requirements → search_github_repos → analyze_contributors → rank_candidates → format_results → END
"""

import asyncio
import json
from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timedelta
from collections import defaultdict
import httpx

from app.models import MissionLog
from app.core.config import settings


# ==================================================
# RECRUITER AGENT STATE
# ==================================================

class RecruiterAgentState(TypedDict):
    # Core identifiers
    mission_id: str
    user_id: str
    query: str
    
    # Parsed requirements
    language: str
    skills: List[str]
    experience_level: str  # "junior", "mid", "senior"
    days_active: int
    
    # Discovery results
    repositories: List[Dict]
    candidates: List[Dict]
    
    # Enrichment results
    enriched_candidates: List[Dict]  # Top candidates with emails
    
    # State management
    error: Optional[str]


# ==================================================
# UTILITY FUNCTIONS
# ==================================================

async def log_recruiter_event(
    mission_id: str,
    user_id: str,
    content: str,
    log_type: str = "action",
    metadata: Dict = {}
):
    """Log recruiter agent events"""
    log = MissionLog(
        mission_id=mission_id,
        role="agent",
        content=content,
        log_type=log_type,
        metadata=metadata
    )
    await log.insert()
    
    try:
        from app.core.socket import get_connection_manager
        manager = get_connection_manager()
        await manager.send_to_user(user_id, {
            "type": log_type,
            "message": content,
            "agent": "RecruiterBot",
            "mission_id": mission_id,
            "metadata": metadata
        })
    except Exception as e:
        print(f"[WS] Failed to broadcast recruiter event: {e}")


# ==================================================
# NODE 1: PARSE_REQUIREMENTS
# ==================================================

async def parse_requirements(state: RecruiterAgentState) -> Dict:
    """
    Parse recruiter's requirements using LLM.
    Extract: language, skills, experience level, activity window
    """
    query = state["query"]
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    await log_recruiter_event(mission_id, user_id, "Understanding your requirements...", "thinking")
    
    try:
        llm = ChatOpenAI(
            temperature=0.0,
            openai_api_key=settings.OPENAI_API_KEY,
            model_name="gpt-4o-mini"
        )
        
        system_prompt = """You are a technical recruiter assistant. Parse the recruiter's request and extract:

1. Primary programming language (e.g., Python, JavaScript, Java, Go)
2. Skills/technologies mentioned (e.g., React, Node.js, Django, AWS)
3. Experience level: "junior", "mid", or "senior" (infer from context)
4. Activity window in days (default: 90 days)

Return ONLY valid JSON:
{
  "language": "Python",
  "skills": ["Django", "REST API", "PostgreSQL"],
  "experience_level": "mid",
  "days_active": 90
}"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Recruiter request: {query}")
        ]
        
        response = await llm.ainvoke(messages)
        content = response.content.strip()
        
        # Clean JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.replace("```", "").strip()
        
        data = json.loads(content)
        
        language = data.get("language", "Python")
        skills = data.get("skills", [])
        experience_level = data.get("experience_level", "mid")
        days_active = data.get("days_active", 90)
        
        await log_recruiter_event(
            mission_id, user_id,
            f"Looking for {experience_level} {language} developers with {', '.join(skills[:3])}...",
            "thinking"
        )
        
        return {
            "language": language,
            "skills": skills,
            "experience_level": experience_level,
            "days_active": days_active
        }
        
    except Exception as e:
        print(f"Requirements parsing failed: {e}")
        return {
            "language": "Python",
            "skills": [],
            "experience_level": "mid",
            "days_active": 90,
            "error": str(e)
        }


# ==================================================
# NODE 2: SEARCH_GITHUB_REPOS
# ==================================================

async def search_github_repos(state: RecruiterAgentState) -> Dict:
    """
    Search GitHub for relevant repositories based on language and skills.
    """
    language = state["language"]
    skills = state.get("skills", [])
    days_active = state.get("days_active", 90)
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    await log_recruiter_event(mission_id, user_id, f"Searching GitHub for {language} projects...", "thinking")
    
    repositories = []
    
    try:
        since_date = (datetime.utcnow() - timedelta(days=days_active)).strftime("%Y-%m-%d")
        
        # Build search query
        query_parts = [f"language:{language}"]
        if skills:
            query_parts.append(f"{skills[0]}")  # Add primary skill
        query_parts.append(f"pushed:>{since_date}")
        
        search_query = " ".join(query_parts)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/search/repositories",
                headers={
                    "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json"
                },
                params={
                    "q": search_query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 20
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                
                for repo in items:
                    repositories.append({
                        "owner": repo["owner"]["login"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "stars": repo["stargazers_count"],
                        "url": repo["html_url"]
                    })
                
                await log_recruiter_event(
                    mission_id, user_id,
                    f"Found {len(repositories)} relevant repositories",
                    "success"
                )
            else:
                await log_recruiter_event(
                    mission_id, user_id,
                    f"GitHub API returned status {response.status_code}",
                    "warning"
                )
                
    except Exception as e:
        print(f"GitHub repo search error: {e}")
        await log_recruiter_event(mission_id, user_id, f"Search error: {str(e)[:50]}", "error")
    
    return {"repositories": repositories}


# ==================================================
# NODE 3: ANALYZE_CONTRIBUTORS
# ==================================================

async def analyze_contributors(state: RecruiterAgentState) -> Dict:
    """
    Analyze contributors from discovered repositories.
    Calculate confidence scores based on activity and skills.
    """
    repositories = state.get("repositories", [])
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    if not repositories:
        return {"candidates": []}
    
    await log_recruiter_event(mission_id, user_id, "Analyzing contributors...", "thinking")
    
    candidates_data = defaultdict(lambda: {
        "backend_repos": 0,
        "languages": defaultdict(int),
        "has_readme": False,
        "total_contributions": 0
    })
    
    try:
        async with httpx.AsyncClient() as client:
            for repo in repositories[:10]:  # Limit to top 10 repos
                owner = repo["owner"]
                repo_name = repo["name"]
                
                # Get contributors
                try:
                    contrib_response = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo_name}/contributors",
                        headers={
                            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                            "Accept": "application/vnd.github+json"
                        },
                        params={"per_page": 10},
                        timeout=15.0
                    )
                    
                    if contrib_response.status_code == 200:
                        contributors = contrib_response.json()
                        
                        # Get repo languages
                        lang_response = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo_name}/languages",
                            headers={
                                "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                                "Accept": "application/vnd.github+json"
                            },
                            timeout=10.0
                        )
                        
                        languages = {}
                        if lang_response.status_code == 200:
                            languages = lang_response.json()
                        
                        # Check for README
                        readme_response = await client.get(
                            f"https://api.github.com/repos/{owner}/{repo_name}/readme",
                            headers={
                                "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                                "Accept": "application/vnd.github+json"
                            },
                            timeout=10.0
                        )
                        has_readme = readme_response.status_code == 200
                        
                        # Process contributors
                        for contributor in contributors:
                            username = contributor["login"]
                            contributions = contributor.get("contributions", 0)
                            
                            candidates_data[username]["backend_repos"] += 1
                            candidates_data[username]["total_contributions"] += contributions
                            candidates_data[username]["has_readme"] |= has_readme
                            
                            for lang, bytes_count in languages.items():
                                candidates_data[username]["languages"][lang] += bytes_count
                        
                        await asyncio.sleep(0.5)  # Rate limiting
                        
                except Exception as e:
                    print(f"Error analyzing repo {repo_name}: {e}")
                    continue
        
        await log_recruiter_event(
            mission_id, user_id,
            f"Analyzed {len(candidates_data)} unique developers",
            "success"
        )
        
    except Exception as e:
        print(f"Contributor analysis error: {e}")
        await log_recruiter_event(mission_id, user_id, f"Analysis error: {str(e)[:50]}", "error")
    
    return {"candidates": dict(candidates_data)}


# ==================================================
# NODE 4: RANK_CANDIDATES
# ==================================================

async def rank_candidates(state: RecruiterAgentState) -> Dict:
    """
    Rank candidates based on confidence scores.
    Fetch user profiles and calculate final scores.
    """
    candidates_data = state.get("candidates", {})
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    if not candidates_data:
        return {"candidates": []}
    
    await log_recruiter_event(mission_id, user_id, "Ranking candidates...", "thinking")
    
    ranked_candidates = []
    
    try:
        async with httpx.AsyncClient() as client:
            for username, data in list(candidates_data.items())[:30]:  # Top 30
                try:
                    # Get user profile
                    user_response = await client.get(
                        f"https://api.github.com/users/{username}",
                        headers={
                            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                            "Accept": "application/vnd.github+json"
                        },
                        timeout=10.0
                    )
                    
                    if user_response.status_code == 200:
                        user = user_response.json()
                        
                        # Sort languages by usage
                        sorted_langs = sorted(
                            data["languages"].items(),
                            key=lambda x: x[1],
                            reverse=True
                        )
                        
                        # Calculate confidence score
                        confidence = min(1.0,
                            0.4 * min(data["backend_repos"] / 5, 1.0) +
                            0.3 * (1 if data["has_readme"] else 0) +
                            0.3 * min(len(sorted_langs) / 3, 1.0)
                        )
                        
                        ranked_candidates.append({
                            "name": user.get("name") or username,
                            "username": username,
                            "github_url": user["html_url"],
                            "avatar_url": user.get("avatar_url"),
                            "bio": user.get("bio", ""),
                            "location": user.get("location", ""),
                            "company": user.get("company", ""),
                            "email": user.get("email"),
                            "signals": {
                                "backend_repos": data["backend_repos"],
                                "languages": [l[0] for l in sorted_langs[:5]],
                                "has_readme": data["has_readme"],
                                "total_contributions": data["total_contributions"]
                            },
                            "confidence_score": round(confidence, 2)
                        })
                    
                    await asyncio.sleep(0.3)  # Rate limiting
                    
                except Exception as e:
                    print(f"Error fetching user {username}: {e}")
                    continue
        
        # Sort by confidence score
        ranked_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        await log_recruiter_event(
            mission_id, user_id,
            f"Ranked {len(ranked_candidates)} candidates",
            "success"
        )
        
    except Exception as e:
        print(f"Ranking error: {e}")
        await log_recruiter_event(mission_id, user_id, f"Ranking error: {str(e)[:50]}", "error")
    
    return {"candidates": ranked_candidates}


# ==================================================
# NODE 5: FORMAT_RESULTS
# ==================================================

async def format_results(state: RecruiterAgentState) -> Dict:
    """
    Format and display candidate results as cards.
    """
    candidates = state.get("candidates", [])
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    if not candidates:
        await log_recruiter_event(
            mission_id, user_id,
            "❌ No candidates found. Try adjusting your search criteria.",
            "error"
        )
        return {}
    
    await log_recruiter_event(
        mission_id, user_id,
        f"✨ Found **{len(candidates)} talented developers**!",
        "success"
    )
    
    for i, candidate in enumerate(candidates[:20], 1):
        name = candidate.get("name", "Unknown")
        username = candidate.get("username", "")
        github_url = candidate.get("github_url", "")
        bio = candidate.get("bio", "")
        location = candidate.get("location", "")
        company = candidate.get("company", "")
        signals = candidate.get("signals", {})
        confidence = candidate.get("confidence_score", 0)
        
        # Build candidate card
        card_msg = f"""### 👨‍💻 {name}

**@{username}**"""
        
        if company:
            card_msg += f" • {company}"
        if location:
            card_msg += f" • 📍 {location}"
        
        if bio:
            card_msg += f"\n\n{bio[:150]}{'...' if len(bio) > 150 else ''}"
        
        card_msg += f"\n\n**Skills:** {', '.join(signals.get('languages', [])[:5])}"
        card_msg += f"\n**Projects:** {signals.get('backend_repos', 0)} repositories"
        card_msg += f"\n**Confidence:** {int(confidence * 100)}%"
        
        card_msg += f"\n\n[🔗 View GitHub Profile]({github_url})"
        
        await log_recruiter_event(
            mission_id, user_id,
            card_msg,
            "action",
            metadata={
                "type": "candidate_card",
                "username": username,
                "github_url": github_url,
                "confidence": confidence,
                "index": i
            }
        )
        
        await asyncio.sleep(0.15)
    
    # Final summary
    await log_recruiter_event(
        mission_id, user_id,
        f"🎯 **Search complete!** {len(candidates)} candidates ranked by relevance",
        "success"
    )
    
    return {}


# ==================================================
# NODE 6: ENRICH_WITH_FIRECRAWL
# ==================================================

async def enrich_with_firecrawl(state: RecruiterAgentState) -> Dict:
    """
    Use Firecrawl to scrape top 5 candidate GitHub profiles and extract emails.
    """
    candidates = state.get("candidates", [])
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    
    if not candidates:
        return {"enriched_candidates": []}
    
    # Take top 5 candidates
    top_candidates = candidates[:5]
    
    await log_recruiter_event(
        mission_id, user_id,
        f"🔍 Enriching top {len(top_candidates)} candidates with contact info...",
        "thinking"
    )
    
    enriched = []
    
    try:
        async with httpx.AsyncClient() as client:
            for candidate in top_candidates:
                github_url = candidate.get("github_url", "")
                
                if not github_url:
                    continue
                
                try:
                    # Use Firecrawl to scrape the GitHub profile
                    response = await client.post(
                        "https://api.firecrawl.dev/v1/scrape",
                        headers={
                            "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "url": github_url,
                            "formats": ["markdown"]
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        markdown_content = data.get("data", {}).get("markdown", "")
                        
                        # Extract email using regex
                        import re
                        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                        emails = re.findall(email_pattern, markdown_content)
                        
                        # Filter out common non-personal emails
                        personal_emails = [
                            email for email in emails 
                            if not any(domain in email.lower() for domain in ['noreply', 'github', 'example'])
                        ]
                        
                        if personal_emails:
                            candidate_copy = candidate.copy()
                            candidate_copy["email"] = personal_emails[0]  # Take first valid email
                            enriched.append(candidate_copy)
                            
                            await log_recruiter_event(
                                mission_id, user_id,
                                f"✅ Found email for {candidate.get('name', 'candidate')}",
                                "success"
                            )
                        else:
                            await log_recruiter_event(
                                mission_id, user_id,
                                f"⚠️ No email found for {candidate.get('name', 'candidate')}",
                                "warning"
                            )
                    
                    await asyncio.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    print(f"Error scraping {github_url}: {e}")
                    continue
        
        await log_recruiter_event(
            mission_id, user_id,
            f"📧 Found emails for {len(enriched)} candidates",
            "success"
        )
        
    except Exception as e:
        print(f"Firecrawl enrichment error: {e}")
        await log_recruiter_event(mission_id, user_id, f"Enrichment error: {str(e)[:50]}", "error")
    
    return {"enriched_candidates": enriched}


# ==================================================
# NODE 7: CREATE_OUTREACH_DRAFTS
# ==================================================

async def create_outreach_drafts(state: RecruiterAgentState) -> Dict:
    """
    Generate personalized recruitment emails for candidates with emails.
    Create drafts in the review queue.
    """
    enriched_candidates = state.get("enriched_candidates", [])
    mission_id = state["mission_id"]
    user_id = state["user_id"]
    language = state.get("language", "")
    skills = state.get("skills", [])
    experience_level = state.get("experience_level", "mid")
    
    if not enriched_candidates:
        await log_recruiter_event(
            mission_id, user_id,
            "No candidates with emails found. Try searching for more candidates.",
            "warning"
        )
        return {}
    
    await log_recruiter_event(
        mission_id, user_id,
        f"✍️ Drafting personalized emails for {len(enriched_candidates)} candidates...",
        "thinking"
    )
    
    from app.models import Draft, DraftStatus, Prospect
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    
    try:
        llm = ChatOpenAI(
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY,
            model_name="gpt-4o"
        )
        
        drafts_created = 0
        
        for candidate in enriched_candidates:
            name = candidate.get("name", "")
            username = candidate.get("username", "")
            email = candidate.get("email", "")
            bio = candidate.get("bio", "")
            github_url = candidate.get("github_url", "")
            signals = candidate.get("signals", {})
            languages = signals.get("languages", [])
            
            # Create prospect
            prospect = Prospect(
                mission_id=mission_id,
                name=name,
                company=candidate.get("company") or "GitHub Developer",
                context_source="GitHub Talent Search",
                public_contact=email,
                relevance_score=candidate.get("confidence_score", 0.8),
                relevance_reason=f"GitHub developer with {', '.join(languages[:3])} experience",
                original_data=candidate
            )
            await prospect.insert()
            
            # Generate personalized email
            system_prompt = f"""You are a technical recruiter writing a personalized outreach email.

Candidate Profile:
- Name: {name}
- GitHub: {username}
- Skills: {', '.join(languages[:5])}
- Bio: {bio}
- Projects: {signals.get('backend_repos', 0)} repositories

Position Requirements:
- Language: {language}
- Skills: {', '.join(skills)}
- Level: {experience_level}

Write a warm, personalized recruitment email that:
1. Mentions their specific GitHub work/projects
2. Explains why they're a great fit
3. Highlights the opportunity
4. Keeps it concise (under 200 words)
5. Professional but friendly tone

Return JSON:
{{
  "subject": "Email subject line",
  "body": "Email body"
}}"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Write a recruitment email for {name}")
            ]
            
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            
            # Clean JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.replace("```", "").strip()
            
            email_data = json.loads(content)
            
            # Create draft
            draft = Draft(
                prospect_id=str(prospect.id),
                channel="email",
                subject=email_data.get("subject", f"Exciting {language} opportunity"),
                body=email_data.get("body", ""),
                ai_reasoning=f"Personalized recruitment email for {experience_level} {language} developer",
                status=DraftStatus.PENDING
            )
            await draft.insert()
            
            drafts_created += 1
            
            await asyncio.sleep(0.5)  # Rate limiting
        
        await log_recruiter_event(
            mission_id, user_id,
            f"✅ Created {drafts_created} recruitment emails in review queue!",
            "success",
            metadata={"action": "drafts_created", "count": drafts_created}
        )
        
    except Exception as e:
        print(f"Draft creation error: {e}")
        await log_recruiter_event(mission_id, user_id, f"Draft error: {str(e)[:50]}", "error")
    
    return {}


# ==================================================
# BUILD RECRUITER GRAPH
# ==================================================

recruiter_workflow = StateGraph(RecruiterAgentState)

# Add nodes
recruiter_workflow.add_node("parse_requirements", parse_requirements)
recruiter_workflow.add_node("search_github_repos", search_github_repos)
recruiter_workflow.add_node("analyze_contributors", analyze_contributors)
recruiter_workflow.add_node("rank_candidates", rank_candidates)
recruiter_workflow.add_node("format_results", format_results)
recruiter_workflow.add_node("enrich_with_firecrawl", enrich_with_firecrawl)
recruiter_workflow.add_node("create_outreach_drafts", create_outreach_drafts)

# Set entry point
recruiter_workflow.set_entry_point("parse_requirements")

# Define edges
recruiter_workflow.add_edge("parse_requirements", "search_github_repos")
recruiter_workflow.add_edge("search_github_repos", "analyze_contributors")
recruiter_workflow.add_edge("analyze_contributors", "rank_candidates")
recruiter_workflow.add_edge("rank_candidates", "format_results")
recruiter_workflow.add_edge("format_results", "enrich_with_firecrawl")
recruiter_workflow.add_edge("enrich_with_firecrawl", "create_outreach_drafts")
recruiter_workflow.add_edge("create_outreach_drafts", END)

# Compile
recruiter_memory = MemorySaver()
recruiter_app = recruiter_workflow.compile(checkpointer=recruiter_memory)


# ==================================================
# RUNNER FUNCTIONS
# ==================================================

async def run_recruiter_agent(mission_id: str, query: str, user_id: str):
    """Start a new recruiter agent run"""
    print(f"DEBUG: Starting recruiter mission {mission_id} with query: {query[:50]}...")
    
    config = {"configurable": {"thread_id": mission_id}}
    inputs = {
        "mission_id": mission_id,
        "user_id": user_id,
        "query": query,
        "language": "",
        "skills": [],
        "experience_level": "mid",
        "days_active": 90,
        "repositories": [],
        "candidates": [],
        "enriched_candidates": [],
        "error": None
    }
    
    try:
        async for event in recruiter_app.astream(inputs, config=config):
            print(f"DEBUG: Recruiter event: {list(event.keys())}")
    except Exception as e:
        import traceback
        print(f"ERROR: Recruiter agent failed: {traceback.format_exc()}")
        try:
            await log_recruiter_event(mission_id, user_id, f"Error: {str(e)}", "error")
        except:
            pass


async def continue_recruiter_agent(mission_id: str, query: str, user_id: str):
    """Continue an existing recruiter conversation"""
    print(f"DEBUG: Continuing recruiter mission {mission_id} with query: {query[:50]}...")
    
    config = {"configurable": {"thread_id": mission_id}}
    
    inputs = {
        "mission_id": mission_id,
        "user_id": user_id,
        "query": query,
        "language": "",
        "skills": [],
        "experience_level": "mid",
        "days_active": 90,
        "repositories": [],
        "candidates": [],
        "enriched_candidates": [],
        "error": None
    }
    
    try:
        async for event in recruiter_app.astream(inputs, config=config):
            print(f"DEBUG: Continue recruiter event: {list(event.keys())}")
    except Exception as e:
        import traceback
        print(f"ERROR: Continue recruiter failed: {traceback.format_exc()}")
        try:
            await log_recruiter_event(mission_id, user_id, f"Error: {str(e)}", "error")
        except:
            pass
