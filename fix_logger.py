with open('src/execution/order_manager.py', 'r') as f:
    content = f.read()

old = """    def __init__(self, db: Session, broker: BaseBroker):
        self.db = db
        self.broker = broker"""

new = """    def __init__(self, db: Session, broker: BaseBroker):
        self.db = db
        self.broker = broker
        self.logger = logger"""

content = content.replace(old, new)

with open('src/execution/order_manager.py', 'w') as f:
    f.write(content)

print("✅ Added logger to __init__")
