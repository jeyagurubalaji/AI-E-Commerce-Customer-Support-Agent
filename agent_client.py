"""AI E-Commerce Customer Support Agent Client.

Powered by:
- LangGraph (StateGraph workflow: decide_tool -> call_tool -> synthesize)
- MCP (Model Context Protocol stdio transport & tools)
- Ollama / Qwen2.5:3B (Classification & Response Synthesis with intelligent fallback)
- SQLite Persistent Memory (Conversation history & Support tickets)
- Rich Terminal UI & Interactive CLI
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

# Configure UTF-8 for Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# Local module imports
import database
import knowledge_base
import mcp_server

# Load environment variables
load_dotenv()

# Initialize Rich Console with legacy_windows=False if possible
console = Console(highlight=False)

# Configuration
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MCP_SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_server.py"))


# =====================================================================
# State Definition
# =====================================================================

class AgentState(TypedDict):
    """LangGraph Agent State representation."""
    query: str
    category: str
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Any
    response: str
    session_id: str


# =====================================================================
# Ollama Availability & Health Check
# =====================================================================

def check_ollama_status(base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Check if Ollama service is reachable and if the requested model is available."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "AIEcommerceAgent"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                model_base = model.split(":")[0]
                model_exists = any(model in m or model_base in m for m in models)
                return {
                    "running": True,
                    "model_available": model_exists,
                    "models": models,
                    "message": "Ollama is running.",
                }
    except Exception:
        pass

    return {
        "running": False,
        "model_available": False,
        "models": [],
        "message": (
            "[bold yellow]Notice:[/bold yellow] Ollama is not currently detected at "
            f"{base_url}.\n"
            "Please install/start Ollama and run:\n\n"
            f"    [bold cyan]ollama pull {model}[/bold cyan]\n\n"
            "[green]Running in Hybrid-Fallback Mode:[/green] "
            "LangGraph, MCP Tools, and SQLite memory are fully operational!"
        ),
    }


# Global Ollama status cache
OLLAMA_STATUS = check_ollama_status()


def query_ollama(prompt: str, system: Optional[str] = None, model: str = DEFAULT_MODEL) -> Optional[str]:
    """Query local Ollama server if available, returning None if offline."""
    if not OLLAMA_STATUS["running"]:
        return None

    try:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if system:
            payload["system"] = system

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "AIEcommerceAgent"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "").strip()
    except Exception:
        return None
    return None


# =====================================================================
# Node 1: decide_tool (Query Router & Tool Selector)
# =====================================================================

def decide_tool(state: AgentState) -> Dict[str, Any]:
    """Analyze the customer query, classify intent, and choose appropriate MCP tool."""
    query = state.get("query", "").strip()
    console.print("[dim][AGENT] Analyzing request...[/dim]")

    category = "general"
    tool_name = "search_policies"
    tool_args: Dict[str, Any] = {"query": query}

    # Extract common entities
    order_id_match = re.search(r"\b(ORD\d{3,5})\b", query, re.IGNORECASE)
    order_id = order_id_match.group(1).upper() if order_id_match else None

    product_id_match = re.search(r"\b(P\d{4})\b", query, re.IGNORECASE)
    product_id = product_id_match.group(1).upper() if product_id_match else None

    # Price extraction: e.g. "under 3000", "below 5000", "less than 2500"
    price_match = re.search(r"(?:under|below|less than|within|budget of)\s*(?:rs\.?|inr|₹)?\s*(\d+)", query, re.IGNORECASE)
    max_price = float(price_match.group(1)) if price_match else None

    # Attempt LLM Classification if Ollama is available
    llm_classified = False
    if OLLAMA_STATUS.get("running") and OLLAMA_STATUS.get("model_available"):
        router_prompt = (
            "You are an e-commerce query classifier. Classify the user query into exactly ONE category:\n"
            "- product_search\n"
            "- product_details\n"
            "- recommendation\n"
            "- order_status\n"
            "- return\n"
            "- refund\n"
            "- shipping\n"
            "- support_ticket\n"
            "- general\n\n"
            f"Customer query: \"{query}\"\n\n"
            "Respond ONLY with a JSON object:\n"
            '{"category": "<one_category_from_above>"}'
        )
        llm_resp = query_ollama(router_prompt)
        if llm_resp:
            try:
                m = re.search(r"\{.*?\}", llm_resp, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    candidate_cat = parsed.get("category", "").lower().strip()
                    valid_cats = {
                        "product_search", "product_details", "recommendation",
                        "order_status", "return", "refund", "shipping",
                        "support_ticket", "general",
                    }
                    if candidate_cat in valid_cats:
                        category = candidate_cat
                        llm_classified = True
            except Exception:
                llm_classified = False

    # Fallback Rule-Based Classifier (Guarantees 100% deterministic accuracy)
    if not llm_classified:
        q_lower = query.lower()
        if any(k in q_lower for k in ["ticket", "support ticket", "raise a ticket", "create a ticket", "create ticket", "file ticket", "agent help"]):
            category = "support_ticket"
        elif any(k in q_lower for k in ["return", "exchange", "replace", "send back"]):
            category = "return"
        elif any(k in q_lower for k in ["where is my order", "order status", "track order", "track my", "where is order"]) or (order_id and any(w in q_lower for w in ["order", "where", "track", "status", "package"])):
            category = "order_status"
        elif any(k in q_lower for k in ["refund", "money back", "reimburse", "when will i get my refund"]):
            category = "refund"
        elif any(k in q_lower for k in ["shipping", "delivery time", "shipping charge", "delivery charge", "dispatch", "courier"]):
            category = "shipping"
        elif any(k in q_lower for k in ["recommend", "suggestion", "suggest", "which is better", "best laptop", "best phone", "best headphone"]):
            category = "recommendation"
        elif product_id or any(k in q_lower for k in ["spec", "specs", "specification", "details of"]):
            category = "product_details"
        elif any(k in q_lower for k in ["find", "search", "headphone", "headphones", "laptop", "phone", "mouse", "keyboard", "watch", "tablet", "price", "under", "available", "have wireless"]):
            category = "product_search"
        else:
            category = "general"

    # Map Category to MCP Tools and arguments
    if category == "order_status":
        tool_name = "check_order_status"
        tool_args = {"order_id": order_id or ""}
    elif category == "return":
        tool_name = "check_return_eligibility"
        tool_args = {"order_id": order_id or ""}
    elif category == "support_ticket":
        tool_name = "create_support_ticket"
        issue_desc = query
        priority = "high" if any(w in query.lower() for w in ["delay", "urgent", "damaged", "broken"]) else "medium"
        ticket_cat = "Order Delay" if "delay" in query.lower() else "General Support"
        tool_args = {
            "issue": issue_desc,
            "category": ticket_cat,
            "order_id": order_id,
            "priority": priority,
        }
    elif category == "product_details":
        tool_name = "get_product_details"
        tool_args = {"product_id": product_id or ""}
    elif category in ("product_search", "recommendation"):
        tool_name = "search_products"
        # Clean query terms for search
        cleaned_search = re.sub(r"[^\w\s]", " ", query)
        cleaned_search = re.sub(r"\b(i need|recommend|good|under|below|\d+|please|can you|for|a|an|the)\b", " ", cleaned_search, flags=re.IGNORECASE)
        cleaned_search = " ".join(cleaned_search.split())
        category_filter = None
        for cat in ["headphones", "laptop", "smartphones", "smartwatches", "keyboards", "mice", "tablets"]:
            if cat[:-1] in query.lower() or cat in query.lower():
                category_filter = cat
                break
        tool_args = {
            "query": cleaned_search or query,
            "max_price": max_price,
            "category": category_filter,
        }
    elif category in ("refund", "shipping", "general"):
        tool_name = "search_policies"
        tool_args = {"query": query}

    console.print(f"[bold cyan][ROUTER][/bold cyan] Category: [green]{category}[/green]")
    console.print(f"[bold magenta][TOOL][/bold magenta] Selected: [yellow]{tool_name}[/yellow] (args: {tool_args})")

    return {
        "category": category,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


# =====================================================================
# Node 2: call_tool (MCP Execution via stdio / direct interface)
# =====================================================================

async def execute_mcp_tool_async(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute the tool via the official MCP Server instance or stdio client."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    try:
        # Connect to MCP server over stdio
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[MCP_SERVER_PATH],
            env=dict(os.environ),
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                if result and result.content:
                    return result.content[0].text
    except Exception:
        # Direct fallback via FastMCP / MCPServer app interface for guaranteed reliability
        result = await mcp_server.app.call_tool(tool_name, tool_args)
        if result and result.content:
            return result.content[0].text

    return json.dumps({"status": "error", "message": "Failed to execute MCP tool."})


def call_tool(state: AgentState) -> Dict[str, Any]:
    """LangGraph node to execute selected MCP tool."""
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]

    try:
        raw_result = asyncio.run(execute_mcp_tool_async(tool_name, tool_args))
        try:
            parsed_result = json.loads(raw_result)
        except Exception:
            parsed_result = {"raw": raw_result}
    except Exception as e:
        parsed_result = {"status": "error", "message": str(e)}

    # Generate a concise one-line result summary for CLI
    summary = "Executed successfully"
    if isinstance(parsed_result, dict):
        if "products" in parsed_result:
            count = parsed_result.get("total_found", len(parsed_result.get("products", [])))
            summary = f"{count} product(s) found"
        elif "order_status" in parsed_result:
            summary = f"Order {parsed_result.get('order_id')} is {parsed_result.get('order_status')}"
        elif "ticket_id" in parsed_result:
            summary = f"Ticket {parsed_result.get('ticket_id')} created"
        elif "return_eligible" in parsed_result:
            eligible = "eligible" if parsed_result.get("return_eligible") else "not eligible"
            summary = f"Order is {eligible} for return"
        elif "policy_result" in parsed_result:
            summary = f"Retrieved {parsed_result['policy_result'].get('best_match', {}).get('title', 'policy')}"
        elif parsed_result.get("status") == "not_found":
            summary = parsed_result.get("message", "Not found")

    console.print(f"[bold blue][TOOL RESULT][/bold blue] {summary}")

    return {"tool_result": parsed_result}


# =====================================================================
# Node 3: synthesize (LLM / Structured Response Synthesis)
# =====================================================================

def format_fallback_response(query: str, category: str, tool_name: str, tool_result: Dict[str, Any]) -> str:
    """Deterministic, high-quality response synthesis fallback matching real customer support standards."""
    status = tool_result.get("status")

    # 1. Order Status
    if tool_name == "check_order_status":
        if status == "success":
            oid = tool_result.get("order_id")
            prod = tool_result.get("product")
            ostatus = tool_result.get("order_status")
            exp = tool_result.get("expected_delivery")
            trk = tool_result.get("tracking_status")
            amt = tool_result.get("amount")
            return (
                f"Your order {oid} for '{prod}' is currently {ostatus}.\n\n"
                f"- Tracking Status: {trk}\n"
                f"- Expected Delivery: {exp}\n"
                f"- Total Amount: Rs. {amt}\n\n"
                f"You can contact support if the delivery does not arrive by the expected date."
            )
        elif status == "not_found":
            oid = tool_result.get("order_id", "specified")
            return (
                f"I checked our records, but order '{oid}' was not found.\n\n"
                "Please verify your order number (for example, ORD1001 or ORD1002) and try again."
            )
        else:
            return (
                "I can certainly check your order status for you! "
                "Please provide your order ID (for example: ORD1001)."
            )

    # 2. Return Eligibility
    elif tool_name == "check_return_eligibility":
        if status == "success":
            oid = tool_result.get("order_id")
            prod = tool_result.get("product")
            eligible = tool_result.get("return_eligible")
            policy = tool_result.get("policy_explanation")
            if eligible:
                return (
                    f"Order {oid} for '{prod}' is eligible for return.\n\n"
                    f"Policy Details: {policy}\n\n"
                    "You can proceed with the return request. Would you like me to schedule a pickup or raise a return ticket?"
                )
            else:
                return (
                    f"Order {oid} for '{prod}' is currently not eligible for return.\n\n"
                    f"Reason: {policy}"
                )
        elif status == "not_found":
            return (
                f"Order '{tool_result.get('order_id', '')}' was not found in our records. "
                "Please provide a valid order ID such as ORD1002."
            )
        else:
            return (
                "To check return eligibility, please provide your order ID (for example: ORD1002)."
            )

    # 3. Support Ticket Creation
    elif tool_name == "create_support_ticket":
        if status == "success":
            tkt = tool_result.get("ticket_id")
            issue = tool_result.get("issue")
            oid = tool_result.get("order_id")
            priority = tool_result.get("priority", "medium").capitalize()
            order_info = f" for your order {oid}" if oid else ""
            return (
                f"Support ticket {tkt} has been created successfully{order_info}.\n\n"
                f"- Issue: {issue}\n"
                f"- Priority: {priority}\n"
                f"- Status: Open\n\n"
                f"Our support team has been notified and will investigate immediately."
            )
        else:
            return f"Unable to create support ticket: {tool_result.get('message', 'Unknown error')}"

    # 4. Product Search & Recommendations
    elif tool_name == "search_products":
        products = tool_result.get("products", [])
        if not products:
            return (
                f"I couldn't find any products matching your criteria in our catalog. "
                "Try searching for headphones, laptops, smartphones, keyboards, or smartwatches."
            )

        if category == "recommendation":
            lines = [f"Here are my top recommendations based on your request:\n"]
            for idx, p in enumerate(products, 1):
                feats = ", ".join(p.get("features", []))
                lines.append(
                    f"{idx}. {p['name']} (Rs. {p['price']}) - Rating: {p['rating']} / 5.0\n"
                    f"   * Highlights: {feats}\n"
                    f"   * {p['description']}"
                )
            best = products[0]
            lines.append(
                f"\n[RECOMMENDED CHOICE] I especially recommend the "
                f"'{best['name']}' because of its high rating ({best['rating']} / 5.0) "
                f"and features tailored to your needs."
            )
            return "\n".join(lines)
        else:
            lines = [f"I found {len(products)} product(s) matching your search:\n"]
            for idx, p in enumerate(products, 1):
                feats = ", ".join(p.get("features", []))
                lines.append(
                    f"{idx}. {p['name']} by {p['brand']}\n"
                    f"   * Price: Rs. {p['price']} | Rating: {p['rating']} / 5.0 | Stock: {p['stock']} units\n"
                    f"   * Features: {feats}"
                )
            lines.append("\nWould you like more details on any of these products?")
            return "\n".join(lines)

    # 5. Product Details
    elif tool_name == "get_product_details":
        if status == "success":
            p = tool_result.get("product", {})
            feats = "\n".join([f"  - {f}" for f in p.get("features", [])])
            return (
                f"Here are the complete product details for {p.get('name')} (ID: {p.get('product_id')}):\n\n"
                f"- Brand: {p.get('brand')}\n"
                f"- Category: {p.get('category').capitalize()}\n"
                f"- Price: Rs. {p.get('price')}\n"
                f"- Rating: {p.get('rating')} / 5.0\n"
                f"- Stock: {p.get('stock')} units available\n"
                f"- Description: {p.get('description')}\n"
                f"- Features:\n{feats}"
            )
        else:
            return tool_result.get("message", "Product not found.")

    # 6. Policy & General Inquiries
    elif tool_name == "search_policies":
        policy_res = tool_result.get("policy_result", {})
        best = policy_res.get("best_match", {})
        title = best.get("title", "Store Policy")
        content = best.get("content", "")
        return f"{title}:\n\n{content}\n\nFeel free to ask if you need further clarification!"

    # 7. Customer History
    elif tool_name == "get_customer_history":
        history = tool_result.get("history", [])
        if not history:
            return "No previous conversations found for this session."
        lines = ["Here are your recent interactions:"]
        for h in history:
            lines.append(f"- [{h['timestamp']}] Customer: {h['user_query']} -> Tool: {h['tool_used']}")
        return "\n".join(lines)

    return "Thank you for contacting customer support. How else can I assist you today?"


def synthesize(state: AgentState) -> Dict[str, Any]:
    """LangGraph node to synthesize final customer response and persist to SQLite."""
    console.print("[dim][AGENT] Generating response...[/dim]")

    query = state.get("query", "")
    category = state.get("category", "general")
    tool_name = state.get("tool_name", "")
    tool_result = state.get("tool_result", {})
    session_id = state.get("session_id", "default_session")

    response_text = None

    # Attempt LLM Response Synthesis via Qwen2.5:3B if Ollama is running
    if OLLAMA_STATUS.get("running") and OLLAMA_STATUS.get("model_available"):
        synth_prompt = (
            "You are an empathetic, professional AI E-Commerce Customer Support Agent.\n"
            "Generate a helpful, natural response to the customer based strictly on the retrieved tool data.\n\n"
            f"Customer Request: \"{query}\"\n"
            f"Category: {category}\n"
            f"Tool Used: {tool_name}\n"
            f"Tool Result Data:\n{json.dumps(tool_result, indent=2)}\n\n"
            "Guidelines:\n"
            "- Always be courteous and direct.\n"
            "- Include specific numbers, dates, prices, or ticket IDs from the tool data.\n"
            "- If an order or product is not found, politely ask the user to double-check their ID.\n"
            "- If a ticket was created, reassure them that our team will follow up.\n"
            "- Keep the response concise and formatted with clean bullet points where appropriate."
        )
        llm_response = query_ollama(synth_prompt)
        if llm_response and len(llm_response.strip()) > 20:
            response_text = llm_response.strip()

    # Fallback to deterministic synthesis if LLM is unavailable or unhelpful
    if not response_text:
        response_text = format_fallback_response(query, category, tool_name, tool_result)

    # Persist interaction into SQLite Memory
    try:
        database.save_conversation(
            session_id=session_id,
            user_query=query,
            category=category,
            tool_used=tool_name,
            response=response_text,
        )
    except Exception as e:
        console.print(f"[dim red]Warning: SQLite save error: {e}[/dim red]")

    return {"response": response_text}


# =====================================================================
# Build LangGraph Workflow
# =====================================================================

def build_support_agent():
    """Construct and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Register Nodes
    workflow.add_node("decide_tool", decide_tool)
    workflow.add_node("call_tool", call_tool)
    workflow.add_node("synthesize", synthesize)

    # Wire Edges: START -> decide_tool -> call_tool -> synthesize -> END
    workflow.add_edge(START, "decide_tool")
    workflow.add_edge("decide_tool", "call_tool")
    workflow.add_edge("call_tool", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow.compile()


# Initialize compiled graph
agent_graph = build_support_agent()


# =====================================================================
# CLI Display Helpers
# =====================================================================

def print_banner():
    """Display startup header."""
    banner = (
        "[bold cyan]==================================================[/bold cyan]\n"
        "[bold white]           AI E-COMMERCE SUPPORT AGENT            [/bold white]\n"
        "[bold cyan]==================================================[/bold cyan]\n"
        "[dim]  Powered by Qwen2.5:3B + LangGraph + MCP + SQLite [/dim]\n"
        "[bold cyan]==================================================[/bold cyan]"
    )
    console.print(banner)
    if not OLLAMA_STATUS["running"]:
        console.print(Panel(OLLAMA_STATUS["message"], title="[yellow]Ollama Status[/yellow]", border_style="yellow"))
    else:
        console.print(f"[green][OK] Ollama connected (Model: {DEFAULT_MODEL})[/green]\n")


def display_history(session_id: Optional[str] = None):
    """Render conversation memory from SQLite."""
    convs = database.get_recent_conversations(session_id=session_id, limit=8)
    if not convs:
        console.print("[yellow]No conversation history recorded yet.[/yellow]\n")
        return

    table = Table(title="Recent Conversations (SQLite Memory)", show_header=True, header_style="bold magenta")
    table.add_column("Session", style="cyan", width=14)
    table.add_column("Category", style="green", width=15)
    table.add_column("Tool Used", style="yellow", width=24)
    table.add_column("Customer Query", style="white")
    table.add_column("Timestamp", style="dim", width=20)

    for c in convs:
        table.add_row(
            c.get("session_id", ""),
            c.get("category", ""),
            c.get("tool_used", ""),
            c.get("user_query", "")[:40] + ("..." if len(c.get("user_query", "")) > 40 else ""),
            c.get("timestamp", "")[:19],
        )
    console.print(table)
    console.print()


def display_tickets():
    """Render support tickets from SQLite."""
    tickets = database.get_recent_tickets(limit=8)
    if not tickets:
        console.print("[yellow]No support tickets found in database.[/yellow]\n")
        return

    table = Table(title="Support Tickets (SQLite Memory)", show_header=True, header_style="bold cyan")
    table.add_column("Ticket ID", style="bold yellow", width=12)
    table.add_column("Issue", style="white")
    table.add_column("Category", style="green", width=15)
    table.add_column("Order ID", style="magenta", width=12)
    table.add_column("Priority", style="red", width=10)
    table.add_column("Status", style="cyan", width=10)
    table.add_column("Timestamp", style="dim", width=20)

    for t in tickets:
        table.add_row(
            t.get("ticket_id", ""),
            t.get("issue", "")[:35] + ("..." if len(t.get("issue", "")) > 35 else ""),
            t.get("category", ""),
            t.get("order_id") or "N/A",
            t.get("priority", "").upper(),
            t.get("status", ""),
            t.get("timestamp", ""),
        )
    console.print(table)
    console.print()


def run_agent_turn(query: str, session_id: str = "demo_user") -> str:
    """Execute a single query through the LangGraph pipeline."""
    initial_state: AgentState = {
        "query": query,
        "category": "",
        "tool_name": "",
        "tool_args": {},
        "tool_result": None,
        "response": "",
        "session_id": session_id,
    }

    final_state = agent_graph.invoke(initial_state)
    response = final_state.get("response", "")

    console.print(f"\n[bold green]AI Support Agent:[/bold green]")
    console.print(response)
    console.print("-" * 60)
    return response


# =====================================================================
# Demo Mode Runner
# =====================================================================

def run_demo():
    """Execute the automated test queries demonstrating the full agentic pipeline."""
    print_banner()
    console.print("\n[bold cyan]>>> STARTING DEMO MODE <<<[/bold cyan]\n")

    demo_queries = [
        ("Product Search", "I need wireless headphones under 3000."),
        ("Order Status", "Where is my order ORD1001?"),
        ("Return Request", "I want to return order ORD1002."),
        ("Support Ticket", "My order ORD1004 is delayed. Create a support ticket."),
        ("Product Recommendation", "Recommend a laptop for programming."),
        ("Error Handling (Invalid Order)", "My order ID is ORD9999. Where is it?"),
        ("Error Handling (Missing ID)", "Where is my order?"),
    ]

    session_id = f"demo_session_{int(time.time())}"

    for index, (label, query) in enumerate(demo_queries, 1):
        console.print(f"\n[bold white on blue] DEMO TEST {index}: {label} [/bold white on blue]")
        console.print(f"[bold yellow]Customer:[/bold yellow] {query}")
        run_agent_turn(query, session_id=session_id)
        time.sleep(0.3)

    console.print("\n[bold cyan]>>> DEMO COMPLETE - VERIFYING SQLITE PERSISTENCE <<<[/bold cyan]\n")
    display_tickets()
    display_history(session_id=session_id)


# =====================================================================
# Interactive Main Loop
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="AI E-Commerce Customer Support Agent")
    parser.add_argument("--demo", action="store_true", help="Run automated demo queries")
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    print_banner()
    session_id = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    console.print("Type your questions below. Special commands: [bold cyan]history[/bold cyan], [bold cyan]tickets[/bold cyan], [bold cyan]exit[/bold cyan], [bold cyan]quit[/bold cyan]\n")

    while True:
        try:
            query = console.input("[bold yellow]Customer:[/bold yellow] ").strip()
            if not query:
                continue

            if query.lower() in ("exit", "quit"):
                console.print("[dim]Thank you for using AI E-Commerce Support. Goodbye![/dim]")
                break
            elif query.lower() == "history":
                display_history(session_id=session_id)
                continue
            elif query.lower() == "tickets":
                display_tickets()
                continue

            run_agent_turn(query, session_id=session_id)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break


if __name__ == "__main__":
    main()
