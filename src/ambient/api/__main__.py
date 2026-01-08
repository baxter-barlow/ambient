"""Run the ambient API server."""
import argparse
import os

import uvicorn

from ambient.config import configure_logging, get_config


def main():
    config = get_config()

    parser = argparse.ArgumentParser(description="Ambient Dashboard API Server")
    parser.add_argument("--host", default=config.api.host, help="Host to bind to")
    parser.add_argument("--port", type=int, default=config.api.port, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default=config.api.log_level, help="Log level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--config", help="Path to config file (JSON)")
    args = parser.parse_args()

    # Load config file if specified
    if args.config:
        from ambient.config import AppConfig

        file_config = AppConfig.from_file(args.config)
        # Merge with environment overrides
        if os.environ.get("AMBIENT_API_HOST"):
            file_config.api.host = os.environ["AMBIENT_API_HOST"]
        if os.environ.get("AMBIENT_API_PORT"):
            file_config.api.port = int(os.environ["AMBIENT_API_PORT"])

    # Configure logging
    configure_logging(args.log_level)

    # Ensure data directories exist
    config.ensure_dirs()

    uvicorn.run(
        "ambient.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()
