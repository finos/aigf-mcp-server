#!/bin/bash
# Fast test runner for development
set -euo pipefail

# Load test environment
if [[ -f ".env.test" ]]; then
    source .env.test
fi

# Run only fast unit tests
echo "🚀 Running fast tests (offline mode)..."
python -m pytest \
    -c pytest.fast.ini \
    --disable-warnings \
    -q \
    -x \
    --tb=short \
    -m "not slow and not integration and not network" \
    tests/unit/

echo "✅ Fast tests completed"
