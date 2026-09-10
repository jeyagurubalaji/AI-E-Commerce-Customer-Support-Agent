# AI E-Commerce Customer Support Agent

An autonomous, tool-calling Agentic AI Customer Support system built with **LangGraph**, **Model Context Protocol (MCP)**, **Ollama (Qwen2.5:3B)**, and **SQLite Persistent Memory**.

---

## 1. Problem Statement

Traditional customer support bots rely on static rule trees or generic, ungrounded conversational LLMs. Such bots cannot reliably interact with backend systems, frequently hallucinate order statuses or inventory levels, fail to adhere strictly to return policies, and cannot escalate issues by filing real support tickets.

E-commerce platforms require an **agentic system** that dynamically inspects customer intent, selects and executes grounded backend tools via standardized protocols, synthesizes polite contextual responses from real database facts, and persists memory across interactions.

---

## 2. Project Objective

To build an end-to-end, demo-ready Agentic AI E-Commerce Customer Support system capable of:
1. **Catalog Search**: Filtering products by category, keyword, and budget constraints.
2. **Personalized Recommendations**: Analyzing needs (e.g. programming, gaming) and highlighting matching products.
3. **Real-Time Order Tracking**: Checking order and courier delivery status by Order ID.
4. **Return & Policy Evaluation**: Enforcing 7-day return windows and store policy compliance.
5. **Knowledge Base Q&A**: Answering policy inquiries regarding refunds, shipping, cancellations, and warranties.
6. **Support Ticket Creation**: Automatically creating prioritized escalation tickets stored in an SQLite database.
7. **Conversational Memory**: Storing all customer interactions and providing past history retrieval.

---

## 3. Key Features

- **Autonomous Tool Selection**: Uses query classification to choose MCP tools instead of hardcoded if/else branching.
- **Model Context Protocol (MCP) Standard**: Implements a dedicated MCP server exposing tools over standardized stdio transport.
- **Local & Privacy-Preserving LLM**: Integrates with local `qwen2.5:3b` via Ollama with zero external API fees or cloud dependencies.
- **Intelligent Hybrid Fallback**: Operates deterministically even if the local Ollama daemon is temporarily offline or downloading models.
- **Persistent SQLite Memory**: Stores conversation logs and support tickets in `ecommerce_memory.db`.
- **Rich Terminal UI**: Professional interactive command-line interface with status telemetry and formatted data tables.
- **Automated Demo Runner**: One-command automated verification executing realistic customer support scenarios.

---

## 4. Agentic AI Architecture

```
                 CUSTOMER
                     │
                     ▼
              ┌─────────────┐
              │  LANGGRAPH  │
              │    AGENT    │
              └──────┬──────┘
                     │
                     ▼
                QUERY ROUTER
                     │
                     ▼
                TOOL SELECTION
                     │
                     ▼
                MCP SERVER
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
  Product Tools  Order Tools   Support Tools
  - search_prods - check_status - create_ticket
  - get_details  - return_elig  - policies
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                TOOL RESULT
                     │
                     ▼
             QWEN2.5:3B LLM
         (Response Synthesis)
                     │
                     ▼
               FINAL RESPONSE
                     │
                     ▼
                SQLITE MEMORY
        (Conversations & Tickets)
```

### LangGraph State Workflow:

```
[START]
   │
   ▼
[decide_tool]  ──> Classifies intent (LLM/Rule-based) & binds tool arguments
   │
   ▼
[call_tool]    ──> Invokes MCP Server via Stdio Client & captures JSON payload
   │
   ▼
[synthesize]   ──> Grounds answer with tool output & saves interaction to SQLite
   │
   ▼
 [END]
```

---

## 5. Technologies Used

- **Python 3.11+**: Core programming language.
- **LangGraph**: Stateful agentic orchestration graph (`StateGraph`, `START`, `END`).
- **LangChain / LangChain-Ollama**: LLM abstraction and Ollama connectivity.
- **MCP (Model Context Protocol)**: Standardized tool hosting and execution (`mcp`, `stdio_client`).
- **Ollama (`qwen2.5:3b`)**: Lightweight, high-performance local open-weights language model.
- **SQLite3**: Local persistent relational memory.
- **Rich**: Terminal formatting, tables, panels, and colorful log badges.
- **Python-Dotenv**: Environment configuration management.

---

## 6. Project Structure

```
ai_ecommerce_agent/
│
├── agent_client.py       # LangGraph agent, Rich CLI interface, and demo runner
├── mcp_server.py         # MCP server defining and serving 7 e-commerce tools
├── database.py           # SQLite database schema, conversation memory & ticket manager
├── knowledge_base.py     # Local store policies (returns, refunds, shipping, warranties)
├── requirements.txt      # Dependency specification
├── README.md             # Complete user and technical manual
├── PROJECT_REPORT.md     # Comprehensive project & internship submission report
├── .env.example          # Environment variables template
│
└── data/
    ├── products.json     # Product catalog (smartphones, laptops, audio, accessories)
    └── orders.json       # Sample demo order records with statuses and tracking info
```

---

## 7. Installation

### 1. Open Windows PowerShell and navigate to the project directory:

```powershell
cd C:\Users\ELCOT\.gemini\antigravity\scratch\ai_ecommerce_agent
```

### 2. Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies:

```powershell
pip install -r requirements.txt
```

---

## 8. Ollama Setup

1. Download and install Ollama for Windows from [https://ollama.com](https://ollama.com).
2. Start the Ollama application or run in PowerShell:

```powershell
ollama serve
```

3. In a separate PowerShell window, pull the Qwen2.5 3B model:

```powershell
ollama pull qwen2.5:3b
```

> **Note**: If Ollama is not installed or running, the agent automatically displays a clear setup message and seamlessly switches to the hybrid fallback engine so you can evaluate the agent and run the demo immediately.

---

## 9. MCP Server Setup

The MCP Server (`mcp_server.py`) is **automatically launched on-demand** by `agent_client.py` as a managed subprocess using standard MCP stdio transport (`StdioServerParameters`). You do **not** need to manually launch a separate server window.

If you wish to test the MCP server independently:

```powershell
python mcp_server.py
```

---

## 10. Running the Application

### Interactive CLI Mode:

```powershell
python agent_client.py
```

In interactive mode, type your query directly. Built-in management commands:
- `history` — Displays recent customer interactions from SQLite.
- `tickets` — Displays all created support tickets from SQLite.
- `exit` or `quit` — Exits the interactive session.

---

## 11. Demo Mode

To run the automated evaluation suite showcasing the complete Agentic AI workflow across 7 real-world test cases:

```powershell
python agent_client.py --demo
```

---

## 12. Example Queries Tested

| Test Scenario | Sample User Query | Selected MCP Tool |
|---|---|---|
| Product Search | `"I need wireless headphones under 3000."` | `search_products` |
| Order Status | `"Where is my order ORD1001?"` | `check_order_status` |
| Return Request | `"I want to return order ORD1002."` | `check_return_eligibility` |
| Support Escalation | `"My order ORD1004 is delayed. Create a support ticket."` | `create_support_ticket` |
| Recommendation | `"Recommend a laptop for programming."` | `search_products` |
| Error Handling | `"My order ID is ORD9999. Where is it?"` | `check_order_status` |
| Missing Parameter | `"Where is my order?"` | `check_order_status` |
| Policy Inquiry | `"What is your refund policy?"` | `search_policies` |

---

## 13. Expected Output (Demo Sample)

```
==================================================
           AI E-COMMERCE SUPPORT AGENT            
==================================================
  Powered by Qwen2.5:3B + LangGraph + MCP + SQLite 
==================================================

>>> STARTING DEMO MODE <<<

 DEMO TEST 2: Order Status 
Customer: Where is my order ORD1001?
[AGENT] Analyzing request...
[ROUTER] Category: order_status
[TOOL] Selected: check_order_status (args: {'order_id': 'ORD1001'})
[TOOL RESULT] Order ORD1001 is Shipped
[AGENT] Generating response...

AI Support Agent:
Your order ORD1001 for 'SoundMax Wireless Headphones' is currently Shipped.

- Tracking Status: In transit at regional hub
- Expected Delivery: 2026-09-12
- Total Amount: Rs. 2499

You can contact support if the delivery does not arrive by the expected date.
------------------------------------------------------------
```

---

## 14. Limitations

- **Simulated Catalog & Logistics**: Products and orders are loaded from local JSON datasets rather than live ERP or carrier APIs (FedEx/Delhivery).
- **Session-Based State**: SQLite tables track conversations per session ID; enterprise customer accounts with multi-factor authentication are out of prototype scope.
- **Local Hardware Dependency**: Model inference speed depends on CPU/GPU capabilities when running local LLMs via Ollama.

---

## 15. Future Enhancements

1. **Multimodal Support**: Allow customers to upload photos of defective or damaged goods for automated visual inspection using vision models.
2. **Live Logistics Webhooks**: Integrate real-time webhook listeners from carrier shipping APIs.
3. **Vector Semantic Search**: Integrate ChromaDB or LanceDB for semantic hybrid retrieval across thousands of product SKUs.
4. **Voice Agent Integration**: Connect Whisper STT and Kokoro TTS for voice-enabled telephonic support.
