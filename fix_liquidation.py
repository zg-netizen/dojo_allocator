import re

with open('src/execution/order_manager.py', 'r') as f:
    content = f.read()

old = """                else:
                    # Partial close - reduce shares
                    value = shares_to_close * float(position.entry_price)
                    position.shares = Decimal(str(float(position.shares) - shares_to_close))
                    self.db.commit()
                    
                    results['total_value_liquidated'] += value
                    results['closed'].append({
                        'position_id': position.position_id,
                        'symbol': position.symbol,
                        'tier': tier,
                        'shares': shares_to_close,
                        'ratio': close_ratio,
                        'value': value
                    })"""

new = """                else:
                    # Partial close - execute actual SELL order
                    partial_exit_order = Order(
                        order_id=f"EXIT_PARTIAL_{position.position_id}_{uuid.uuid4().hex[:8]}",
                        position_id=position.position_id,
                        signal_id=position.signal_id,
                        symbol=position.symbol,
                        direction='SELL',
                        shares=Decimal(str(shares_to_close)),
                        order_type='MARKET',
                        status='PENDING',
                        reason=f'EMERGENCY_L{level}_PARTIAL',
                        created_at=datetime.utcnow()
                    )
                    
                    success = self.execute_order(partial_exit_order)
                    
                    if success:
                        self.db.refresh(partial_exit_order)
                        exit_price = float(partial_exit_order.filled_price)
                        
                        entry_cost = shares_to_close * float(position.entry_price)
                        exit_proceeds = shares_to_close * exit_price
                        partial_pnl = exit_proceeds - entry_cost
                        
                        position.shares = Decimal(str(float(position.shares) - shares_to_close))
                        
                        value = shares_to_close * exit_price
                        results['total_value_liquidated'] += value
                        results['closed'].append({
                            'position_id': position.position_id,
                            'symbol': position.symbol,
                            'tier': tier,
                            'shares': shares_to_close,
                            'ratio': close_ratio,
                            'entry_price': float(position.entry_price),
                            'exit_price': exit_price,
                            'partial_pnl': partial_pnl,
                            'value': value
                        })
                        
                        self.db.commit()
                    else:
                        results['failed'].append(position.position_id)"""

if old in content:
    content = content.replace(old, new)
    print("SUCCESS: Found and replaced")
else:
    print("ERROR: Could not find exact match")
    exit(1)

with open('src/execution/order_manager.py', 'w') as f:
    f.write(content)

print("File updated")
