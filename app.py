"""
Milestone 5 — Query Interface (Gradio web UI)

The user-facing end of the pipeline. A viewer types a question, gets back a
grounded answer plus the list of documents that answer was drawn from.

The actual work lives in query.ask(); this file is only the interface wiring.
Sources are produced by ask() from retrieval metadata, so what the UI shows in
"Retrieved from" is guaranteed to match the chunks the answer was grounded in.

Run:  python app.py   then open  http://localhost:7860
"""

import gradio as gr

from query import ask

EXAMPLES = [
    "Which amenities does The Standard at Tampa highlight?",
    "What features does Halo 46 list on its amenities page?",
    "What amenities are featured for Hub On Campus Tampa?",
    "What does 4050 Lofts showcase on its amenities page?",
    "What amenities are listed for Venue at North Campus?",
]


def handle_query(question: str):
    """Run one question through the grounded pipeline and format for display."""
    result = ask(question)
    if result["sources"]:
        sources = "\n".join(f"• {s}" for s in result["sources"])
    else:
        sources = "(no sources — the guide doesn't cover this)"
    return result["answer"], sources


with gr.Blocks(title="The Unofficial Guide — USF Tampa Off-Campus Housing") as demo:
    gr.Markdown(
        "# The Unofficial Guide\n"
        "Ask about amenities at off-campus student housing near USF Tampa. "
        "Answers come **only** from the collected property pages, with sources listed."
    )
    inp = gr.Textbox(
        label="Your question",
        placeholder="e.g. What amenities does The Standard at Tampa highlight?",
    )
    btn = gr.Button("Ask", variant="primary")
    answer = gr.Textbox(label="Answer", lines=8)
    sources = gr.Textbox(label="Retrieved from", lines=4)

    gr.Examples(examples=EXAMPLES, inputs=inp)

    btn.click(handle_query, inputs=inp, outputs=[answer, sources])
    inp.submit(handle_query, inputs=inp, outputs=[answer, sources])


if __name__ == "__main__":
    demo.launch()
