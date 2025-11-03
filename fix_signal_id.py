with open('src/execution/order_manager.py', 'r') as f:
    content = f.read()

old = """                    partial_exit_order = Order(
                        order_id=f"EXIT_PARTIAL_{position.position_id}_{uuid.uuid4().hex[:8]}",
                        position_id=position.position_id,
                        signal_id=position.signal_id,
                        symbol=position.symbol,"""

new = """                    partial_exit_order = Order(
                        order_id=f"EXIT_PARTIAL_{position.position_id}_{uuid.uuid4().hex[:8]}",
                        position_id=position.position_id,
                        symbol=position.symbol,"""

content = content.replace(old, new)

with open('src/execution/order_manager.py', 'w') as f:
    f.write(content)

print("✅ Removed signal_id from Order")
