# Three Angles

A research workspace for checking an idea before building it.

I wanted to look at an idea from more than one direction: does the problem matter, what already exists, and what assumption could make it fail? Three Angles gives each question its own investigator, then brings their findings together.

You enter a brief. The investigators search the web, read sources and produce separate reports. You can open the evidence behind a finding, challenge it, and send one investigator back with a more specific question. Earlier reports stay available so you can see what changed.

## What you can do

- Research a brief from three perspectives: the problem, existing solutions and a skeptic.
- Read source excerpts alongside findings, with source claims and investigator inferences labeled separately.
- Challenge a finding without restarting the whole investigation.
- Compare the reports and record your own decision: pursue, reshape, drop or research further.
- Reopen saved investigations and export the research and your notes.

## Run it locally

You need Python 3.10 or later and a browser. There are no third-party Python dependencies.

```bash
python3 server.py
```

Open [localhost:8766](http://127.0.0.1:8766/). On macOS, you can also double-click `Start.command`. For another port:

```bash
python3 server.py --port 8767
```

In **Connect your tools**, enter a Nebius or Fireworks API key, the exact ID of a model that supports native function calling, and a Tavily API key. Live research uses credits from those accounts. Keys stay in page memory and active server jobs; they are not saved with investigations. Refreshing the page clears the connection.

To explore without API keys, open the worked example. It is labeled as a curated example and makes no API calls.

## Hosting

The repository includes a Render Blueprint in `render.yaml`. Connect this repository in Render, create a Blueprint and deploy the `three-angles` web service. It uses Python directly, listens on the assigned port and checks `/health`.

Hosted mode separates visitor histories using an anonymous, secure browser cookie. No provider keys need to be configured on the host: visitors connect their own tools in the app. Local mode retains the original single-user workspace.

The free Render configuration uses temporary storage. Export research you want to keep; history can be lost when the service sleeps, restarts or redeploys. For durable storage, use a hosting plan with a persistent disk and set `DATA_DIR` to its mounted path. The free service can also take time to wake after inactivity.

## How it works

The three investigators use the same configured model in separate conversations, each with a different role and its own sources. Python worker threads run them concurrently.

Each investigator can choose three tools:

| Tool | Purpose |
| --- | --- |
| `search_web` | Find relevant public pages through Tavily |
| `open_source` | Read a source and obtain excerpts |
| `publish_findings` | Submit a structured report linked to those excerpts |

A separate model call compares the completed reports. A challenge creates a new round for the selected investigator and updates the comparison when it finishes. Each round is bounded to seven model calls, two searches and three opened sources per investigator.

The backend uses Python's standard library: `http.server` for the local server, `concurrent.futures` for workers, `urllib` for API requests and `sqlite3` for storage. The frontend is plain HTML, CSS and JavaScript.

Investigations are stored locally in `.data/investigations.sqlite3`. If a step fails, completed research is retained. You can retry one investigator, or retry just the comparison using the saved reports.

## An example from testing

I tested a brief about tracking decisions that change across meetings. The initial research suggested a gap in existing meeting tools. The skeptic found vendor pages describing reversal or contradiction tracking, which challenged that claim. The final comparison recommended reshaping the idea.

That was a useful reminder: not finding a feature in the first few sources does not mean it doesn't exist. Vendor descriptions also need to be checked before treating them as proven capabilities.

## Project files

| File | Contents |
| --- | --- |
| `research.py` | Investigator loop, provider requests, storage and recovery |
| `server.py` | Local server and API routes |
| `src/` | Browser interface |
| `sample.py` | Curated worked example |
| `tests/test_research.py` | Backend tests with simulated provider responses |
| `docs/PROJECT.md` | Architecture notes |
| `docs/VALIDATION.txt` | Test coverage and live verification record |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The 36 automated tests cover orchestration, source references, follow-ups and recovery. A complete Nebius/Tavily investigation was also checked on October 31, 2026. See [the validation record](docs/VALIDATION.txt) for details.

Source excerpts help trace a finding back to a page; they do not prove that its interpretation is correct. The workspace supports research and a human decision. Establishing product demand still needs conversations with users and practical tests.
