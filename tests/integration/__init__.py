"""
Integration tests for MassaCorp API.

These tests run against a real database and test the full stack.

Usage:
    pytest tests/integration/ -m integration

Requirements:
    - PostgreSQL database (TEST_DATABASE_URL env var)
    - Redis (optional, for rate limiting tests)
"""
