# Consensus Backend

A production-grade crypto narrative tracking system that ingests news and social media data, analyzes sentiment, and computes narrative strength metrics for cryptocurrency markets.

## Features

- **Security-First Architecture**: JWT authentication with RS256, rate limiting, CORS, input validation
- **Narrative Tracking**: Configurable lexicon-based matching for crypto market narratives  
- **Sentiment Analysis**: Financial sentiment analysis using FinBERT with caching
- **Real-time APIs**: RESTful endpoints for narrative strength, leaderboards, and drivers
- **Test-Driven Development**: Comprehensive test suite with 90%+ coverage
- **Production Ready**: Docker containerization, structured logging, health checks

## Quick Start

### Prerequisites

- Python 3.11+
- Redis 7+
- OpenSSL (for JWT key generation)

### Setup (Recommended)

```bash
# Clone repository
git clone <repo-url> consensus-backend
cd consensus-backend

# Complete setup (creates venv, installs deps, generates keys, starts services)
make setup

# Start the API server
make run# Consensus-Crypto
