# Multi-stage Dockerfile for ambient radar interface
# Supports both development (with hot reload) and production builds

# =============================================================================
# Base stage: Common system dependencies
# =============================================================================
FROM python:3.11-slim AS base

# System dependencies for serial communication and signal processing
RUN apt-get update && apt-get install -y --no-install-recommends \
	libusb-1.0-0 \
	udev \
	usbutils \
	&& rm -rf /var/lib/apt/lists/*

# Create non-root user with dialout group for serial port access
RUN groupadd -r ambient && useradd -r -g ambient -G dialout ambient

WORKDIR /app

# =============================================================================
# Dependencies stage: Install Python packages
# =============================================================================
FROM base AS deps

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	&& rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (better caching)
COPY pyproject.toml ./

# Install core dependencies
RUN pip install --no-cache-dir -e ".[dashboard]"

# =============================================================================
# Development stage: Full dev environment with hot reload
# =============================================================================
FROM deps AS dev

# Install dev dependencies
RUN pip install --no-cache-dir -e ".[all]"

# Install Node.js for frontend development
RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	&& curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
	&& apt-get install -y nodejs \
	&& rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Install frontend dependencies
WORKDIR /app/dashboard
RUN npm install

WORKDIR /app

# Set ownership
RUN chown -R ambient:ambient /app

USER ambient

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV AMBIENT_DATA_DIR=/app/data
ENV AMBIENT_CONFIG_DIR=/app/configs

# Expose ports
EXPOSE 8000 5173

# Default command: run both backend and frontend
CMD ["sh", "-c", "uvicorn ambient.api.main:app --host 0.0.0.0 --port 8000 --reload & cd dashboard && npm run dev -- --host 0.0.0.0"]

# =============================================================================
# Frontend builder stage: Build production frontend
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/dashboard

COPY dashboard/package*.json ./
RUN npm ci

COPY dashboard/ .
RUN npm run build

# =============================================================================
# Production stage: Minimal runtime image
# =============================================================================
FROM base AS prod

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy source code
COPY src/ /app/src/
COPY configs/ /app/configs/
COPY pyproject.toml /app/

# Copy built frontend
COPY --from=frontend-builder /app/dashboard/dist /app/dashboard/dist

# Create data directory
RUN mkdir -p /app/data && chown -R ambient:ambient /app

USER ambient

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV AMBIENT_DATA_DIR=/app/data
ENV AMBIENT_CONFIG_DIR=/app/configs

EXPOSE 8000

# Run production server
CMD ["uvicorn", "ambient.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
