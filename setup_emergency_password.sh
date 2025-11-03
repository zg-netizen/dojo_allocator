#!/bin/bash

cd ~/dojo_allocator

EMERGENCY_PASSWORD=$(openssl rand -base64 16)

echo ""
echo "==========================="
echo "EMERGENCY ADMIN PASSWORD:"
echo "${EMERGENCY_PASSWORD}"
echo "==========================="
echo ""
echo "SAVE THIS PASSWORD SECURELY!"
echo ""

if ! grep -q "EMERGENCY_ADMIN_PASSWORD" .env; then
    echo "" >> .env
    echo "# Emergency Liquidation Password" >> .env
    echo "EMERGENCY_ADMIN_PASSWORD=${EMERGENCY_PASSWORD}" >> .env
    echo "✅ Added to .env"
else
    echo "⚠️ Password already exists in .env"
fi

if ! grep -q "EMERGENCY_ADMIN_PASSWORD" docker-compose.yml; then
    python3 << 'PYSCRIPT'
with open("docker-compose.yml", "r") as f:
    lines = f.readlines()

inserted = False
for i, line in enumerate(lines):
    if "- ALPACA_API_SECRET=" in line and not inserted:
        indent = len(line) - len(line.lstrip())
        lines.insert(i + 1, " " * indent + "- EMERGENCY_ADMIN_PASSWORD=${EMERGENCY_ADMIN_PASSWORD}\n")
        inserted = True
        break

if inserted:
    with open("docker-compose.yml", "w") as f:
        f.writelines(lines)
    print("✅ Added to docker-compose.yml")
else:
    print("⚠️ Could not find insertion point")
PYSCRIPT
else
    echo "✅ Already in docker-compose.yml"
fi

echo ""
echo "=== VERIFICATION ==="
grep "EMERGENCY_ADMIN_PASSWORD" .env
grep "EMERGENCY_ADMIN_PASSWORD" docker-compose.yml | head -1

echo ""
echo "📝 WRITE DOWN THIS PASSWORD:"
echo "${EMERGENCY_PASSWORD}"
