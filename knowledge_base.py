"""Local Knowledge Base for E-Commerce Policies.

Contains policy definitions for:
- Shipping Policy
- Return Policy
- Refund Policy
- Cancellation Policy
- Payment Information
- Delivery Information
- Warranty Information
"""

from typing import Dict, Any, List


KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "return_policy": {
        "title": "Return Policy",
        "keywords": ["return", "returns", "exchange", "replacement", "eligible", "send back"],
        "content": (
            "Products can be returned within 7 days of delivery if they meet the return conditions. "
            "Items must be unused, in their original packaging, with all accessories, user manuals, "
            "and intact warranty seals. Once a return request is accepted, a courier pickup is scheduled "
            "within 2-3 business days. Damaged or altered items are not eligible for return."
        ),
    },
    "refund_policy": {
        "title": "Refund Policy",
        "keywords": ["refund", "refunds", "money back", "reimbursement", "credit"],
        "content": (
            "Refunds are processed after the returned product is received at our fulfillment center "
            "and passes physical inspection (typically 2-4 business days after pickup). "
            "Once approved, the refund is initiated to the original payment method within 5-7 business days. "
            "For Cash on Delivery (COD) orders, refunds are credited directly to the provided bank account or store credits."
        ),
    },
    "shipping_policy": {
        "title": "Shipping Policy",
        "keywords": ["ship", "shipping", "courier", "dispatch", "transit", "shipping charge"],
        "content": (
            "Orders are dispatched within 24-48 hours of confirmation. Standard delivery takes 3-6 business days "
            "depending on the destination pincode. We offer free standard shipping on orders above 999. "
            "Expedited shipping (1-2 business days) is available in select metro areas for an additional charge of 149."
        ),
    },
    "delivery_information": {
        "title": "Delivery Information",
        "keywords": ["delivery", "deliver", "expected delivery", "tracking", "track", "delayed", "late"],
        "content": (
            "Customers receive a live tracking link via SMS/Email once the order is shipped. Delivery agents will attempt "
            "up to 3 delivery attempts before the shipment is returned to origin. If your delivery is delayed past the "
            "expected date due to adverse weather or transit route issues, our customer support team can escalate and raise a ticket."
        ),
    },
    "cancellation_policy": {
        "title": "Cancellation Policy",
        "keywords": ["cancel", "cancellation", "abort", "stop order"],
        "content": (
            "Orders can be cancelled at any time before they enter the 'Shipped' status directly from the order page "
            "or via customer support. Once an order has been shipped, it cannot be cancelled directly; the customer can "
            "either refuse delivery upon arrival or initiate a standard return post-delivery."
        ),
    },
    "payment_information": {
        "title": "Payment Information",
        "keywords": ["pay", "payment", "card", "upi", "netbanking", "cod", "cash on delivery", "emi"],
        "content": (
            "We support all major payment methods including Credit Cards (Visa, MasterCard, Amex), Debit Cards, "
            "UPI (Google Pay, PhonePe, Paytm), Net Banking across 50+ banks, and Cash on Delivery (COD) on eligible items. "
            "No-cost EMI is available on select credit cards for purchases above 3000."
        ),
    },
    "warranty_information": {
        "title": "Warranty Information",
        "keywords": ["warranty", "guarantee", "repair", "service center", "defect"],
        "content": (
            "All electronic products sold come with an official 1-Year manufacturer warranty covering technical and manufacturing "
            "defects. Accessories like charging cables, adapters, and batteries typically carry a 6-month warranty. "
            "Physical damage, water exposure (unless explicitly rated), and unauthorized tampering are not covered under warranty."
        ),
    },
}


def search_knowledge_base(query: str) -> Dict[str, Any]:
    """Search knowledge base policies matching keywords in query.

    Args:
        query: Customer query or policy topic.

    Returns:
        Dictionary containing matched policy information.
    """
    if not query or not query.strip():
        return {
            "found": False,
            "message": "Empty query provided.",
            "policies": [],
        }

    query_lower = query.lower()
    matches: List[Dict[str, Any]] = []

    for key, policy in KNOWLEDGE_BASE.items():
        score = 0
        for kw in policy["keywords"]:
            if kw in query_lower:
                score += 1
        if score > 0:
            matches.append({
                "key": key,
                "title": policy["title"],
                "content": policy["content"],
                "match_score": score,
            })

    # Sort by match score descending
    matches.sort(key=lambda x: x["match_score"], reverse=True)

    if matches:
        return {
            "found": True,
            "best_match": matches[0],
            "policies": matches,
        }

    # Fallback to general policies overview if no specific match
    return {
        "found": True,
        "best_match": {
            "key": "general",
            "title": "General Store Policy",
            "content": (
                "Our store offers standard 7-day returns on eligible items, refunds within 5-7 business days "
                "post-inspection, reliable 3-6 day shipping, and 1-year manufacturer warranty on all electronics."
            ),
        },
        "policies": [],
    }


def get_all_topics() -> List[str]:
    """Return all available policy topic names."""
    return [p["title"] for p in KNOWLEDGE_BASE.values()]
