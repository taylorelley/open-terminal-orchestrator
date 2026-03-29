# Testing Guide

This guide covers how to run tests, write new tests, and validate changes in the Open Terminal Orchestrator project.

## Quick Reference

```bash
# Backend tests
cd backend && python -m pytest -v

# Frontend validation
npm run lint
npm run typecheck

# Run everything before committing
npm run lint && npm run typecheck && cd backend && python -m pytest -v
```

## Backend Tests

The backend test suite uses pytest and contains approximately 236 tests covering routes, services, and database operations.

### Running Backend Tests

```bash
cd backend

# Run all tests with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest -v tests/test_policies.py

# Run tests matching a pattern
python -m pytest -v -k "test_sandbox"

# Run with shorter traceback output
python -m pytest -v --tb=short

# Run with coverage reporting
python -m pytest -v --cov=app --cov-report=term-missing

# Stop on first failure
python -m pytest -v -x
```

### Installing Test Dependencies

Test dependencies are included in the `[test]` extra:

```bash
cd backend
pip install -e ".[test]"
```

This installs pytest, pytest-asyncio, httpx (for async test client), and other test utilities.

## Frontend Validation

The frontend does not currently use a unit test runner for all components. Code quality is enforced through linting and type checking.

### ESLint

ESLint enforces code quality rules including React Hooks rules and React Refresh compatibility:

```bash
npm run lint
```

This runs ESLint across all TypeScript and React files in the project. Fix any reported errors before committing.

### TypeScript Type Checking

TypeScript strict mode is enabled with additional strictness flags (`noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`):

```bash
npm run typecheck
```

This runs `tsc --noEmit` to check types without producing output files.

## Frontend Tests

Frontend tests use Vitest and React Testing Library. Test files are located alongside the components they test in `src/pages/__tests__/`.

### Running Frontend Tests

```bash
# Run all frontend tests
npx vitest run

# Run in watch mode during development
npx vitest

# Run a specific test file
npx vitest run src/pages/__tests__/Dashboard.test.tsx
```

### Writing Frontend Tests

Frontend tests follow React Testing Library patterns, focusing on user-visible behavior rather than implementation details.

```tsx
// src/pages/__tests__/Policies.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Policies from '../Policies';

// Mock the Supabase query hook
vi.mock('../../hooks/useSupabaseQuery', () => ({
  useSupabaseQuery: () => ({
    data: [
      { id: '1', name: 'Default Policy', tier: 'standard', is_active: true },
    ],
    loading: false,
    error: null,
  }),
}));

describe('Policies', () => {
  it('renders the policy list', async () => {
    render(
      <MemoryRouter>
        <Policies />
      </MemoryRouter>
    );

    expect(screen.getByText('Default Policy')).toBeInTheDocument();
  });

  it('opens the create modal when clicking the add button', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Policies />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: /add policy/i }));
    expect(screen.getByText('Create Policy')).toBeInTheDocument();
  });
});
```

### Key Testing Patterns

- **Wrap components in `MemoryRouter`** when they use React Router hooks or components.
- **Mock `useSupabaseQuery`** to provide controlled test data without a real database connection.
- **Mock `useAuth`** when testing components that depend on authentication state.
- **Use `userEvent`** for simulating user interactions (clicks, typing) rather than `fireEvent`.
- **Use `waitFor`** for assertions that depend on async state updates.

## Writing Backend Tests

### Test Structure

Backend tests are organized by module in the `backend/tests/` directory:

```
backend/tests/
├── conftest.py              # Shared fixtures (async client, DB session, admin headers)
├── test_policies.py         # Policy endpoint tests
├── test_sandboxes.py        # Sandbox endpoint tests
├── test_users.py            # User endpoint tests
├── test_system.py           # System configuration tests
├── test_auth.py             # Authentication tests
├── test_policy_engine.py    # Policy engine service tests
├── test_pool_manager.py     # Pool manager service tests
├── test_audit_service.py    # Audit logging tests
└── ...
```

### Fixtures

Common test fixtures are defined in `conftest.py`:

```python
# backend/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.main import app
from app.config import Settings


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def admin_headers():
    settings = Settings()
    return {"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}


@pytest_asyncio.fixture
async def db_session():
    # Provides a transactional database session that rolls back after each test
    ...
```

### Async Tests

All tests that involve database operations or HTTP requests must be marked as async:

```python
import pytest


@pytest.mark.asyncio
async def test_create_sandbox(async_client, admin_headers):
    response = await async_client.post(
        "/api/v1/sandboxes",
        json={"user_id": "user-123", "policy_id": "policy-456"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "WARMING"
    assert data["user_id"] == "user-123"
```

### Mocking Services

Use `unittest.mock` or pytest-mock to mock external service calls:

```python
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_sandbox_creation_calls_gateway(async_client, admin_headers):
    with patch("app.services.openshell_client.OpenShellClient.create_sandbox") as mock_create:
        mock_create.return_value = {"id": "sandbox-789", "status": "warming"}

        response = await async_client.post(
            "/api/v1/sandboxes",
            json={"user_id": "user-123", "policy_id": "policy-456"},
            headers=admin_headers,
        )

        assert response.status_code == 201
        mock_create.assert_called_once()
```

### Testing Services Directly

Services can be tested in isolation without going through HTTP endpoints:

```python
@pytest.mark.asyncio
async def test_policy_engine_evaluates_yaml(db_session):
    from app.services.policy_engine import PolicyEngine

    engine = PolicyEngine(db_session)
    result = await engine.evaluate(
        user_id="user-123",
        command="rm -rf /",
    )

    assert result.allowed is False
    assert "destructive command" in result.reason.lower()
```

## Running All Checks Before Committing

Always run the full validation suite before committing changes:

```bash
# From the repository root
npm run lint && npm run typecheck && cd backend && python -m pytest -v
```

If any check fails, fix the issues before committing. The CI pipeline runs these same checks and will reject pull requests with failures.

## CI Pipeline Overview

The continuous integration pipeline runs the following steps on every pull request:

1. **Checkout** -- Clone the repository at the PR branch.
2. **Install dependencies** -- `npm install` and `pip install -e ".[test]"`.
3. **Frontend lint** -- `npm run lint` must pass with zero errors.
4. **Frontend typecheck** -- `npm run typecheck` must pass with zero errors.
5. **Backend tests** -- `cd backend && python -m pytest -v` must pass all tests.
6. **Build** -- `npm run build` must succeed to verify the production build.

All steps must pass before a pull request can be merged. If a step fails, check the CI logs for the specific error and fix it locally before pushing again.
