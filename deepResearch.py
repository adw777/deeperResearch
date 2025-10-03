import os
from typing import Literal, Optional
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import sys
import json

load_dotenv()

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

openai_model = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.4,
    api_key=os.getenv("OPENAI_API_KEY"),
)


def legal_search(
    query: str,
    jurisdiction: Literal["indian", "international", "general"] = "indian",
    max_results: int = 10,
    include_raw_content: bool = True,
):
    """Search for legal information across various sources."""
    enhanced_query = query
    if jurisdiction == "indian":
        enhanced_query = f"{query} Indian law India legal"
    
    search_results = tavily_client.search(
        enhanced_query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        exclude_domains=["indiankanoon.org"],
        topic="general",
    )
    return search_results


def case_law_search(
    query: str,
    court_level: Optional[Literal["supreme_court", "high_court", "district_court", "all"]] = "all",
    max_results: int = 8,
):
    """Search specifically for case law and judicial precedents."""
    court_keywords = {
        "supreme_court": "Supreme Court of India",
        "high_court": "High Court India",
        "district_court": "District Court India",
        "all": "Indian courts"
    }
    
    enhanced_query = f"{query} {court_keywords.get(court_level, 'Indian courts')} case law judgment"
    
    search_results = tavily_client.search(
        enhanced_query,
        max_results=max_results,
        include_raw_content=True,
        exclude_domains=["indiankanoon.org"],
        topic="general",
    )
    return search_results


def statutory_search(
    query: str,
    act_type: Optional[Literal["central", "state", "both"]] = "both",
    max_results: int = 8,
):
    """Search for statutes, acts, and legislative provisions."""
    act_keywords = {
        "central": "Central Act India Parliament",
        "state": "State Act India Legislature",
        "both": "Indian legislation Act"
    }
    
    enhanced_query = f"{query} {act_keywords.get(act_type, 'Indian legislation')} statute provision"
    
    search_results = tavily_client.search(
        enhanced_query,
        max_results=max_results,
        include_raw_content=True,
        exclude_domains=["indiankanoon.org"],
        topic="general",
    )
    return search_results


query_analyzer_prompt = """You are a legal query analyzer. Your job is to understand the user's legal query and determine:

1. Whether this is a legal query requiring deep research
2. The complexity level: simple, moderate, or complex
3. The type of legal research required
4. The jurisdiction
5. The legal domain
6. Key legal concepts and terms involved

IMPORTANT: Assess if this query is:
- A genuine legal research question (proceed with full analysis)
- A simple legal question that can be answered directly without deep research
- A non-legal query (flag as irrelevant)
- A casual conversation attempt (flag as off-topic)

Based on your analysis, provide a structured breakdown:

- Query Relevance: [legal-complex / legal-simple / non-legal / off-topic]
- Complexity: [simple / moderate / complex]
- Query Type: [case law/statutory/advisory/comparative/other]
- Jurisdiction: [central/state/international]
- Legal Domain: [criminal/civil/constitutional/etc.]
- Key Terms: [list of important legal terms]
- Research Strategy: [brief guidance on how to approach this query]
- Recommendation: [full-research / direct-answer / politely-decline]

Only use the search tools if you need clarification on legal terminology or concepts.
Your analysis will guide whether to proceed with deep research or provide a direct response."""

query_analyzer_subagent = {
    "name": "query-analyzer",
    "description": "Analyzes legal queries to understand their nature, jurisdiction, domain, and complexity.",
    "prompt": query_analyzer_prompt,
    "tools": [legal_search],
    "model": openai_model,
}


case_law_researcher_prompt = """You are a case law research specialist. Your job is to find and analyze relevant judicial precedents.

When researching case law:
1. Search for landmark judgments and binding precedents
2. Identify the ratio decidendi of each case
3. Note the court hierarchy and precedential value
4. Check if cases have been overruled or distinguished
5. Find recent applications of the legal principle

Use the case_law_search tool extensively. 

CRITICAL: For every case you find, capture the URL from the search results.

Your findings will be compiled into the final legal research report, so be comprehensive and accurate."""

case_law_researcher_subagent = {
    "name": "case-law-researcher",
    "description": "Specializes in finding and analyzing case law, judicial precedents, and court judgments.",
    "prompt": case_law_researcher_prompt,
    "tools": [case_law_search, legal_search],
    "model": openai_model,
}


statutory_researcher_prompt = """You are a statutory interpretation specialist. Your job is to research legislation, acts, rules, and regulations.

When researching statutes:
1. Find the exact statutory provisions relevant to the query
2. Identify key definitions from the relevant Act
3. Check for amendments and current status of provisions
4. Look for subordinate legislation
5. Find legislative intent through statements of objects and reasons

Use the statutory_search tool extensively.

CRITICAL: For every statute or provision you find, capture the URL from the search results.

Your findings will be used in the final report, so ensure accuracy in citing provisions."""

statutory_researcher_subagent = {
    "name": "statutory-researcher",
    "description": "Specializes in researching statutes, acts, rules, regulations, and legislative provisions.",
    "prompt": statutory_researcher_prompt,
    "tools": [statutory_search, legal_search],
    "model": openai_model,
}


comparative_analyst_prompt = """You are a comparative legal analyst. Your job is to compare legal positions across different jurisdictions or analyze conflicting precedents.

When doing comparative analysis:
1. Research the legal position in different jurisdictions
2. Identify similarities and differences in approach
3. Analyze the rationale behind different approaches
4. Highlight best practices and potential reforms
5. Consider practical implications of different legal regimes

Use all available search tools as needed.

CRITICAL: Capture URLs for all sources you reference.

Present your analysis in a structured, comparative format showing key differences and similarities."""

comparative_analyst_subagent = {
    "name": "comparative-analyst",
    "description": "Specializes in comparative legal analysis across jurisdictions or conflicting precedents.",
    "prompt": comparative_analyst_prompt,
    "tools": [legal_search, case_law_search, statutory_search],
    "model": openai_model,
}


legal_research_instructions_normal = """
You are an expert Indian legal research agent with deep mastery of Indian law, courts, procedures, and statutory regimes.

Your job: take a legal question, do rigorous research, and output ONLY a valid JSON response with structured content and references.

WORKFLOW:

1. QUERY ANALYSIS (MANDATORY FIRST STEP)  
   - ALWAYS invoke the query-analyzer subagent first to classify the query.  
   - Based on that, label the query as one of:
     * legal-complex - requires full deep research  
     * legal-simple - straightforward legal question  
     * non-legal / off-topic - outside your domain  

2. NON-LEGAL / OFF-TOPIC QUERIES  
   - If the classification is non-legal or off-topic:  
     Return JSON: {"error": "I am a specialized legal research agent focused on Indian law. This query seems outside that domain.", "suggestion": "Please ask legal questions related to Indian law."}

3. SIMPLE LEGAL QUERIES  
   - If classification is legal-simple:  
     Provide a brief, direct answer with 1-2 citations in the JSON format below.

4. DEEP RESEARCH FOR COMPLEX QUERIES  
   - If classification is legal-complex:  
     * Invoke relevant subagents as needed
     * Combine their outputs with direct calls to search tools
     * Identify key issues, doctrinal tensions, hierarchy of authorities
     * Note binding vs persuasive sources, conflicting judgments
     * Provide a CONCISE but COMPREHENSIVE response

5. JSON OUTPUT FORMAT (MANDATORY)  
   Your response MUST be ONLY valid JSON in this exact structure:

   {
     "content": [
       {
         "text": "First paragraph or sentence of analysis",
         "refs": ["ref1", "ref2"]
       },
       {
         "text": "Next paragraph or sentence",
         "refs": ["ref3"]
       }
     ],
     "references": {
       "ref1": {
         "title": "Title or case name",
         "url": "https://example.com",
         "authors": "Author or bench",
         "year": 2023,
         "type": "case"
       },
       "ref2": {
         "title": "Statute name",
         "url": "https://example.com",
         "authors": "Legislature",
         "year": 2020,
         "type": "statute"
       }
     }
   }

CRITICAL RULES:
- Output ONLY valid JSON, no other text before or after
- Each text segment should reference relevant sources via refs array
- All references must be defined in the references object
- Types can be: "case", "statute", "article", "regulation", "report"
- Include URLs whenever available from search results
- Break content into logical paragraphs or sections
- Ensure JSON is properly escaped and valid
- Be CONCISE and FOCUSED - provide optimal depth without unnecessary verbosity
"""

legal_research_instructions_detailed = """
You are an expert Indian legal research agent with deep mastery of Indian law, courts, procedures, and statutory regimes.

Your job: take a legal question, do rigorous research, and output ONLY a valid JSON response with EXTREMELY DETAILED structured content and references.

WORKFLOW:

1. QUERY ANALYSIS (MANDATORY FIRST STEP)  
   - ALWAYS invoke the query-analyzer subagent first to classify the query.  
   - Based on that, label the query as one of:
     * legal-complex - requires full deep research  
     * legal-simple - straightforward legal question  
     * non-legal / off-topic - outside your domain  

2. NON-LEGAL / OFF-TOPIC QUERIES  
   - If the classification is non-legal or off-topic:  
     Return JSON: {"error": "I am a specialized legal research agent focused on Indian law. This query seems outside that domain.", "suggestion": "Please ask legal questions related to Indian law."}

3. SIMPLE LEGAL QUERIES  
   - If classification is legal-simple:  
     Still provide DETAILED analysis with multiple citations.

4. DEEP RESEARCH FOR COMPLEX QUERIES  
   - If classification is legal-complex:  
     * Invoke ALL relevant subagents extensively
     * Make MULTIPLE calls to search tools to gather comprehensive information
     * Provide EXHAUSTIVE statutory analysis with clause-by-clause breakdown
     * Include ALL relevant case law with detailed facts, holdings, and reasoning
     * Discuss historical legislative context and evolution
     * Analyze multiple jurisdictional perspectives where applicable
     * Detail procedural requirements extensively
     * Provide comprehensive practical implications and risk analysis
     * Discuss policy considerations and potential reforms
     * Include multiple hypothetical scenarios and examples
     * MAXIMIZE depth, breadth, and comprehensiveness of analysis

5. JSON OUTPUT FORMAT (MANDATORY)  
   Your response MUST be ONLY valid JSON in this exact structure with EXTENSIVE content:

   {
     "content": [
       {
         "text": "Detailed first section of analysis with comprehensive explanation",
         "refs": ["ref1", "ref2", "ref3"]
       },
       {
         "text": "Detailed next section with thorough examination",
         "refs": ["ref4", "ref5"]
       }
     ],
     "references": {
       "ref1": {
         "title": "Title or case name",
         "url": "https://example.com",
         "authors": "Author or bench",
         "year": 2023,
         "type": "case"
       }
     }
   }

CRITICAL RULES:
- Output ONLY valid JSON, no other text before or after
- Each text segment should reference relevant sources via refs array
- All references must be defined in the references object
- Types can be: "case", "statute", "article", "regulation", "report"
- Include URLs whenever available from search results
- Break content into MANY logical paragraphs or sections
- Ensure JSON is properly escaped and valid
- MAXIMIZE detail - generate the LONGEST, most COMPREHENSIVE response possible
- Include EXTENSIVE case law analysis
- Provide DETAILED statutory interpretation
- Cover ALL possible angles and perspectives
- Generate AT LEAST 10-20 content sections for complex queries
"""


def create_agent_for_mode(mode: Literal["normal", "detailed"]):
    """Create agent with appropriate instructions based on mode."""
    instructions = legal_research_instructions_detailed if mode == "detailed" else legal_research_instructions_normal
    
    return create_deep_agent(
        tools=[legal_search, case_law_search, statutory_search],
        instructions=instructions,
        model=openai_model,
        subagents=[
            query_analyzer_subagent,
            case_law_researcher_subagent,
            statutory_researcher_subagent,
            comparative_analyst_subagent,
        ],
    ).with_config({"recursion_limit": 50 if mode == "detailed" else 30})


def research_legal_query(
    query: str, 
    files: Optional[dict] = None, 
    verbose: bool = True,
    mode: Literal["normal", "detailed"] = "normal"
):
    """
    Research a legal query and return JSON response.
    
    Args:
        query: The legal question or research topic
        files: Optional dictionary of files to provide as context
        verbose: Whether to show detailed streaming output
        mode: "normal" for optimal response, "detailed" for maximum comprehensive response
    
    Returns:
        JSON string with structured legal research
    """
    agent = create_agent_for_mode(mode)
    
    input_state = {
        "messages": [{"role": "user", "content": query}]
    }
    
    if files:
        input_state["files"] = files
    
    if verbose:
        print("\n" + "=" * 80)
        print(f"LEGAL RESEARCH AGENT - {mode.upper()} MODE".center(80))
        print("=" * 80)
        print(f"\nQuery: {query}\n")
        print("-" * 80 + "\n")
    
    final_result = None
    
    try:
        for chunk in agent.stream(input_state, stream_mode=["updates"]):
            if isinstance(chunk, dict):
                for node_name, node_data in chunk.items():
                    if verbose:
                        print(f"[NODE COMPLETED] {node_name}")
                        
                        if node_data and isinstance(node_data, dict):
                            if "files" in node_data:
                                for filename in node_data["files"].keys():
                                    print(f"  [FILE UPDATED] {filename}")
                            
                            if "messages" in node_data:
                                msg_count = len(node_data["messages"]) if isinstance(node_data["messages"], list) else 1
                                print(f"  [MESSAGES] Added {msg_count} message(s)")
                        
                        print()
                
                final_result = chunk
            elif isinstance(chunk, tuple):
                if verbose:
                    print(f"[DEBUG] Received tuple chunk: {type(chunk)}")
                final_result = chunk[1] if len(chunk) > 1 else chunk[0]
        
        if verbose:
            print("=" * 80)
            print("RESEARCH COMPLETE".center(80))
            print("=" * 80 + "\n")
        
        if final_result:
            if isinstance(final_result, dict):
                for node_data in final_result.values():
                    if isinstance(node_data, dict) and "messages" in node_data:
                        messages = node_data["messages"]
                        last_message = messages[-1] if isinstance(messages, list) else messages
                        
                        if hasattr(last_message, "content"):
                            return last_message.content
                        elif isinstance(last_message, dict) and "content" in last_message:
                            return last_message["content"]
            elif hasattr(final_result, "content"):
                return final_result.content
        
        return json.dumps({"error": "No response generated"})
        
    except Exception as e:
        if verbose:
            print(f"\n[ERROR] {str(e)}\n")
            import traceback
            traceback.print_exc()
        return json.dumps({
            "error": "Research failed",
            "details": str(e)
        })


if __name__ == "__main__":
    test_queries = {
        "complex": "Can a private company take a loan from an LLP? I have a privately owned private limited company and I want to check if it can take a loan from an LLP under Indian law?",
        "simple": "What is the age of majority in India?",
        "greeting": "hi wassup?"
    }
    
    query_to_test = test_queries["complex"]
    mode_to_test = "normal"
    
    print(f"\nTesting with query type: complex")
    print(f"Mode: {mode_to_test}")
    print(f"Query: {query_to_test}\n")
    
    result = research_legal_query(
        query_to_test, 
        verbose=True,
        mode=mode_to_test
    )
    
    print("\n" + "=" * 80)
    print("FINAL JSON RESPONSE".center(80))
    print("=" * 80)
    print(result)
    
    try:
        parsed = json.loads(result)
        print("\n" + "=" * 80)
        print("JSON VALIDATION: PASSED".center(80))
        print("=" * 80)
        print(f"\nContent sections: {len(parsed.get('content', []))}")
        print(f"References: {len(parsed.get('references', {}))}")
    except json.JSONDecodeError as e:
        print("\n" + "=" * 80)
        print("JSON VALIDATION: FAILED".center(80))
        print("=" * 80)
        print(f"Error: {e}")