# IBM Power Porting Triage Agent

An intelligent agentic AI system that automates the assessment of enterprise workload migration readiness to IBM Power (`ppc64le`) architecture. The system performs multi-source availability lookups, recursive transitive dependency analysis, architecture-specific code heuristics, and generates executive sales qualification deliverables.

![Architecture](https://img.shields.io/badge/Architecture-ppc64le-blue)
![Python](https://img.shields.io/badge/Python-3.9+-green)
![React](https://img.shields.io/badge/React-18.3+-61DAFB)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688)
![License](https://img.shields.io/badge/License-IBM-blue)

## 🚀 Features

### Core Capabilities

- **Universal Ingestion**: Parses SBOMs (CycloneDX, SPDX), Dockerfiles, language manifests (requirements.txt, package.json, pom.xml, go.mod), and freeform text
- **Multi-Source Probing**: Queries Docker Hub, Quay.io, RHEL/Ubuntu package repositories, PyPI, and IBM Power ecosystem databases
- **Transitive Dependency Analysis**: Recursively scopes build-time dependencies and computes compounded porting effort
- **Architecture Sensitivity Detection**: Identifies x86 SIMD/AVX instructions, inline assembly, and 64KB page size issues
- **Agentic AI Orchestration**: Uses Google Gemini API with function calling for intelligent reasoning and synthesis
- **Executive Reporting**: Generates readiness scores, effort estimates (person-days), and pre-sales qualification memos

### Real-Time Intelligence

- **Live Agent Reasoning Stream**: Watch the AI agent think and make decisions in real-time via Server-Sent Events (SSE)
- **Interactive Dependency Tables**: Drill down into package analysis with sortable, filterable views
- **Executive Scorecard**: Visual dashboard with migration readiness metrics
- **Code Audit Deep-Dive**: Detailed architecture sensitivity analysis with SIMD complexity tiers

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                    │
│  - Real-time agent reasoning stream (SSE)                   │
│  - Interactive dependency tables with drill-down            │
│  - Executive scorecard & export capabilities                │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / Server-Sent Events
┌────────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI + Python)                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. Universal Normalizer (PURL, SBOM, Docker, Python)  │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 2. Multi-Source Prober (Registries, Repos, PyPI)      │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 3. Build Analyzer (Transitive deps, SIMD detection)   │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 4. Repo Scanner (Git clone, Dockerfile/CI analysis)   │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ 5. Agentic AI Layer (Gemini Tool Calling + Synthesis) │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.9+ with FastAPI and Uvicorn
- Pydantic for data validation and serialization
- Google GenAI SDK (`google-genai`) for Gemini API integration
- httpx for async HTTP requests to registries
- PyYAML for configuration parsing

**Frontend:**
- React 18.3+ with Vite build system
- Lucide React for icons
- Custom CSS design system (IBM Carbon-inspired dark theme)
- Server-Sent Events (SSE) for real-time streaming

**Deployment:**
- Docker containerization for both frontend and backend
- Docker Compose orchestration with health checks
- Nginx for frontend static file serving

## 📦 Prerequisites

- **Docker** and **Docker Compose** (recommended for quick start)
- **Python 3.9+** (for local development)
- **Node.js 18+** (for frontend development)
- **Google Gemini API Key** (optional - system runs in simulation mode without it)

## ⚡ Quick Start

### Using Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd gemini-elite-ai
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Gemini API key (optional)
   ```

3. **Start the application:**
   ```bash
   docker-compose up --build
   ```
   
   Or use the convenience script:
   ```bash
   ./docker-start.sh
   ```

4. **Access the application:**
   - Frontend: http://localhost:5173 or http://localhost:80
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/health

5. **Stop the application:**
   ```bash
   docker-compose down
   ```
   
   Or use the convenience script:
   ```bash
   ./docker-stop.sh
   ```

## 🔧 Installation

### Local Development Setup

#### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp ../.env.example ../.env
   # Edit .env and add your Gemini API key
   ```

5. **Run the backend server:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```

4. **Access the application:**
   - Frontend: http://localhost:5173

## 💡 Usage

### Basic Workflow

1. **Input Your Workload**: Choose from three input methods:
   - **SBOM/Manifest**: Paste CycloneDX, SPDX, requirements.txt, package.json, etc.
   - **Dockerfile**: Paste your Dockerfile content
   - **Freeform Text**: Describe your workload in natural language

2. **Load Sample Workloads**: Try one of four curated demo scenarios:
   - Enterprise Cloud Microservices
   - AI/ML Data Pipeline
   - High-Throughput Storage Engine
   - Legacy Financial Analytics

3. **Run Analysis**: Click "Analyze Workload" and watch the AI agent work in real-time

4. **Review Results**:
   - **Executive Scorecard**: Migration readiness score, effort estimates, risk factors
   - **Dependency Table**: Detailed package-by-package analysis with availability tiers
   - **Code Audit**: Architecture sensitivity findings (SIMD/AVX, inline assembly, page size issues)

5. **Export Reports**: Generate executive summaries, technical reports, or raw JSON data

### Understanding Availability Tiers

The system classifies packages into five tiers:

- **Tier 1 (Native)**: Native ppc64le packages in official repos - ready to use
- **Tier 2 (Agnostic)**: Platform-agnostic (scripts, bytecode) - no porting needed
- **Tier 3 (Substitute)**: Substitute packages available - minor changes required
- **Tier 4 (Unported)**: Requires source build - moderate effort
- **Tier 5 (Blocker)**: Proprietary x86 dependencies - high risk/effort

### SIMD Complexity Tiers

For x86 SIMD/AVX code, the system provides four complexity levels:

- **Direct**: Simple macro drop-in replacements
- **SIMDe Compatible**: SIMDe header library mapping
- **Partial Rewrite**: Mixed intrinsics requiring VSX rewrite
- **Full Redesign**: Deep AVX-512 dependencies requiring significant refactoring

## 📚 API Documentation

### Endpoints

#### Health Check
```http
GET /api/health
```
Returns the health status of the API.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

#### Sample Workloads
```http
GET /api/sample-workloads
```
Returns curated demo workloads for testing.

**Response:**
```json
{
  "workloads": [
    {
      "id": "enterprise-microservices",
      "name": "Enterprise Cloud Microservices",
      "description": "...",
      "manifest": "..."
    }
  ]
}
```

#### Synchronous Triage
```http
POST /api/triage
Content-Type: application/json

{
  "input_text": "your workload description or manifest",
  "input_type": "sbom|dockerfile|freeform"
}
```

**Response:**
```json
{
  "readiness_score": 85,
  "total_effort_days": 12.5,
  "packages": [...],
  "arch_sensitivity": {...},
  "executive_summary": "..."
}
```

#### Streaming Triage (SSE)
```http
POST /api/triage/stream
Content-Type: application/json

{
  "input_text": "your workload description or manifest",
  "input_type": "sbom|dockerfile|freeform"
}
```

**Response:** Server-Sent Events stream with real-time agent steps and final result.

### Interactive API Documentation

Visit http://localhost:8000/docs for the full interactive Swagger UI documentation.

## 🛠️ Development

### Project Structure

```
gemini-elite-ai/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── agent.py             # Core agentic orchestrator
│   ├── models.py            # Pydantic schemas
│   ├── normalizer.py        # Universal manifest parser
│   ├── prober.py            # Multi-source availability engine
│   ├── build_analyzer.py    # Transitive dependency resolver
│   ├── repo_scanner.py      # Git repository analysis
│   ├── gemini_helper.py     # Gemini API utilities
│   ├── requirements.txt     # Python dependencies
│   └── tests/               # Unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main application component
│   │   └── components/      # Reusable UI components
│   ├── package.json         # Node.js dependencies
│   └── vite.config.js       # Vite configuration
├── docker-compose.yml       # Docker orchestration
├── .env.example             # Environment variables template
└── README.md                # This file
```

### Code Organization

**Backend Modules:**
- `main.py`: API endpoints and FastAPI configuration
- `agent.py`: Agentic AI orchestration with Gemini function calling
- `models.py`: Pydantic data models for validation and serialization
- `normalizer.py`: Parses SBOMs, Dockerfiles, and language manifests
- `prober.py`: Queries Docker Hub, PyPI, and package repositories
- `build_analyzer.py`: Analyzes dependencies and architecture sensitivities
- `repo_scanner.py`: Clones and scans Git repositories
- `gemini_helper.py`: Gemini API interaction utilities

**Frontend Components:**
- `InputSection.jsx`: Tabbed input with sample workload loaders
- `AgentLiveFeed.jsx`: Real-time agent execution stream
- `Scorecard.jsx`: Executive metrics dashboard
- `DependencyTable.jsx`: Interactive package analysis table
- `CodeAuditModal.jsx`: Architecture sensitivity deep-dive
- `ExportModal.jsx`: Report generation and export

### Adding New Features

#### Adding a New Package Ecosystem

1. Update `normalizer.py` to parse the new manifest format
2. Add probing logic in `prober.py` for the ecosystem's registry
3. Update `BuildAnalyzer` if the ecosystem has unique build patterns
4. Add test cases in `backend/tests/`

#### Extending Architecture Heuristics

1. Add detection patterns in `build_analyzer.py`
2. Update `ArchSensitivity` model in `models.py` with new fields
3. Adjust effort multipliers in `scale_arch_effort()` function
4. Update frontend to display new sensitivity indicators

### Environment Variables

Create a `.env` file in the project root:

```bash
# Google Gemini API Key for dynamic LLM reasoning
# If left empty, the system runs in autonomous simulation mode
GEMINI_API_KEY=your_gemini_api_key_here

# Preferred Gemini model (recommended: gemini-3.5-flash)
GEMINI_MODEL=gemini-3.5-flash
```

**Note:** The system will run in "autonomous simulation mode" if no API key is provided, faithfully emulating multi-step tool calling and streaming thought steps.

## 🧪 Testing

### Backend Tests

Run the test suite:
```bash
cd backend
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html
```

### Manual Testing

Use the sample workloads provided in the UI or via the API:
```bash
curl http://localhost:8000/api/sample-workloads
```

## 🐛 Troubleshooting

### Backend Issues

**Backend won't start:**
- Verify Python 3.9+ is installed: `python --version`
- Check that all dependencies are installed: `pip list`
- Ensure port 8000 is not already in use: `lsof -i :8000`

**Gemini API errors:**
- Verify API key is correctly set in `.env`
- Check API quota limits in Google Cloud Console
- System will automatically fall back to simulation mode if API is unavailable

### Frontend Issues

**Frontend build fails:**
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Verify Node.js version is 18+: `node --version`
- Check for port conflicts on 5173

### Docker Issues

**Docker Compose fails:**
- Ensure Docker daemon is running: `docker info`
- Check logs: `docker-compose logs backend` or `docker-compose logs frontend`
- Rebuild containers: `docker-compose up --build --force-recreate`
- Clean up old containers: `docker-compose down -v`

**Port conflicts:**
- Backend (8000), Frontend (5173, 80) must be available
- Change ports in `docker-compose.yml` if needed

### Common Issues

**"Connection refused" errors:**
- Ensure both backend and frontend are running
- Check that services are healthy: `docker-compose ps`
- Verify network connectivity between containers

**Slow performance:**
- Shallow Git clones are used to minimize I/O
- HTTP requests use connection pooling
- Consider increasing Docker resource limits

## 🔒 Security Considerations

- **API Keys**: Never commit API keys to the repository
- **Environment Variables**: Use `.env` files for local development (excluded via `.gitignore`)
- **Production Deployment**: Use Docker secrets or environment variables
- **CORS**: Currently configured for development (`allow_origins=["*"]`) - restrict in production
- **Input Validation**: All inputs are validated using Pydantic schemas

## 📄 License

This project is proprietary to IBM. All rights reserved.

## 🤝 Contributing

This is an internal IBM prototype. For questions or contributions, please contact the development team.

## 📞 Support

For issues, questions, or feature requests, please contact:
- **Development Team**: [Your Team Contact]
- **Documentation**: See `AGENTS.md` for detailed development guidelines

## 🎯 Roadmap

- [ ] Support for additional package ecosystems (Rust, Go modules)
- [ ] Enhanced SIMD detection with more granular complexity scoring
- [ ] Integration with IBM Power ecosystem databases
- [ ] Automated CI/CD pipeline integration
- [ ] Multi-language support for executive reports
- [ ] Historical analysis and trend tracking

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - UI library
- [Vite](https://vitejs.dev/) - Frontend build tool
- [Google Gemini](https://ai.google.dev/) - Agentic AI capabilities
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Lucide React](https://lucide.dev/) - Icon library

---

**Made with ❤️ by IBM**
