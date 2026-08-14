# Research Decisions

## Working Title

Comparative Evaluation of Multi-Agent AI Frameworks for Real-World Task Automation

## Optional Subtitle

A Reproducible Benchmarking Study of LangGraph, CrewAI, and AutoGen

## Target Venue

IEEE International Conference on Agentic AI

## Full Paper Format

Detailed research paper, approximately 18–22 pages before compression.

## IEEE Submission Format

IEEE conference version, compressed to the official page limit after the full paper is complete.

## Frameworks

- LangGraph
- CrewAI
- AutoGen

## Task Suite

- T1: Research Synthesis Agent
- T2: Customer Support Triage
- T3: Data Cleaning Pipeline
- T4: Travel Planning Assistant
- T5: Code Review and Refactoring Agent

## Evaluation Dimensions

### Performance
- Task completion rate
- Accuracy or F1 where applicable
- Reasoning quality

### Efficiency
- End-to-end latency
- Throughput
- Token usage
- API cost

### Reliability
- Failure rate
- Recovery success
- Output consistency

### Resource Usage
- Memory footprint
- Concurrency behavior

### Engineering
- Lines of code
- Development time
- Debugging effort
- Maintainability
- Learning curve

## Planned Replication

Multiple runs per task and framework. Final run count to be fixed before experiments.

## Open-Source Artifacts

- Benchmark code
- Framework adapters
- Task definitions
- Prompts
- Evaluation scripts
- Statistical analysis
- Figures and tables
- Reproduction instructions

---

## Decisions to Lock

Mark each item **Pending** until an explicit value is chosen. Do not fill in unknown values with guesses — the master rule is: **do not claim that a factor is controlled until you have actually controlled it.**

| Item | Decision Required | Status | Value |
|---|---|---|---|
| LLM | Exact model name and version | Pending | |
| Provider | API provider or local inference | Pending | |
| Temperature | Exact value | Pending | |
| Maximum tokens | Exact value | Pending | |
| Hardware | CPU, RAM, GPU, operating system | Pending | |
| Python | Exact version | Pending | |
| Framework versions | Exact versions for all three frameworks | Pending | |
| Number of runs | e.g. 5, 10, or more per task | Pending | |
| Tool access | Search, APIs, code execution, database, or none | Pending | |
| Evaluation method | Rule-based, reference-based, human, LLM judge, or hybrid | Pending | |
| Cost calculation | Provider pricing snapshot and formula | Pending | |
| Scalability test | Agent counts and workload levels | Pending | |
| Developer study | Who develops the systems and how time is measured | Pending | |
