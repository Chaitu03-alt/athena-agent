"""Personal Adaptive AI Agent CLI (Typer).

Interactive terminal chat interface communicating with the backend REST and SSE streaming API.
"""

import json
import sys
from typing import Optional
import httpx
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

app = typer.Typer(
    name="agent",
    help="Personal Adaptive AI Agent CLI — Chat and manage memory from your terminal.",
    add_completion=False,
)
console = Console()


@app.command()
def chat(
    api_url: str = typer.Option("http://127.0.0.1:8000", "--api-url", "-u", help="Backend API base URL"),
    session_id: Optional[str] = typer.Option(None, "--session-id", "-s", help="Existing session ID to resume"),
    title: Optional[str] = typer.Option("Terminal Chat", "--title", "-t", help="Session title if creating new"),
) -> None:
    """Start an interactive multi-turn chat session with real-time streaming and episodic memory."""
    console.print(
        Panel.fit(
            "[bold cyan]Personal Adaptive AI Agent[/bold cyan] [dim](Phase 1: MVP Chat + Raw Memory)[/dim]\n"
            "Type your message and press Enter. Type [bold yellow]/exit[/bold yellow] or [bold yellow]/quit[/bold yellow] to leave.",
            border_style="cyan",
        )
    )

    client = httpx.Client(base_url=api_url, timeout=60.0)

    # 1. Ensure backend is running
    try:
        health_resp = client.get("/api/health")
        if health_resp.status_code != 200:
            console.print(f"[bold red]Backend returned status {health_resp.status_code}[/bold red]")
            raise typer.Exit(1)
    except Exception as exc:
        console.print(
            f"[bold red]Could not connect to backend at {api_url}:[/bold red] {exc}\n"
            "Please ensure the backend server is running with: [green]uvicorn app.main:app --reload[/green]"
        )
        raise typer.Exit(1)

    # 2. Get or create session
    current_session_id = session_id
    if not current_session_id:
        try:
            create_resp = client.post("/api/sessions", json={"title": title})
            create_resp.raise_for_status()
            session_data = create_resp.json()
            current_session_id = session_data["id"]
            console.print(f"[dim]Started new session: [bold]{current_session_id}[/bold] ({session_data['title']})[/dim]\n")
        except Exception as exc:
            console.print(f"[bold red]Failed to create session:[/bold red] {exc}")
            raise typer.Exit(1)
    else:
        console.print(f"[dim]Connected to session: [bold]{current_session_id}[/bold][/dim]\n")

    # 3. Interactive turn loop
    while True:
        try:
            user_input = console.input("[bold green]You[/bold green] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Goodbye![/dim]")
            break

        # Send message via SSE streaming
        console.print("[bold cyan]Agent[/bold cyan] > ", end="")
        full_response = []
        importance_info = None

        try:
            with client.stream(
                "POST",
                f"/api/sessions/{current_session_id}/messages",
                json={"content": user_input},
            ) as response:
                if response.status_code != 200:
                    console.print(f"\n[bold red]Error from server:[/bold red] {response.status_code}")
                    continue

                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        raw_data = line[6:]
                        try:
                            event = json.loads(raw_data)
                            if event.get("type") == "token":
                                token = event.get("content", "")
                                sys.stdout.write(token)
                                sys.stdout.flush()
                                full_response.append(token)
                            elif event.get("type") == "done":
                                importance_info = event
                            elif event.get("type") == "error":
                                console.print(f"\n[bold red]Agent error:[/bold red] {event.get('error')}")
                        except json.JSONDecodeError:
                            continue

            sys.stdout.write("\n")
            sys.stdout.flush()

            # Render memory logging metadata
            if importance_info:
                score = importance_info.get("importance_score", 0.0)
                tags = importance_info.get("tags", [])
                tags_str = ", ".join(tags) if tags else "none"
                console.print(
                    f"[dim]🧠 Episodic turn logged | Importance: [bold]{score}[/bold] | Tags: [{tags_str}][/dim]\n"
                )
            else:
                console.print()

        except Exception as exc:
            console.print(f"\n[bold red]Connection error during turn:[/bold red] {exc}\n")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
