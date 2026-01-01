#!/usr/bin/env python3
"""
Instant SWOT Agent - Unified Entry Point

Provides CLI access to all application modes:
- api: Start FastAPI backend server
- streamlit: Start Streamlit dashboard
- analyze: Run CLI analysis for a stock

Usage:
    python -m src.main api [--host HOST] [--port PORT]
    python -m src.main streamlit
    python -m src.main analyze TICKER [--strategy STRATEGY]
"""

import sys
import click


@click.group()
@click.version_option(version="2.0.0", prog_name="Instant SWOT Agent")
def cli():
    """Instant SWOT Agent - Multi-agent SWOT analysis with self-correction."""
    pass


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8002, type=int, help='Port to listen on')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def api(host: str, port: int, reload: bool):
    """Start the FastAPI backend server."""
    import uvicorn

    click.echo(f"Starting Instant SWOT Agent API on {host}:{port}")
    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload
    )


@cli.command()
@click.option('--port', default=8501, type=int, help='Port for Streamlit')
def streamlit(port: int):
    """Start the Streamlit dashboard."""
    import subprocess

    click.echo(f"Starting Instant SWOT Agent Streamlit UI on port {port}")
    subprocess.run([
        sys.executable, '-m', 'streamlit', 'run',
        'streamlit_app.py',
        '--server.port', str(port)
    ])


@cli.command()
@click.argument('ticker')
@click.option('--company', '-c', default=None, help='Company name (defaults to ticker)')
@click.option('--strategy', '-s', default='Competitive Position',
              help='Strategy focus for analysis')
@click.option('--output', '-o', type=click.Choice(['text', 'json']),
              default='text', help='Output format')
def analyze(ticker: str, company: str, strategy: str, output: str):
    """Run SWOT analysis for a stock ticker.

    Example:
        python -m src.main analyze AAPL
        python -m src.main analyze TSLA --company "Tesla Inc" --strategy "Cost Leadership"
    """
    import json
    from src.workflow.runner import run_self_correcting_workflow

    company_name = company or ticker

    click.echo(f"Analyzing {company_name} ({ticker})...")
    click.echo(f"Strategy focus: {strategy}")
    click.echo("-" * 50)

    try:
        result = run_self_correcting_workflow(
            company_name=company_name,
            ticker=ticker,
            strategy_focus=strategy
        )

        if output == 'json':
            output_data = {
                "company_name": company_name,
                "ticker": ticker,
                "strategy_focus": strategy,
                "score": result.get("score", 0),
                "revision_count": result.get("revision_count", 0),
                "provider_used": result.get("provider_used"),
                "data_source": result.get("data_source"),
                "draft_report": result.get("draft_report", ""),
                "critique": result.get("critique", "")
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            # Text output
            click.echo(f"\nScore: {result.get('score', 0)}/10")
            click.echo(f"Revisions: {result.get('revision_count', 0)}")
            click.echo(f"Provider: {result.get('provider_used', 'unknown')}")
            click.echo("\n" + "=" * 50)
            click.echo("SWOT ANALYSIS")
            click.echo("=" * 50)
            click.echo(result.get("draft_report", "No report generated"))

            if result.get("critique"):
                click.echo("\n" + "-" * 50)
                click.echo("CRITIQUE")
                click.echo("-" * 50)
                click.echo(result.get("critique"))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
def info():
    """Show system information and configuration status."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    click.echo("Instant SWOT Agent - System Info")
    click.echo("=" * 40)

    # LLM Providers
    click.echo("\nLLM Providers:")
    providers = [
        ("GROQ_API_KEY", "Groq"),
        ("GEMINI_API_KEY", "Gemini"),
        ("OPENROUTER_API_KEY", "OpenRouter")
    ]
    for env_var, name in providers:
        status = "configured" if os.getenv(env_var) else "not configured"
        click.echo(f"  {name}: {status}")

    # Data Sources
    click.echo("\nData Sources:")
    sources = [
        ("FRED_API_KEY", "FRED (Macro data)"),
        ("FINNHUB_API_KEY", "Finnhub (Sentiment)")
    ]
    for env_var, name in sources:
        status = "configured" if os.getenv(env_var) else "not configured"
        click.echo(f"  {name}: {status}")

    click.echo("\nEntry Points:")
    click.echo("  API:       python -m src.main api")
    click.echo("  Streamlit: python -m src.main streamlit")
    click.echo("  CLI:       python -m src.main analyze <TICKER>")


if __name__ == "__main__":
    cli()
