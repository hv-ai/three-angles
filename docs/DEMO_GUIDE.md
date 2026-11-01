# Three Angles five minute demo

Run a live investigation before recording. Keep the completed case in Investigations so the demonstration does not depend on waiting for every API request. If you show the prepared example, identify it as curated. Do not display API keys.

## Brief to use

An assistant for small remote teams that turns recurring meeting transcripts into a searchable log of decisions, owners and unresolved questions. Investigate the documented problem, overlap with existing meeting tools, and assumptions that could make this idea fail. Focus on finding the latest decision when it changes across meetings.

## Follow up to use

Check whether the named products document tracking decisions that are reversed or changed across meetings. Use official product documentation where possible. Separate confirmed features from capabilities you could not verify, and explain whether this changes your recommendation.

## Recording sequence

| Time | Screen | What to explain |
| --- | --- | --- |
| 0:00-0:35 | Home page and brief | I built Three Angles to help someone investigate an idea before spending time building it. The output is a decision brief and an experiment to try next. |
| 0:35-1:15 | Launch or open a completed live case | Three independent model conversations investigate the problem, existing alternatives and the weakest assumptions. Each chooses searches and sources through tools. |
| 1:15-2:05 | One finding and its evidence | Show a specific, useful discovery. Open its source. Explain what it establishes and what remains an inference. |
| 2:05-3:10 | Challenge a finding | Send the follow-up above to the relevant investigator. Show a new query or source opening, then an already-completed follow-up if the API is still working. Explain that prior reports are retained. |
| 3:10-3:50 | Comparison and decision | Explain a real tension or unanswered question. Record your decision and rationale. Do not claim the recommendation must change. |
| 3:50-4:30 | GitHub architecture and tests | Python worker threads run the investigators concurrently. SQLite stores research history. Native tool calls reach Nebius or Fireworks and Tavily. Mention a tested error case. |
| 4:30-4:55 | Final app view | I used Codex to implement and debug the workflow. My main learning was that useful agents need explicit state, bounded tools, recovery, and a way for a person to redirect the work. |

## Explain it in plain English

An LLM chooses the next allowed action. Python executes that action and returns its result. The LLM then decides whether to search again, open a source, or submit findings. A separate comparison call reads the three finished reports. The human can redirect one investigator and retains the final decision.

These are three separate conversations with the same configured model, not necessarily three different model families. SQLite is local storage, not a vector database. Tavily searches current public pages; this project does not require Pinecone or dense retrieval. Custom Python implements the orchestration; LangGraph is not used.

## Before submitting

- Finish at least one live run and one targeted follow-up. Export the history.
- Record which provider and exact model ID worked, plus observed elapsed time. Do not invent latency or quality results.
- Check the repository link is accessible to reviewers, or submit the source ZIP as permitted by the handout.
- Upload the project overview DOCX to Google Drive and open it with Google Docs if a Google Doc link is required.
- Record your own video and submit it with the code and document links through the course form.
