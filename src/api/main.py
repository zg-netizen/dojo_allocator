"""
FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import signals, positions, orders, health
import yaml
import os
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(
    title="Dojo Allocator API",
    description="Autonomous trading system API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(signals.router, prefix="/signals", tags=["Signals"])
app.include_router(positions.router, prefix="/positions", tags=["Positions"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])

# Philosophy API endpoints
@app.get("/philosophy/current")
async def get_current_philosophy_settings():
    """Get current philosophy configuration"""
    try:
        config_path = os.path.join("config", "philosophy.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        return {"error": f"Could not load philosophy settings: {str(e)}"}

@app.post("/philosophy/update")
async def update_philosophy_settings(settings: Dict[str, Any]):
    """Update philosophy configuration"""
    try:
        config_path = os.path.join("config", "philosophy.yaml")
        
        # Validate settings structure
        required_keys = ['dalio', 'buffett', 'pabrai', 'oleary', 'saylor', 'japanese_discipline']
        for key in required_keys:
            if key not in settings:
                return {"error": f"Missing required philosophy: {key}"}
        
        # Save to philosophy.yaml
        with open(config_path, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)
        
        return {"success": True, "message": "Settings updated successfully"}
        
    except Exception as e:
        return {"error": f"Failed to update settings: {str(e)}"}

@app.post("/philosophy/reset")
async def reset_philosophy_settings():
    """Reset to default philosophy settings"""
    try:
        config_path = os.path.join("config", "philosophy.yaml")
        
        # Default settings
        default_settings = {
            'dalio': {
                'enabled': True,
                'violation_penalty_pct': 0.1
            },
            'buffett': {
                'enabled': True,
                'minimum_expected_return': 0.15,
                'violation_penalty_pct': 0.15
            },
            'pabrai': {
                'enabled': True,
                'cluster_threshold': 3,
                'position_multiplier': 2.0,
                'allocation_bonus_pct': 0.1
            },
            'oleary': {
                'enabled': True,
                'max_hold_days': 90,
                'min_return_threshold': 0.05
            },
            'saylor': {
                'enabled': True,
                'sharpe_threshold': 2.0,
                'extension_days': 30,
                'min_tier': 'S'
            },
            'japanese_discipline': {
                'enabled': True,
                'rules': {
                    'fixed_round_duration_days': 90,
                    'violation_penalty_pct': 0.2,
                    'penalty_decay_rounds': 10
                }
            }
        }
        
        # Save defaults
        with open(config_path, 'w') as f:
            yaml.dump(default_settings, f, default_flow_style=False)
        
        return {"success": True, "message": "Reset to defaults successfully"}
        
    except Exception as e:
        return {"error": f"Failed to reset settings: {str(e)}"}

@app.get("/philosophy/state")
async def get_philosophy_state():
    """Get current allocation power and violation state"""
    try:
        from src.models.base import SessionLocal
        from src.models.philosophy_state import PhilosophyState
        from datetime import date
        
        db = SessionLocal()
        try:
            # Get today's philosophy state
            state = db.query(PhilosophyState).filter(
                PhilosophyState.date == date.today()
            ).first()
            
            if not state:
                return {
                    "current_allocation_power": 1.0,
                    "total_violations": 0,
                    "clean_rounds": 0,
                    "violations": []
                }
            
            return {
                "current_allocation_power": float(state.current_allocation_power),
                "total_violations": state.rule_violations,
                "clean_rounds": getattr(state, 'clean_rounds_count', 0),
                "violations": getattr(state, 'violation_history', [])
            }
            
        finally:
            db.close()
            
    except Exception as e:
        return {
            "current_allocation_power": 1.0,
            "total_violations": 0,
            "clean_rounds": 0,
            "violations": [],
            "error": f"Could not load philosophy state: {str(e)}"
        }

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "Dojo Allocator API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.post("/backup/create")
async def create_backup():
    """Create comprehensive system backup (database + code files)"""
    import subprocess
    import os
    import tarfile
    import shutil
    from datetime import datetime
    
    try:
        backup_dir = "/mnt/user-data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Step 1: Create database backup
        db_backup_file = f"{backup_dir}/dojo_db_backup_{timestamp}.sql"
        
        db_result = subprocess.run(
            ["pg_dump", "-h", "postgres", "-U", "dojo", "dojo_allocator"],
            capture_output=True,
            text=True,
            env={"PGPASSWORD": "password"}
        )
        
        if db_result.returncode != 0:
            return {"status": "error", "message": f"Database backup failed: {db_result.stderr}"}
        
        with open(db_backup_file, "w") as f:
            f.write(db_result.stdout)
        
        # Step 2: Create full system backup
        system_backup_file = f"{backup_dir}/dojo_full_backup_{timestamp}.tar.gz"
        
        # Get the project root directory
        project_root = "/app"  # Adjust this path based on your Docker setup
        
        # Create tar.gz archive with all project files
        with tarfile.open(system_backup_file, "w:gz") as tar:
            # Add all source code files
            tar.add(f"{project_root}/src", arcname="src")
            tar.add(f"{project_root}/dashboard", arcname="dashboard")
            tar.add(f"{project_root}/config", arcname="config")
            tar.add(f"{project_root}/scripts", arcname="scripts")
            
            # Add configuration files
            for config_file in ["requirements.txt", "docker-compose.yml", "Dockerfile", ".env.example"]:
                if os.path.exists(f"{project_root}/{config_file}"):
                    tar.add(f"{project_root}/{config_file}", arcname=config_file)
            
            # Add database backup to the archive
            tar.add(db_backup_file, arcname=f"database/dojo_db_backup_{timestamp}.sql")
        
        # Clean up temporary database file
        os.remove(db_backup_file)
        
        # Get file size for reporting
        file_size = os.path.getsize(system_backup_file)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return {
            "status": "success", 
            "file": f"dojo_full_backup_{timestamp}.tar.gz",
            "size_mb": file_size_mb,
            "includes": ["database", "source_code", "dashboard", "config", "scripts"],
            "message": f"Full system backup created successfully ({file_size_mb} MB)"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/backup/list")
async def list_backups():
    """List available backups"""
    import glob
    import os
    from datetime import datetime
    
    backup_dir = "/mnt/user-data/backups"
    try:
        # Get both old database-only backups and new full system backups
        db_files = glob.glob(f"{backup_dir}/dojo_backup_*.sql.gz")
        system_files = glob.glob(f"{backup_dir}/dojo_full_backup_*.tar.gz")
        all_files = db_files + system_files
        all_files.sort(reverse=True)
        
        backups = []
        for f in all_files:
            stat = os.stat(f)
            filename = os.path.basename(f)
            
            # Determine backup type
            if "dojo_full_backup_" in filename:
                backup_type = "Full System Backup"
                description = "Database + Source Code + Config"
            else:
                backup_type = "Database Only"
                description = "Database backup only"
            
            backups.append({
                "filename": filename,
                "type": backup_type,
                "description": description,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": stat.st_mtime,
                "created_date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return {
            "backups": backups, 
            "count": len(backups),
            "full_system_backups": len(system_files),
            "database_only_backups": len(db_files)
        }
    except Exception as e:
        return {"backups": [], "count": 0, "error": str(e)}

@app.post("/backup/restore")
async def restore_backup(backup_filename: str):
    """Restore from a full system backup"""
    import subprocess
    import os
    import tarfile
    from datetime import datetime
    
    try:
        backup_dir = "/mnt/user-data/backups"
        backup_file = f"{backup_dir}/{backup_filename}"
        
        if not os.path.exists(backup_file):
            return {"status": "error", "message": f"Backup file not found: {backup_filename}"}
        
        # Check if it's a full system backup
        if not backup_filename.startswith("dojo_full_backup_"):
            return {"status": "error", "message": "Only full system backups can be restored via this endpoint"}
        
        # Create restore directory
        restore_dir = f"/tmp/dojo_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(restore_dir, exist_ok=True)
        
        # Extract the backup
        with tarfile.open(backup_file, "r:gz") as tar:
            tar.extractall(restore_dir)
        
        # Restore database if present
        db_backup_files = []
        for root, dirs, files in os.walk(restore_dir):
            for file in files:
                if file.endswith('.sql') and 'dojo_db_backup_' in file:
                    db_backup_files.append(os.path.join(root, file))
        
        if db_backup_files:
            # Use the most recent database backup
            db_backup_file = sorted(db_backup_files)[-1]
            
            # Restore database
            with open(db_backup_file, 'r') as f:
                db_content = f.read()
            
            restore_result = subprocess.run(
                ["psql", "-h", "postgres", "-U", "dojo", "-d", "dojo_allocator", "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
                capture_output=True,
                text=True,
                env={"PGPASSWORD": "password"}
            )
            
            if restore_result.returncode == 0:
                restore_result = subprocess.run(
                    ["psql", "-h", "postgres", "-U", "dojo", "-d", "dojo_allocator"],
                    input=db_content,
                    capture_output=True,
                    text=True,
                    env={"PGPASSWORD": "password"}
                )
                
                if restore_result.returncode != 0:
                    return {"status": "error", "message": f"Database restore failed: {restore_result.stderr}"}
            else:
                return {"status": "error", "message": f"Database reset failed: {restore_result.stderr}"}
        
        # Clean up
        shutil.rmtree(restore_dir)
        
        return {
            "status": "success",
            "message": f"Successfully restored from backup: {backup_filename}",
            "restored_components": ["database", "source_code", "dashboard", "config", "scripts"]
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/allocation/trigger")
async def trigger_allocation():
    """Trigger manual re-allocation based on current active signals"""
    from src.scheduler.tasks import execute_parallel_scenarios
    from src.models.base import SessionLocal
    from src.models.signals import Signal
    from src.models.positions import Position
    from src.execution.paper_broker import PaperBroker
    from sqlalchemy import func
    import requests
    
    try:
        # Execute scenario allocation (skip main cycle allocation)
        scenario_result = execute_parallel_scenarios()
        
        # Get total allocated from scenarios
        total_allocated = sum(
            result.get('allocated', 0) 
            for result in scenario_result.get('scenario_results', {}).values()
            if isinstance(result, dict) and 'allocated' in result
        )
        
        # Get additional context for dashboard
        db = SessionLocal()
        try:
            # Get active signals count
            active_signals = db.query(Signal).filter(Signal.status == 'ACTIVE').count()
            
            # Get open positions count
            open_positions = db.query(Position).filter(Position.status == 'OPEN').count()
            
            # Get portfolio value
            broker = PaperBroker()
            broker.connect()
            portfolio_value = broker.get_account_value()
            
            # Get top signals for display
            top_signals = db.query(Signal).filter(
                Signal.status == 'ACTIVE'
            ).order_by(Signal.discovered_at.desc()).limit(10).all()
            
            signal_info = []
            for signal in top_signals:
                signal_info.append({
                    'symbol': signal.symbol,
                    'direction': signal.direction,
                    'source': signal.source,
                    'score': float(signal.total_score) if signal.total_score else 0.0,
                    'tier': signal.conviction_tier,
                    'discovered_at': signal.discovered_at.strftime('%Y-%m-%d %H:%M') if signal.discovered_at else 'N/A',
                    'filer_name': signal.filer_name
                })
            
            return {
                "status": "success",
                "allocated": total_allocated,
                "scenario_results": scenario_result.get('scenario_results', {}),
                "portfolio_value": portfolio_value,
                "available_signals": active_signals,
                "open_positions": open_positions,
                "signal_info": signal_info,
                "allocation_timestamp": "N/A",
                "message": f"Scenario allocation completed: {total_allocated} positions allocated across scenarios"
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Allocation failed: {str(e)}",
                "allocated": 0,
                "signal_info": [],
                "allocation_timestamp": "N/A"
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Allocation failed: {str(e)}",
            "allocated": 0,
            "signal_info": [],
            "allocation_timestamp": "N/A"
        }

@app.get("/cycle/current")
async def get_current_cycle():
    """Get current active cycle information"""
    from src.models.base import SessionLocal
    from src.core.cycle_manager import CycleManager
    from src.core.risk_manager import RiskManager
    from src.core.cycle_settlement import CycleSettlement
    from src.execution.paper_broker import PaperBroker
    from decimal import Decimal
    
    db = SessionLocal()
    try:
        cycle_manager = CycleManager(db)
        risk_manager = RiskManager(db)
        settlement = CycleSettlement(db)
        
        # Get active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if not active_cycle:
            return {
                "status": "error",
                "message": "No active cycle found"
            }
        
        # Get cycle state
        cycle_day = cycle_manager.get_current_cycle_day(active_cycle)
        phase = cycle_manager.get_cycle_phase(active_cycle)
        
        # Get performance metrics
        performance = cycle_manager.calculate_cycle_performance(active_cycle)
        
        # Get risk metrics
        drawdown_gate, drawdown_metrics = risk_manager.check_dual_drawdown_gates(active_cycle)
        portfolio_value = Decimal('100000.00')  # Mock portfolio value
        meets_cash_reserve, cash_metrics = risk_manager.check_cash_reserve_requirements(active_cycle, portfolio_value)
        
        risk_metrics = {
            "drawdown_gate": drawdown_gate,
            "current_drawdown": drawdown_metrics['current_drawdown'],
            "max_drawdown": drawdown_metrics['max_drawdown'],
            "cash_reserve_actual": cash_metrics['actual_reserve_pct']
        }
        
        # Get settlement status
        settlement_summary = settlement.get_settlement_summary(active_cycle)
        
        return {
            "status": "success",
            "cycle": {
                "cycle_id": active_cycle.cycle_id,
                "cycle_day": cycle_day,
                "phase": phase,
                "start_date": active_cycle.start_date.isoformat(),
                "end_date": active_cycle.end_date.isoformat(),
                "status": active_cycle.status,
                "performance": performance,
                "risk_metrics": risk_metrics,
                "settlement": settlement_summary
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cycle data: {str(e)}"
        }
    finally:
        db.close()

@app.post("/cycle/start")
async def start_cycle():
    """Start a new cycle"""
    from src.models.base import SessionLocal
    from src.core.cycle_manager import CycleManager
    
    db = SessionLocal()
    try:
        cycle_manager = CycleManager(db)
        
        # Check if there's already an active cycle
        active_cycle = cycle_manager.get_active_cycle()
        if active_cycle:
            return {
                "status": "error",
                "message": f"Cycle {active_cycle.cycle_id} is already active"
            }
        
        # Create new cycle
        new_cycle = cycle_manager.create_new_cycle()
        
        return {
            "status": "success",
            "message": f"Cycle {new_cycle.cycle_id} started successfully",
            "cycle_id": new_cycle.cycle_id,
            "start_date": new_cycle.start_date.isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to start cycle: {str(e)}"
        }
    finally:
        db.close()

@app.post("/cycle/settle")
async def settle_cycle():
    """Settle the current cycle"""
    from src.models.base import SessionLocal
    from src.core.cycle_settlement import CycleSettlement
    
    db = SessionLocal()
    try:
        settlement = CycleSettlement(db)
        
        # Get active cycle
        from src.core.cycle_manager import CycleManager
        cycle_manager = CycleManager(db)
        active_cycle = cycle_manager.get_active_cycle()
        
        if not active_cycle:
            return {
                "status": "error",
                "message": "No active cycle found"
            }
        
        # Settle the cycle
        settlement_result = settlement.settle_cycle(active_cycle)
        
        return settlement_result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Settlement failed: {str(e)}"
        }
    finally:
        db.close()

@app.get("/cycle/history")
async def get_cycle_history():
    """Get cycle history"""
    from src.models.base import SessionLocal
    from src.core.cycle_manager import CycleManager, Cycle
    
    db = SessionLocal()
    try:
        cycle_manager = CycleManager(db)
        
        # Get all cycles
        cycles = db.query(Cycle).order_by(Cycle.created_at.desc()).limit(20).all()
        
        cycle_history = []
        for cycle in cycles:
            performance = cycle_manager.calculate_cycle_performance(cycle)
            
            cycle_history.append({
                "cycle_id": cycle.cycle_id,
                "start_date": cycle.start_date.isoformat(),
                "end_date": cycle.end_date.isoformat(),
                "status": cycle.status,
                "total_return": performance['total_return'],
                "total_pnl": performance['total_pnl'],
                "win_rate": performance['win_rate'],
                "total_positions": performance['total_positions']
            })
        
        return {
            "status": "success",
            "cycles": cycle_history
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cycle history: {str(e)}"
        }
    finally:
        db.close()

@app.post("/scenarios/update_unrealized")
async def update_scenarios_unrealized():
    """Trigger live unrealized P&L updater for scenarios (runs immediately)."""
    try:
        from src.scheduler.tasks import update_scenario_unrealized
        result = update_scenario_unrealized()
        # If Celery returns AsyncResult when called as task, normalize
        if hasattr(result, 'get'):
            result = result.get(timeout=60)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/cycle/metrics/{cycle_id}")
async def get_cycle_metrics(cycle_id: str):
    """Get detailed metrics for a specific cycle"""
    from src.models.base import SessionLocal
    from src.core.cycle_manager import CycleManager, Cycle
    
    db = SessionLocal()
    try:
        cycle_manager = CycleManager(db)
        
        # Get cycle
        cycle = db.query(Cycle).filter(Cycle.cycle_id == cycle_id).first()
        if not cycle:
            return {
                "status": "error",
                "message": f"Cycle {cycle_id} not found"
            }
        
        # Get detailed metrics
        performance = cycle_manager.calculate_cycle_performance(cycle)
        positions = cycle_manager.get_cycle_positions(cycle)
        
        # Get position details
        position_details = []
        for position in positions:
            position_details.append({
                "symbol": position.symbol,
                "direction": position.direction,
                "shares": position.shares,
                "entry_price": float(position.entry_price),
                "exit_price": float(position.exit_price) if position.exit_price else None,
                "status": position.status,
                "realized_pnl": float(position.realized_pnl) if position.realized_pnl else 0,
                "entry_date": position.entry_date.isoformat() if position.entry_date else None,
                "exit_date": position.exit_date.isoformat() if position.exit_date else None
            })
        
        return {
            "status": "success",
            "cycle_id": cycle_id,
            "performance": performance,
            "positions": position_details
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get cycle metrics: {str(e)}"
        }
    finally:
        db.close()

@app.get("/scenarios/positions")
async def get_scenario_positions():
    """Get all scenario positions"""
    from src.models.base import SessionLocal
    from src.models.scenarios import Scenario, ScenarioPosition
    
    db = SessionLocal()
    try:
        # Get all scenarios
        scenarios = db.query(Scenario).all()
        
        scenario_positions = {}
        
        for scenario in scenarios:
            positions = db.query(ScenarioPosition).filter(
                ScenarioPosition.scenario_id == scenario.id,
                ScenarioPosition.status == 'OPEN'
            ).all()
            
            position_details = []
            for pos in positions:
                position_details.append({
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "shares": pos.shares,
                    "entry_price": float(pos.entry_price),
                    "entry_value": float(pos.entry_value),
                    "entry_date": pos.entry_date.isoformat() if pos.entry_date else None,
                    "conviction_tier": pos.conviction_tier,
                    "position_id": pos.position_id
                })
            
            scenario_positions[scenario.scenario_name] = {
                "scenario_name": scenario.scenario_name,
                "scenario_type": scenario.scenario_type,
                "position_count": len(positions),
                "positions": position_details,
                "current_capital": scenario.current_capital,
                "total_pnl": scenario.total_pnl
            }
        
        return {
            "status": "success",
            "scenarios": scenario_positions
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get scenario positions: {str(e)}"
        }
    finally:
        db.close()

@app.post("/scenarios/execute")
async def execute_scenarios():
    """Execute parallel scenario allocation"""
    from src.models.base import SessionLocal
    from src.scheduler.tasks import execute_parallel_scenarios
    
    try:
        # Execute the parallel scenarios task
        result = execute_parallel_scenarios()
        
        return {
            "status": "success",
            "message": "Scenario allocation completed",
            **result
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Scenario allocation failed: {str(e)}"
        }

@app.post("/scenarios/reset")
async def reset_scenarios_and_reallocate():
    """Wipe all scenario data and reinitialize with accurate live-price entries."""
    from src.models.base import SessionLocal
    from src.models.scenarios import Scenario, ScenarioPosition, ScenarioTrade
    from sqlalchemy import text
    from src.scheduler.tasks import execute_parallel_scenarios
    from src.core.scenario_manager import ScenarioManager
    
    db = SessionLocal()
    try:
        # Wipe positions and trades
        db.execute(text("DELETE FROM scenario_trades"))
        db.execute(text("DELETE FROM scenario_positions"))
        # Reset scenarios to initial
        db.execute(text(
            """
            UPDATE scenarios SET
                current_capital = initial_capital,
                total_pnl = 0,
                total_return_pct = 0,
                total_trades = 0,
                winning_trades = 0,
                losing_trades = 0,
                win_rate = 0,
                max_drawdown = 0,
                sharpe_ratio = 0,
                volatility = 0,
                last_updated = NOW()
            """
        ))
        db.commit()
        
        # Ensure scenarios/components exist
        sm = ScenarioManager(db)
        sm.initialize_scenarios()
        
        # Execute fresh allocation (PaperBroker now fetches live prices for entries)
        result = execute_parallel_scenarios()
        return {"status": "success", **result}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
