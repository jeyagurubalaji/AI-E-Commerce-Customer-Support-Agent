"""Model Context Protocol (MCP) Server for E-Commerce Customer Support.

Exposes standard MCP tools:
1. search_products
2. get_product_details
3. check_order_status
4. check_return_eligibility
5. create_support_ticket
6. get_customer_history
7. search_policies
"""

import json
import os
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer
import database
import knowledge_base


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(BASE_DIR, "data", "products.json")
ORDERS_FILE = os.path.join(BASE_DIR, "data", "orders.json")


def load_products() -> List[Dict[str, Any]]:
    """Load products from products.json."""
    if not os.path.exists(PRODUCTS_FILE):
        return []
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_orders() -> List[Dict[str, Any]]:
    """Load orders from orders.json."""
    if not os.path.exists(ORDERS_FILE):
        return []
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Initialize MCP Server
app = MCPServer("ecommerce_support_server")


@app.tool()
def search_products(
    query: str,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
) -> str:
    """Search products database by keyword query, optional max price, and optional category.

    Args:
        query: Search term (e.g. 'wireless headphones', 'laptop', 'mouse').
        max_price: Maximum price filter (optional).
        category: Product category filter (optional).
    """
    products = load_products()
    query_lower = (query or "").lower().strip()
    category_lower = (category or "").lower().strip() if category else None

    results = []
    for p in products:
        # Category filter
        if category_lower and category_lower not in p.get("category", "").lower():
            continue

        # Max price filter
        if max_price is not None and float(p.get("price", 0)) > float(max_price):
            continue

        # Keyword matching across name, description, brand, category, features
        if query_lower:
            text_corpus = " ".join([
                p.get("name", ""),
                p.get("description", ""),
                p.get("brand", ""),
                p.get("category", ""),
                " ".join(p.get("features", [])),
            ]).lower()

            words = query_lower.split()
            # If any significant query word is present
            if any(w in text_corpus for w in words if len(w) > 2) or query_lower in text_corpus:
                results.append(p)
        else:
            results.append(p)

    if not results:
        filters_applied = []
        if query:
            filters_applied.append(f"query '{query}'")
        if max_price:
            filters_applied.append(f"max price Rs. {max_price}")
        if category:
            filters_applied.append(f"category '{category}'")
        filter_str = " and ".join(filters_applied) if filters_applied else "criteria"
        return json.dumps({
            "status": "not_found",
            "message": f"No products matching {filter_str} were found in the catalog.",
            "products": [],
        }, indent=2)

    # Sort results by rating descending
    results.sort(key=lambda x: x.get("rating", 0), reverse=True)

    summary_list = []
    for p in results[:5]:  # Return top 5 matches
        summary_list.append({
            "product_id": p["product_id"],
            "name": p["name"],
            "category": p["category"],
            "brand": p["brand"],
            "price": p["price"],
            "rating": p["rating"],
            "stock": p["stock"],
            "features": p["features"][:3],
            "description": p["description"],
        })

    return json.dumps({
        "status": "success",
        "total_found": len(results),
        "products": summary_list,
    }, indent=2)


@app.tool()
def get_product_details(product_id: str) -> str:
    """Retrieve full details of a specific product by its ID.

    Args:
        product_id: Unique product ID (e.g. 'P1001').
    """
    if not product_id or not product_id.strip():
        return json.dumps({"status": "error", "message": "Please provide a valid product ID."}, indent=2)

    pid_clean = product_id.strip().upper()
    products = load_products()

    for p in products:
        if p.get("product_id", "").upper() == pid_clean:
            return json.dumps({
                "status": "success",
                "product": p,
            }, indent=2)

    return json.dumps({
        "status": "not_found",
        "message": f"Product with ID '{product_id}' was not found in our catalog.",
    }, indent=2)


@app.tool()
def check_order_status(order_id: str) -> str:
    """Check the real-time shipping and delivery status of a customer order.

    Args:
        order_id: The order identifier (e.g. 'ORD1001').
    """
    if not order_id or not order_id.strip():
        return json.dumps({
            "status": "error",
            "message": "Order ID is required. Please specify your order number (e.g., ORD1001).",
        }, indent=2)

    oid_clean = order_id.strip().upper()
    orders = load_orders()

    for o in orders:
        if o.get("order_id", "").upper() == oid_clean:
            return json.dumps({
                "status": "success",
                "order_id": o["order_id"],
                "product": o["product"],
                "order_status": o["status"],
                "tracking_status": o["tracking_status"],
                "expected_delivery": o["expected_delivery"],
                "amount": o["amount"],
                "return_eligible": o["return_eligible"],
            }, indent=2)

    return json.dumps({
        "status": "not_found",
        "order_id": order_id,
        "message": f"Order '{order_id}' was not found. Please double-check your order number (example: ORD1001, ORD1002).",
    }, indent=2)


@app.tool()
def check_return_eligibility(order_id: str) -> str:
    """Check whether a specific order is eligible for return or replacement.

    Args:
        order_id: The order identifier (e.g. 'ORD1002').
    """
    if not order_id or not order_id.strip():
        return json.dumps({
            "status": "error",
            "message": "Order ID is required to check return eligibility (e.g., ORD1002).",
        }, indent=2)

    oid_clean = order_id.strip().upper()
    orders = load_orders()

    for o in orders:
        if o.get("order_id", "").upper() == oid_clean:
            eligible = bool(o.get("return_eligible", False))
            status = o.get("status", "")
            product = o.get("product", "")

            if eligible:
                policy_note = (
                    "Order is within the 7-day return window. Item must be in original condition "
                    "with intact packaging, tags, and all accessories."
                )
            else:
                policy_note = (
                    f"Order is not eligible for return. Current status is '{status}' or the "
                    "7-day return window has expired."
                )

            return json.dumps({
                "status": "success",
                "order_id": o["order_id"],
                "product": product,
                "order_status": status,
                "return_eligible": eligible,
                "policy_explanation": policy_note,
            }, indent=2)

    return json.dumps({
        "status": "not_found",
        "order_id": order_id,
        "message": f"Order '{order_id}' was not found. Please provide a valid order ID.",
    }, indent=2)


@app.tool()
def create_support_ticket(
    issue: str,
    category: str = "General Support",
    order_id: Optional[str] = None,
    priority: str = "medium",
) -> str:
    """Create a new customer support ticket in SQLite database.

    Args:
        issue: Description of customer issue or problem.
        category: Ticket category (e.g. 'Order Delay', 'Return', 'Refund', 'Product Defect').
        order_id: Associated order ID if applicable (e.g. 'ORD1004').
        priority: Priority level ('low', 'medium', 'high', 'urgent').
    """
    if not issue or not issue.strip():
        return json.dumps({"status": "error", "message": "Issue description cannot be empty."}, indent=2)

    ticket_id = database.create_ticket(
        issue=issue.strip(),
        category=category,
        order_id=order_id.strip().upper() if order_id else None,
        priority=priority,
    )

    return json.dumps({
        "status": "success",
        "ticket_id": ticket_id,
        "issue": issue.strip(),
        "category": category,
        "order_id": order_id.strip().upper() if order_id else None,
        "priority": priority,
        "message": f"Support ticket {ticket_id} created successfully.",
    }, indent=2)


@app.tool()
def get_customer_history(session_id: str) -> str:
    """Retrieve recent conversation history and interactions for a given session.

    Args:
        session_id: The session or customer identifier.
    """
    history = database.get_recent_conversations(session_id=session_id, limit=5)
    return json.dumps({
        "status": "success",
        "session_id": session_id,
        "history_count": len(history),
        "history": history,
    }, indent=2)


@app.tool()
def search_policies(query: str) -> str:
    """Search knowledge base for shipping, return, refund, cancellation, payment, or warranty policy.

    Args:
        query: Policy question or topic (e.g. 'refund policy', 'shipping duration', 'warranty').
    """
    result = knowledge_base.search_knowledge_base(query)
    return json.dumps({
        "status": "success",
        "query": query,
        "policy_result": result,
    }, indent=2)


if __name__ == "__main__":
    app.run()
