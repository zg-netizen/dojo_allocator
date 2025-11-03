# 🥋 Dojo Allocator

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red.svg)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-TimescaleDB-blue.svg)](https://www.timescale.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

An autonomous trading system that processes insider trading data, congressional trades, and institutional filings to generate and execute trading signals across multiple parallel portfolio scenarios.

## 🌟 Features

### Multi-Scenario Trading
- Runs 5 parallel trading strategies simultaneously:
  - **Conservative**: Lower risk, capital preservation focus
  - **Balanced**: Moderate risk, diversified approach
  - **Aggressive**: High conviction, larger positions
  - **High-Risk**: Maximum risk tolerance, concentrated positions
  - **Custom**: User-configurable parameters

### Signal Processing
- **SEC Form 4 Filings**: Real-time insider trading data from corporate executives
- **Congressional Trades**: STOCK Act disclosures from politicians
- **13F Filings**: Institutional holdings and trades
- **OpenInsider Data**: Aggregated insider trading information
- **Quality Filtering**: Advanced algorithms filter low-quality signals
- **Conviction Scoring**: S, A, B, C tier classification

### Philosophy Engine
Implements legendary investor strategies:
- **Warren Buffett**: Value investing with long-term focus
- **George Soros**: Reflexivity and trend-following strategies
- **Ray Dalio**: All-weather portfolio principles
- **Paul Tudor Jones**: Macro trend and momentum strategies
- **Japanese Discipline**: Risk management and position sizing

### Real-Time Dashboard
- Live performance metrics for all scenarios
- Position tracking with current market prices
- Signal analysis and filtering
- Cycle status monitoring
- Philosophy settings configuration
- Performance analytics and comparison charts

### Risk Management
- **Drawdown Gates**: Automatic position reduction at risk thresholds
- **Position Limits**: Maximum position size per stock and scenario
- **Cash Reserves**: Minimum cash levels maintained
- **Correlation Analysis**: Avoids over-concentration
- **Volatility Adjustment**: Dynamic position sizing

### 90-Day Trading Cycles
- Structured cycle-based allocation
- Automatic settlement and performance tracking
- Phase-based position management
- Cycle history and analytics

## 🏗️ Architecture

```
┌─────────────────┐
│  Data Sources   │  SEC, Congressional, 13F, OpenInsider
└────────┬────────┘
         │
┌────────▼────────┐
│ Signal Scorer   │  Quality filtering & conviction scoring
└────────┬────────┘
         │
┌────────▼────────┐
│ Philosophy      │  Buffett, Soros, Dalio, etc.
│ Engine          │
└────────┬────────┘
         │
┌────────▼────────┐
│ Scenario        │  5 Parallel Strategies
│ Allocator      │
└────────┬────────┘
         │
┌────────▼────────┐
│ Paper Broker    │  Execution & Position Management
└────────┬────────┘
         │
┌────────▼────────┐
│ Dashboard       │  Real-time Monitoring
└─────────────────┘
```

### Technology Stack

**Backend:**
- FastAPI - High-performance REST API
- PostgreSQL with TimescaleDB - Time-series database
- Redis - Caching and session management
- Celery - Asynchronous task processing

**Frontend:**
- Streamlit - Interactive dashboard
- Plotly - Interactive charts and visualizations
- HTML/CSS - Custom styling and UI components

**Data Processing:**
- Pandas - Data manipulation and analysis
- NumPy - Numerical computations
- yfinance - Real-time market data
- BeautifulSoup4 - Web scraping

**Infrastructure:**
- Docker - Containerization
- Docker Compose - Multi-container orchestration
- Nginx - Reverse proxy and SSL termination

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- API Keys (Alpaca, FRED - optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zg-netizen/dojo_allocator.git
   cd dojo_allocator
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Access the dashboard**
   - Dashboard: http://localhost:8501
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Production Deployment

See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for complete AWS deployment instructions.

```bash
# Quick production setup
./deploy.sh
```

## 📊 Dashboard Features

### Overview Page
- Multi-scenario performance summary
- Real-time KPI metrics
- Scenario comparison cards
- Portfolio overview

### Performance Page
- Detailed performance analytics
- Return charts and comparisons
- Benchmark comparisons (SPY, QQQ, GLD)
- Win/loss statistics

### Signals Page
- Live feed of trading signals
- Signal filtering and search
- Conviction tier breakdown
- Source analysis

### Positions Page
- Open and closed positions
- Real-time P&L calculation
- Entry/exit price tracking
- Scenario-based organization

### Cycle Status
- Current cycle information
- Cycle history
- Performance metrics
- Risk gate status

### Philosophy Settings
- Configure investment philosophies
- Adjust risk parameters
- Customize position sizing
- Real-time application

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://dojo:password@postgres:5432/dojo_allocator

# Trading API
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here

# Economic Data
FRED_API_KEY=your_key_here

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

### Philosophy Configuration

Edit `config/philosophy.yaml` to customize:
- Position sizing rules
- Risk management parameters
- Philosophy multipliers
- Violation penalties

### Risk Limits

Edit `config/risk_limits.yaml` to adjust:
- Maximum position sizes
- Portfolio allocation limits
- Drawdown thresholds
- Cash reserve requirements

## 📈 Usage

### Starting a New Cycle

```bash
curl -X POST http://localhost:8000/cycle/start
```

### Triggering Scenario Allocation

```bash
curl -X POST http://localhost:8000/scenarios/execute
```

### Resetting Scenarios

```bash
curl -X POST http://localhost:8000/scenarios/reset
```

### Updating Performance Metrics

```bash
curl -X POST http://localhost:8000/scenarios/update_unrealized
```

## 🧪 Testing

```bash
# Run system integration test
python3 scripts/test_system.py

# Test database connection
docker-compose exec postgres psql -U dojo -d dojo_allocator -c "SELECT 1"
```

## 📚 Documentation

- [AWS Deployment Guide](AWS_DEPLOYMENT.md) - Deploy to AWS
- [How It Works](dashboard/app.py) - See "How It Works" page in dashboard
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [GitHub Setup Guide](GITHUB_SETUP.md) - Repository setup

## 🔐 Security

- All sensitive data excluded from repository
- Environment variables managed via `.env` files
- Production-ready SSL/TLS configuration
- Database password encryption support
- API key security best practices

## 📋 Project Structure

```
dojo_allocator/
├── src/
│   ├── api/              # FastAPI endpoints
│   ├── core/             # Business logic (allocators, managers)
│   ├── data/             # Data fetchers (SEC, OpenInsider, etc.)
│   ├── execution/        # Broker and order management
│   ├── models/           # Database models
│   ├── scheduler/        # Celery tasks
│   └── utils/            # Utilities
├── dashboard/            # Streamlit dashboard
├── config/               # Configuration files
├── scripts/              # Utility scripts
├── docker-compose.yml    # Development setup
├── docker-compose.prod.yml # Production setup
└── requirements.txt     # Python dependencies
```

## 🛠️ Management Commands

```bash
# Start services
./manage.sh start

# Stop services
./manage.sh stop

# View logs
./manage.sh logs -f

# Create backup
./manage.sh backup

# Update application
./manage.sh update

# Health check
./manage.sh health
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is proprietary software. All rights reserved. See the [LICENSE](LICENSE) file for details.

**Important:** This software is NOT free to use, modify, or distribute without explicit written permission from the copyright holder.

## ⚠️ Disclaimer

**This software is for educational and paper trading purposes only. It is not financial advice.**

- All trading is simulated (paper trading)
- Past performance does not guarantee future results
- Trading involves risk of financial loss
- Use at your own risk

## 🙏 Acknowledgments

- Built with inspiration from legendary investors:
  - Warren Buffett
  - George Soros
  - Ray Dalio
  - Paul Tudor Jones
  - Japanese trading discipline

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the documentation in the dashboard
- Review the API documentation at `/docs`

## 📊 Status

![GitHub last commit](https://img.shields.io/github/last-commit/zg-netizen/dojo_allocator)
![GitHub repo size](https://img.shields.io/github/repo-size/zg-netizen/dojo_allocator)
![GitHub language count](https://img.shields.io/github/languages/count/zg-netizen/dojo_allocator)

---

**Made with ❤️ for algorithmic trading enthusiasts**

