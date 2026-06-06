"""Generate architecture diagram PNGs for BAO_CAO Word document."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT_DIR = Path(__file__).parent / "images" / "architecture"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Couture AI palette
C_PRIMARY = "#1e40af"
C_ACCENT = "#0d9488"
C_BOX = "#eff6ff"
C_BORDER = "#1e293b"
C_ARROW = "#475569"
C_TEXT = "#0f172a"
C_MUTED = "#64748b"


def _save(fig: plt.Figure, name: str) -> Path:
    path = OUT_DIR / name
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return path


def _box(ax, x, y, w, h, text, *, fc=C_BOX, fontsize=9, bold=False):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.4,
        edgecolor=C_BORDER,
        facecolor=fc,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=C_TEXT, weight=weight, wrap=True)


def _arrow(ax, x1, y1, x2, y2, *, style="-|>", color=C_ARROW):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle=style,
            mutation_scale=12,
            linewidth=1.2,
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def _setup_ax(w=14, h=8):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def fig_3_1_use_case() -> Path:
    fig, ax = _setup_ax(14, 9)
    _box(ax, 7, 8.2, 8, 0.9, "AI Fashion Recommendation System\n(Couture AI)", fc="#dbeafe", fontsize=11, bold=True)

    actors = [
        (1.5, 6.2, "Guest", ["View Landing", "View Demo"]),
        (4.5, 6.2, "End User", ["Register / Login", "Chat with AI", "Get Recommendations", "Browse Trends", "Save Favorites"]),
        (8.5, 6.2, "Admin", ["View Analytics", "Admin Insights"]),
        (12, 6.2, "Superadmin", ["Bootstrap", "System Config"]),
    ]
    for x, y, title, cases in actors:
        _box(ax, x, y, 2.4, 0.7, title, fc="#fef3c7", fontsize=9, bold=True)
        _arrow(ax, x, y - 0.35, x, 5.0)
        for i, case in enumerate(cases):
            cy = 4.5 - i * 0.55
            _box(ax, x, cy, 2.5, 0.45, case, fontsize=7.5)
            _arrow(ax, x, 5.0, x, cy + 0.23)

    ax.text(7, 0.4, "Hình 3.1 — Use Case Diagram", ha="center", fontsize=10, color=C_MUTED)
    return _save(fig, "fig_3_1_use_case.png")


def fig_3_2_activity() -> Path:
    fig, ax = _setup_ax(10, 14)
    steps = [
        "Start: User nhập message\n(+ optional image)",
        "Validate JWT & Rate Limit",
        "Load / Create Conversation",
        "RAG: embed query → search KB + chat_memory",
        "Build system prompt + history + KB context",
        "Detect outfit intent?",
        "Yes → Hybrid Recommendation Engine\n→ LLM re-rank → attach payload",
        "No → Skip recommendation",
        "Stream LLM tokens via SSE",
        "Save messages → PostgreSQL",
        "Index chat_memory → Qdrant",
        "Log analytics event",
        "End: SSE done + recommendations",
    ]
    y = 13.2
    for i, step in enumerate(steps):
        h = 0.9 if "\n" in step else 0.65
        fc = "#fef9c3" if "intent" in step else C_BOX
        _box(ax, 5, y, 7.5, h, step, fc=fc, fontsize=8.5)
        if i > 0 and i != 6:
            _arrow(ax, 5, y + h / 2 + 0.15, 5, y + h / 2 + 0.55)
        y -= h + 0.35
    _arrow(ax, 5, 8.9, 3.2, 7.8)
    ax.text(3.2, 8.2, "Yes", fontsize=8, color=C_ACCENT, weight="bold")
    _arrow(ax, 5, 8.9, 6.8, 7.8)
    ax.text(6.8, 8.2, "No", fontsize=8, color=C_MUTED, weight="bold")
    return _save(fig, "fig_3_2_activity.png")


def fig_3_3_login_sequence() -> Path:
    fig, ax = _setup_ax(14, 7)
    cols = [("User", 1.5), ("Frontend\n(Next.js)", 4.5), ("Backend\n(FastAPI)", 8), ("PostgreSQL", 11.5)]
    y_top = 6.2
    for label, x in cols:
        ax.plot([x, x], [0.8, y_top], color=C_MUTED, linewidth=1, linestyle="--")
        _box(ax, x, y_top, 2.2, 0.7, label, fontsize=8, bold=True)

    messages = [
        (1.5, 4.5, 4.5, 4.5, "POST /login"),
        (4.5, 4.0, 8, 4.0, "POST /auth/login"),
        (8, 3.5, 11.5, 3.5, "verify bcrypt"),
        (11.5, 3.0, 8, 3.0, "user row"),
        (8, 2.5, 11.5, 2.5, "create refresh token"),
        (8, 2.0, 4.5, 2.0, "access + refresh JWT"),
        (4.5, 1.5, 1.5, 1.5, "set HttpOnly cookies"),
        (1.5, 1.0, 4.5, 1.0, "API call + Bearer"),
        (4.5, 0.5, 8, 0.5, "decode JWT → 200 OK"),
    ]
    for x1, y1, x2, y2, label in messages:
        _arrow(ax, x1, y1, x2, y2)
        ax.text((x1 + x2) / 2, y1 + 0.12, label, ha="center", fontsize=7, color=C_TEXT)
    return _save(fig, "fig_3_3_login_sequence.png")


def fig_3_4_chat_sequence() -> Path:
    fig, ax = _setup_ax(16, 7)
    cols = [
        ("User", 1),
        ("Frontend", 3.5),
        ("ChatService", 6.5),
        ("RAG/Qdrant", 9.5),
        ("OpenAI", 12),
        ("Postgres", 14.5),
    ]
    y_top = 6.2
    for label, x in cols:
        ax.plot([x, x], [0.5, y_top], color=C_MUTED, linewidth=1, linestyle="--")
        _box(ax, x, y_top, 2.0, 0.65, label, fontsize=7.5, bold=True)

    flows = [
        (1, 5.2, 3.5, 5.2, "message"),
        (3.5, 4.7, 6.5, 4.7, "POST /chat/stream"),
        (6.5, 4.2, 9.5, 4.2, "retrieve_context"),
        (9.5, 3.7, 6.5, 3.7, "KB docs"),
        (6.5, 3.2, 12, 3.2, "stream completion"),
        (12, 2.7, 6.5, 2.7, "token chunks"),
        (6.5, 2.2, 3.5, 2.2, "SSE token"),
        (3.5, 1.7, 1, 1.7, "render UI"),
        (6.5, 1.2, 14.5, 1.2, "save messages"),
        (6.5, 0.8, 3.5, 0.8, "SSE done + recommendations"),
    ]
    for x1, y1, x2, y2, label in flows:
        _arrow(ax, x1, y1, x2, y2)
        ax.text((x1 + x2) / 2, y1 + 0.1, label, ha="center", fontsize=6.5, color=C_TEXT)
    return _save(fig, "fig_3_4_chat_sequence.png")


def fig_3_5_erd() -> Path:
    fig, ax = _setup_ax(16, 10)
    entities = [
        (2.5, 8, "users", ["id PK", "email", "role", "preferences"]),
        (7, 8, "conversations", ["id PK", "user_id FK", "title"]),
        (11.5, 8, "messages", ["id PK", "convo_id FK", "role", "content"]),
        (2.5, 5.5, "favorite_outfits", ["user_id FK", "outfit_id FK"]),
        (7, 5.5, "outfits", ["id PK", "name, style", "brand, price", "tags[], meta"]),
        (11.5, 5.5, "outfit_items", ["outfit_id FK", "category", "name"]),
        (7, 2.8, "recommendations", ["user_id FK", "items JSON", "reasoning"]),
        (2, 1.2, "fashion_trends", ["id PK", "title, tags"]),
        (5.5, 1.2, "sync_runs", ["job_type", "status"]),
        (9, 1.2, "event_logs", ["event_type", "payload"]),
        (12.5, 1.2, "refresh_tokens", ["user_id FK", "token_hash"]),
    ]
    for x, y, name, fields in entities:
        h = 0.35 + len(fields) * 0.32
        patch = FancyBboxPatch(
            (x - 1.3, y - h / 2),
            2.6,
            h,
            boxstyle="square,pad=0",
            linewidth=1.4,
            edgecolor=C_BORDER,
            facecolor=C_BOX,
        )
        ax.add_patch(patch)
        ax.add_patch(
            mpatches.Rectangle((x - 1.3, y + h / 2 - 0.38), 2.6, 0.38, facecolor=C_PRIMARY, edgecolor=C_BORDER)
        )
        ax.text(x, y + h / 2 - 0.19, name, ha="center", va="center", fontsize=8, color="white", weight="bold")
        for i, f in enumerate(fields):
            ax.text(x - 1.15, y + h / 2 - 0.55 - i * 0.32, f, fontsize=7, color=C_TEXT, family="monospace")

    rels = [
        (3.8, 8, 5.7, 8, "1:N"),
        (8.3, 8, 10.2, 8, "1:N"),
        (2.5, 7.2, 2.5, 6.3, "1:N"),
        (3.8, 5.5, 5.7, 5.5, "N:1"),
        (8.3, 5.5, 10.2, 5.5, "1:N"),
        (7, 4.9, 7, 3.5, "1:N"),
    ]
    for x1, y1, x2, y2, label in rels:
        _arrow(ax, x1, y1, x2, y2)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.15, label, fontsize=7, color=C_ACCENT)
    return _save(fig, "fig_3_5_erd.png")


def fig_3_6_deployment() -> Path:
    fig, ax = _setup_ax(12, 9)
    _box(ax, 6, 8, 3, 0.7, "Nginx  :80 / :443", fc="#dbeafe", fontsize=10, bold=True)
    for x, label in [(2.5, "Next.js\n(frontend)\n:3000"), (6, "FastAPI\n(backend)\n:8000"), (9.5, "Static\n(uploads)")]:
        _box(ax, x, 6.2, 2.4, 1.1, label, fontsize=8.5)
        _arrow(ax, x, 7.65, x, 6.75)
    _arrow(ax, 6, 5.65, 6, 4.8)
    for x, label, sub in [
        (2, "PostgreSQL\n:5432", "source of truth"),
        (6, "Redis\n:6379", "cache / rate limit"),
        (10, "Qdrant\n:6333", "vector store"),
    ]:
        _box(ax, x, 3.8, 2.6, 1.0, label, fc="#ecfdf5", fontsize=8.5)
        ax.text(x, 3.15, sub, ha="center", fontsize=7, color=C_MUTED)
        _arrow(ax, 6, 4.8, x, 4.3)
    ax.text(
        6,
        1.5,
        "Docker Compose — fashion-net bridge network\npostgres · redis · qdrant · backend · frontend · nginx",
        ha="center",
        fontsize=8,
        color=C_MUTED,
    )
    return _save(fig, "fig_3_6_deployment.png")


def fig_3_6_1_backend_layers() -> Path:
    fig, ax = _setup_ax(10, 8)
    layers = [
        ("HTTP / WebSocket Layer", "app/api/v1/* · app/api/ws.py", "#dbeafe"),
        ("Service Layer", "app/services/* — use cases & orchestration", "#e0e7ff"),
        ("Repository Layer", "app/repositories/* — async SQLAlchemy", "#ede9fe"),
        ("ORM Models", "app/models/* — PostgreSQL entities", "#fce7f3"),
        ("AI Engine", "ai_engine/* — LLM, RAG, recommender, vision", "#d1fae5"),
        ("Core & Middleware", "security · cache · rate-limit · logging · CORS", "#fef3c7"),
    ]
    y = 7
    for title, desc, fc in layers:
        _box(ax, 5, y, 8.5, 0.55, title, fc=fc, fontsize=10, bold=True)
        ax.text(5, y - 0.45, desc, ha="center", fontsize=8, color=C_MUTED)
        if y < 7:
            _arrow(ax, 5, y + 0.55, 5, y + 0.85)
        y -= 1.15
    return _save(fig, "fig_3_6_1_backend_layers.png")


def fig_3_8_rag() -> Path:
    """RAG pipeline — parallel Qdrant retrieval then merge (matches ai_engine/rag.py)."""
    fig, ax = _setup_ax(12, 10.5)
    cy = 9.3
    _box(ax, 6, cy, 3.2, 0.55, "User Query", fc="#dbeafe", bold=True)
    _arrow(ax, 6, cy - 0.28, 6, cy - 0.75)
    cy = 8.0
    _box(ax, 6, cy, 4.8, 0.65, "embed_text()\nOpenAI Embedding", fc=C_BOX)

    # Parallel vector search (same embedding → 3 Qdrant collections)
    merge_y = 5.35
    branch_y = 6.55
    branches = [
        (2.3, "fashion_kb\n(top_k=6)"),
        (6.0, "chat_memory\n(user_id filter)"),
        (9.7, "optional\ncollections"),
    ]
    for x, label in branches:
        _arrow(ax, 6, cy - 0.33, x, branch_y + 0.38)
        _box(ax, x, branch_y, 2.5, 0.72, label, fc="#ecfdf5", fontsize=8)
        _arrow(ax, x, branch_y - 0.36, 6, merge_y + 0.12)

    pipeline = [
        (4.75, "De-dupe + Rank by score", C_BOX),
        (3.55, "format_kb_block (≤ 4000 chars)", C_BOX),
        (2.35, "System Prompt + LLM\nCompletion / Stream", C_BOX),
        (1.05, "SSE / JSON Response", "#fef3c7"),
    ]
    _arrow(ax, 6, merge_y, 6, pipeline[0][0] + 0.33)
    for i, (y, label, fc) in enumerate(pipeline):
        bold = label.startswith("SSE")
        _box(ax, 6, y, 5.4, 0.62 if "\n" in label else 0.55, label, fc=fc, fontsize=8.5, bold=bold)
        if i < len(pipeline) - 1:
            next_y = pipeline[i + 1][0]
            _arrow(ax, 6, y - 0.31, 6, next_y + 0.31)

    ax.text(
        6,
        0.35,
        "Qdrant: fashion_kb · chat_memory · optional collections",
        ha="center",
        fontsize=7.5,
        color=C_MUTED,
    )
    return _save(fig, "fig_3_8_rag.png")


def fig_3_7_recommendation() -> Path:
    fig, ax = _setup_ax(12, 10)
    _box(ax, 6, 9.2, 9, 0.6, "Inputs: query · profile · filters · image · season · weather", fc="#dbeafe", fontsize=8.5)
    branches = [
        (2.5, "Vector Search\n(Qdrant outfits)"),
        (6, "SQL Content Filter\n(Postgres)"),
        (9.5, "Collaborative\n(Favorites graph)"),
    ]
    for x, label in branches:
        _arrow(ax, 6, 8.9, x, 7.8)
        _box(ax, x, 7.3, 2.8, 0.9, label, fc="#ecfdf5", fontsize=8)
        _arrow(ax, x, 6.85, 6, 5.9)
    extras = ["Profile vector search", "Image match (vision + KNN)"]
    for i, txt in enumerate(extras):
        ax.text(2.5, 6.5 - i * 0.4, f"• {txt}", fontsize=7, color=C_MUTED)
    _arrow(ax, 6, 5.9, 6, 5.53)
    for step, y in [("Merge + Weight (adaptive W)", 5.2), ("LLM Re-ranking + Reasoning", 4.0), ("Persist + Return HybridResult", 2.8)]:
        _box(ax, 6, y, 5, 0.65, step, fc=C_BOX, fontsize=9)
    _arrow(ax, 6, 4.85, 6, 4.33)
    _arrow(ax, 6, 3.65, 6, 3.13)
    return _save(fig, "fig_3_7_recommendation.png")


def _tree_image(name: str, title: str, lines: list[str]) -> Path:
    fig, ax = _setup_ax(11, max(6, len(lines) * 0.28 + 1.5))
    ax.set_facecolor("#1e293b")
    fig.patch.set_facecolor("#1e293b")
    ax.text(0.4, len(lines) * 0.28 + 0.6, title, fontsize=10, color="#94a3b8", family="monospace")
    for i, line in enumerate(lines):
        color = "#e2e8f0"
        if line.strip().startswith("#"):
            color = "#64748b"
        elif "├──" in line or "└──" in line:
            color = "#cbd5e1"
        ax.text(0.4, len(lines) * 0.28 - i * 0.28, line, fontsize=8.5, color=color, family="Consolas", va="top")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, len(lines) * 0.28 + 1)
    ax.axis("off")
    return _save(fig, name)


def fig_backend_structure() -> Path:
    lines = [
        "backend/",
        "├── app/",
        "│   ├── api/v1/          # auth, chat, outfits, recommendations, trends",
        "│   ├── services/        # chat_service, trend_service, auth_service",
        "│   ├── repositories/    # data access layer",
        "│   ├── models/          # SQLAlchemy ORM",
        "│   ├── schemas/         # Pydantic v2 DTOs",
        "│   ├── core/            # security, cache, rate_limit",
        "│   ├── middleware/      # correlation ID, security headers",
        "│   ├── scripts/         # import_hm_catalog, sync_hm_trends",
        "│   └── main.py",
        "├── ai_engine/",
        "│   ├── llm.py · embeddings.py · vector_store.py",
        "│   ├── rag.py · recommender.py · vision.py · prompts.py",
        "├── alembic/             # DB migrations",
        "└── Dockerfile",
    ]
    return _tree_image("fig_backend_structure.png", "Backend project structure", lines)


def fig_frontend_structure() -> Path:
    lines = [
        "frontend/src/",
        "├── app/",
        "│   ├── page.tsx                 # Landing",
        "│   ├── (auth)/login, register",
        "│   └── (app)/",
        "│       ├── chat/page.tsx",
        "│       ├── recommendations/page.tsx",
        "│       ├── trends/page.tsx, [id]/page.tsx",
        "│       ├── outfits/page.tsx",
        "│       ├── profile/page.tsx",
        "│       └── admin/page.tsx",
        "├── components/          # UI, chat, admin",
        "├── lib/                 # api, i18n, trends",
        "└── store/               # auth, chat, locale (Zustand)",
    ]
    return _tree_image("fig_frontend_structure.png", "Frontend project structure", lines)


def fig_hm_pipeline() -> Path:
    fig, ax = _setup_ax(14, 4)
    nodes = [
        (1.5, "RapidAPI\nH&M"),
        (4.5, "HMClient\n(cache/throttle)"),
        (7.5, "import_hm_catalog\n/ sync_hm_trends"),
        (10.5, "PostgreSQL\noutfits table"),
        (13, "embed_texts\n(OpenAI)"),
    ]
    for x, label in nodes:
        _box(ax, x, 2.5, 2.2, 1.0, label, fc="#ecfdf5", fontsize=8)
    for i in range(len(nodes) - 1):
        _arrow(ax, nodes[i][0] + 1.1, 2.5, nodes[i + 1][0] - 1.1, 2.5)
    _box(ax, 7.5, 0.9, 3, 0.55, 'Qdrant "outfits" + sync_runs log', fc="#dbeafe", fontsize=8)
    _arrow(ax, 13, 2.0, 9.5, 1.18)
    _arrow(ax, 10.5, 2.0, 8.5, 1.18)
    return _save(fig, "fig_hm_pipeline.png")


# block index in docx → image filename
BLOCK_IMAGE_MAP: dict[int, str] = {
    298: "fig_3_1_use_case.png",
    307: "fig_3_2_activity.png",
    313: "fig_3_3_login_sequence.png",
    329: "fig_3_4_chat_sequence.png",
    334: "fig_3_5_erd.png",
    340: "fig_3_6_deployment.png",
    355: "fig_3_6_1_backend_layers.png",
    369: "fig_3_8_rag.png",
    374: "fig_3_7_recommendation.png",
    384: "fig_backend_structure.png",
    391: "fig_frontend_structure.png",
    642: "fig_hm_pipeline.png",
}


def generate_all() -> dict[int, Path]:
    generators = {
        298: fig_3_1_use_case,
        307: fig_3_2_activity,
        313: fig_3_3_login_sequence,
        329: fig_3_4_chat_sequence,
        334: fig_3_5_erd,
        340: fig_3_6_deployment,
        355: fig_3_6_1_backend_layers,
        369: fig_3_8_rag,
        374: fig_3_7_recommendation,
        384: fig_backend_structure,
        391: fig_frontend_structure,
        642: fig_hm_pipeline,
    }
    result: dict[int, Path] = {}
    for idx, fn in generators.items():
        path = fn()
        result[idx] = path
        print(f"Generated block {idx}: {path.name}")
    return result


if __name__ == "__main__":
    generate_all()
