with open('src/execution/order_manager.py', 'r') as f:
    content = f.read()

# Replace direction='SELL' with side='SELL'
content = content.replace("direction='SELL'", "side='SELL'")

with open('src/execution/order_manager.py', 'w') as f:
    f.write(content)

print("✅ Changed direction to side")
