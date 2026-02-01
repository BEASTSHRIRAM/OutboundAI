# 🚀 Outbound AI

### The Operating System for Autonomous Sales Teams

![Hero Image](https://placehold.co/1200x400/1e293b/ffffff?text=Outbound+AI+Mission+Control)

> **Stop prospecting manually. Let AI build your pipeline.**
> Outbound AI is the first autonomous SDR platform that plans, researches, and executes complex outbound campaigns with human-like precision at 100x scale.

---

## ⚡ Why Outbound AI?

Sales teams are drowning in manual tasks—finding emails, researching leads, and writing personalized notes. **Outbound AI** replaces the grunt work with intelligent agents that act as your virtual salesforce.

- **10x Faster Prospecting**: Agents scan millions of profiles in minutes.
- **Hyper-Personalization**: Every email is crafted using real-time insights from news, LinkedIn, and company reports.
- **Human-in-the-Loop**: You maintain control. AI drafts the outreach; you approve it in the Review Queue.

---

## ️ Technology Stack

Built for speed, scalability, and developer joy.

| Component        | Tech                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| **Frontend**     | React 18, Vite, TailwindCSS, shadcn/ui, TanStack Query, Framer Motion, Three.js (R3F) |
| **Backend**      | FastAPI, Python 3.12+, AsyncIO, WebSockets                                            |
| **Database**     | MongoDB (Beanie ODM), Neo4j (Graph DB)                                                |
| **AI & Agents**  | LangChain, LangGraph, Groq/OpenAI                                                     |
| **Integrations** | Firecrawl (Search/Scrape), Composio, Clerk (Auth), Unipile                            |

---

## � Project Structure

```bash
.
├── backend/            # FastAPI backend application
│   ├── app/            # Application logic, models, and routers
│   ├── main.py         # App entry point
│   └── requirements.txt
├── frontend/           # React + Vite frontend application
│   ├── src/            # Components, pages, and hooks
│   └── package.json
└── README.md
```

---

## 🚀 Getting Started

Follow these instructions to run the project locally.

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **MongoDB Instance** (Local or Atlas)
- **Neo4j Instance** (Optional, for Knowledge Graph)

### 1. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory with your configuration:

```ini
# Required
MONGODB_URI=mongodb://localhost:27017
PROJECT_NAME=OutboundAI

# AI & Search Providers (Required for Agent features)
GROQ_API_KEY=your_groq_key
FIRECRAWL_API_KEY=your_firecrawl_key
COMPOSIO_API_KEY=your_composio_key

# Authentication (Clerk)
CLERK_SECRET_KEY=your_clerk_secret_key

# Graph Database (Optional but recommended)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

Start the backend server:

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` (Docs at `/docs`).

### 2. Frontend Setup

Open a new terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
# or if you use bun:
# bun install
```

Create a `.env` file in the `frontend/` directory:

```ini
VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
```

Start the development server:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`.

---

## 🛡️ License

Private & Confidential.
