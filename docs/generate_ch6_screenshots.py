"""Render docker compose ps and curl latency as terminal-style PNGs."""
from __future__ import annotations

import subprocess
from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "images" / "ui"
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).parent.parent


def _terminal_png(lines: list[str], outfile: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(12, max(3.5, len(lines) * 0.35 + 1.2)))
    ax.set_facecolor("#0f172a")
    fig.patch.set_facecolor("#0f172a")
    ax.text(0.35, len(lines) * 0.35 + 0.55, title, fontsize=10, color="#94a3b8", family="monospace")
    for i, line in enumerate(lines):
        color = "#22c55e" if "healthy" in line.lower() or "200" in line else "#e2e8f0"
        if line.startswith("$"):
            color = "#fbbf24"
        ax.text(0.35, len(lines) * 0.35 - i * 0.35, line, fontsize=9, color=color, family="Consolas", va="top")
    ax.set_xlim(0, 11.5)
    ax.set_ylim(0, len(lines) * 0.35 + 0.8)
    ax.axis("off")
    path = OUT / outfile
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    return path


def docker_ps() -> Path:
    result = subprocess.run(
        ["docker", "compose", "ps"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = ["$ docker compose ps", ""] + result.stdout.strip().splitlines()
    return _terminal_png(lines, "fig_6_1_docker.png", "Hình 6.1 — Docker Compose deployment (localhost)")


def curl_latency() -> Path:
    endpoints = ["/health", "/api/v1/trends?limit=3", "/api/v1/outfits?limit=5"]
    lines = ["$ Performance smoke test (PowerShell Invoke-WebRequest)", ""]
    for ep in endpoints:
        url = f"http://localhost:8000{ep}"
        ps = (
            f'$sw = [System.Diagnostics.Stopwatch]::StartNew(); '
            f'try {{ $r = Invoke-WebRequest -Uri "{url}" -UseBasicParsing -TimeoutSec 30; '
            f'$sw.Stop(); "$($sw.ElapsedMilliseconds) ms HTTP $($r.StatusCode) {ep}" }} '
            f'catch {{ $sw.Stop(); "$($sw.ElapsedMilliseconds) ms ERROR {ep}" }}'
        )
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        lines.append(out.stdout.strip() or out.stderr.strip() or f"ERROR {ep}")
    lines.extend(["", "Environment: Windows 11 + Docker Desktop + Uvicorn workers=2"])
    return _terminal_png(lines, "fig_6_2_curl_latency.png", "Hình 6.2 — API latency observation (dev local)")


if __name__ == "__main__":
    docker_ps()
    curl_latency()
    print("Generated fig_6_1_docker.png and fig_6_2_curl_latency.png")
