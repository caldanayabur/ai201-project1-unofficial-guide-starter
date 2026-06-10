

https://github.com/user-attachments/assets/93847d18-e915-4851-913e-43289f8c36b4

# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

Off-campus student housing amenities around the **USF Tampa** campus. The system answers
questions about what each apartment complex offers — pools, fitness centers, study lounges,
parking, smart-home features, and so on — for students comparing places to live.

This knowledge is valuable because it is scattered: each property publishes its amenities on
its own marketing site, in its own layout and vocabulary, mixed in with leasing CTAs, pricing
banners, and cookie notices. A student who wants to compare ten complexes normally has to open
ten sites and dig through the boilerplate on each. This guide ingests those pages, strips the
marketing noise, and lets a student ask one question and get a grounded, per-property answer
with the source link — instead of tab-hopping across a dozen sites that are each optimized to
sell rather than to inform.

---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

All ten sources are the official property/amenities pages for student-housing complexes near
USF Tampa. Each was fetched with `requests` + BeautifulSoup (`ingest.py`), cleaned
(`clean.py`), and stored as JSON in `documents/`.

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | The Standard at Tampa | Official site showcasing luxury community amenities like the rooftop pool and golf simulator. | https://thestandardtampa.landmark-properties.com/amenities/ |
| 2 | Halo 46 | Official amenities page highlighting smart-home features, resort pool, and 24/7 fitness center. | https://www.halo46studentliving.com/amenities/ |
| 3 | Hub On Campus Tampa | Official amenities page featuring the rooftop deck, hot tub, on-site barista coffee, and study lounges. | https://huboncampus.com/tampa/amenities/ |
| 4 | The Province Tampa | Official property overview listing clubhouse features, theater room, and outdoor grilling stations. | https://www.americancampus.com/student-apartments/fl/tampa/the-province-tampa |
| 5 | Avalon Heights | Official features overview detailing the 24-hour mega fitness center, basketball courts, and study lounges. | https://www.americancampus.com/student-apartments/fl/tampa/avalon-heights |
| 6 | 4050 Lofts | Official amenities section showcasing the two resort-style swimming pools, resident lounge, and coffee bar. | https://www.4050lofts.com/apartments/fl/tampa/amenities |
| 7 | Venue at North Campus | Official property portal highlighting the cyber cafe, pet park, sand volleyball courts, and gated access. | https://venueatnorthcampus.prospectportal.com/tampa/venue-at-north-campus/amenities/ |
| 8 | Station 42 | Official community page detailing the renovated clubhouse, outdoor grills, and 24/7 student study rooms. | https://station42.us/amenities/ |
| 9 | 42N Apartments | Official amenities guide covering the hammock garden, fire pits, and outdoor half-basketball court. | https://www.live42n.com/amenities/ |
| 10 | The Ivy | Official amenities page detailing the boutique clubhouse, movie theater room, and tennis courts. | https://www.livetheivy.com/apartments/fl/tampa/amenities |


---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** Target **275 tokens (~1,100 characters)**, the midpoint of the planned
250–300 token range. Token budgets are converted to characters at ~4 chars/token so no
tokenizer is needed at ingest time (`chunk.py`).

**Overlap:** **~45 tokens (~180 characters)**, paragraph-aligned. Rather than cutting mid-text,
the next chunk *backs up* by whole trailing paragraphs of the previous chunk until it reaches
the overlap budget, so a heading is never split from the list that follows it.

**Why these choices fit your documents:** These are short, section-structured marketing pages —
an amenities heading followed by a list, repeated. Before chunking, `clean.py` strips the
boilerplate that would otherwise dominate small chunks: it removes whole boilerplate sections
(contact blocks, cookie banners, end-of-page CTAs), drops junk lines (pricing banners like
`$820 / Month`, "Schedule a Tour", "Apply Now", lone carousel numbers, floor-plan nav labels),
fixes mojibake/encoding artifacts (curly quotes, em dashes), and de-duplicates repeated lines.
Chunking then splits the cleaned text on blank lines into paragraph units and greedily merges
them up to the target size, which keeps a property's amenity list together in one chunk instead
of fragmenting it. A target of ~275 tokens is large enough to hold a full amenity list but small
enough that retrieval stays specific to one section. Tail chunks under ~50 tokens are merged
back into the preceding chunk so no useless fragments are emitted.

**Final chunk count:** **23 chunks** across the 10 documents.

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** **`all-MiniLM-L6-v2`** via sentence-transformers, run locally (no API key, no
per-query cost). Retrieval uses **top-k = 5** with **cosine distance** in ChromaDB. One tuning
detail: many chunks are bare amenity lists with no property name in their text, so a query like
"amenities at The Standard" would match a generic intro chunk of the *wrong* complex. To fix
this, each chunk's text is **prepended with its property name before embedding** (the clean text
is still stored separately for display), which keeps retrieval specific to the correct property.
Top-k was raised from 4 to 5 after testing, because the chunk actually listing The Standard's
pool and multi-sport simulator ranked #5. Retrieval is also **property-aware**: when a question
names exactly one known property, the query is scoped with a ChromaDB metadata filter
(`where={"property_name": ...}`) to return all of that property's chunks rather than a raw top-5,
so a single-property question gets that property's complete amenity list and no unrelated sources
(see Failure Case Analysis). General or multi-property questions fall back to plain top-k.

**Production tradeoff reflection:** I chose a small local model because the corpus is short,
English, single-domain official pages, where MiniLM is fast and accurate enough, and running it
locally avoids API cost and latency. If cost weren't a constraint and this served real users, I
would weigh: **accuracy on domain text** (a larger model such as `bge-large` or an API embedder
like OpenAI `text-embedding-3-large` would separate near-duplicate amenity lists across similar
properties more reliably); **context length** (MiniLM truncates at 256 tokens, which is fine for
my ~275-token chunks but would force smaller chunks if pages were longer); **multilingual
support** (irrelevant here since all pages are English, but a multilingual model would matter if
sources included non-English listings); and **latency / local vs. hosted** (a hosted embedder
adds network latency and a dependency on an external service, traded for higher accuracy). For
this project the accuracy gain wouldn't justify the added cost and complexity.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:** Generation runs through Groq's
`llama-3.3-70b-versatile` (`query.py`) at temperature 0. The retrieved chunks are formatted into
a numbered `CONTEXT:` block, each tagged with its property and source document, and the system
prompt makes grounding a hard rule rather than a suggestion. The actual instruction:

> 1. Answer using ONLY the information in the CONTEXT section of the user message. The context is the sole source of truth.
> 2. Do NOT use any prior or general knowledge about apartments, amenities, Tampa, or these properties. If a fact is not in the context, you do not know it.
> 3. If the context does not contain enough information to answer the question, reply with exactly this sentence and nothing else: "I don't have enough information on that."
> 4. Do not speculate, generalize, or add caveats drawn from outside the context. Do not invent property names, amenities, or details.
> 5. The context may contain chunks from several different properties. Each chunk is labelled with its property. Attribute an amenity to a property ONLY if it appears in a chunk labelled with that same property. Never mix amenities from one property into the answer for another.

Grounding is enforced at three layers, not just by the prompt: (a) a **relevance gate** — if the
best retrieved chunk's cosine distance exceeds 0.9, the system returns the "not enough
information" sentence *without ever calling the LLM*, so clearly off-domain questions can't draw
a confident-sounding answer from training data; (b) the **strict system prompt** above; and
(c) **temperature 0** for deterministic, non-creative output. Tested against an out-of-domain
question ("best pizza in downtown Chicago"), the system correctly returns the refusal sentence
with no sources.

**How source attribution is surfaced in the response:** Attribution is **programmatically
guaranteed, not left to the LLM**. `ask()` returns `{"answer", "sources"}`, where `sources` is
built in Python from the retrieval metadata of the chunks that were actually placed in
context — property name, source document, and source URL — de-duplicated in best-match order. It
is never parsed out of the model's free text, so the model cannot forget to cite, mis-cite, or
invent a source. The Gradio UI (`app.py`) shows these in a separate "Retrieved from" box beside
the answer. When the model returns the refusal sentence, the sources list is dropped so a refusal
can't appear falsely "cited."

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | Which amenities does The Standard at Tampa highlight? | Rooftop Fitness Center, Academic Lounge, Computer Center, Yoga Room, Sauna, Tanning Beds, Fully Furnished, Private Bedrooms/Bathrooms Available, Granite Countertops, Stainless Steel Appliances, Full-Size Washer/Dryer, High-Speed Internet & Cable, Balconies, Ceiling Fans Throughout, Private Courtyards, Rooftop Pool, Grilling Area, Hammocks, Cornhole Area, Outdoor Gaming Lawn, Arcade & Game Room, PGA Golf Simulator, Shops and Dining, Parking Garage, Bike Storage, Pet Friendly, On-Site Maintenance & Management, You Speak, We Listen Program, Community Rewards, RentPlus Program, Rentable Storage, Standard Perks, EV Charging |The Standard at Tampa highlights the following amenities: Rooftop Fitness Center, Academic Lounge, Computer Center, Yoga Room, Sauna, Tanning Beds, Fully Furnished, Private Bedrooms/Bathrooms, Granite Countertops, Stainless Steel Appliances, Full-Size Washer/Dryer, High-Speed Internet & Cable, Balconies, Ceiling Fans, Private Courtyards, Rooftop Pool, Grilling Area, Hammocks, Cornhole Area, Outdoor Gaming Lawn, Arcade & Game Room, PGA Golf Simulator, and Shops and Dining. | Relevant | Partially accurate |
| 2 | What features does Halo 46 list on its amenities page? | Friendly Management & 24/7 Support, Resident Parking Available, Keyless Entry & Secure Package Lockers, Convenient Bull Runner Shuttle Bus Stop, Resort-Style Pool with Spacious Sundeck, Game Lounge and Social Spaces, Outdoor Grilling and Picnic Areas, Dog Park for You and Your Furry Friend, 24-Hour Fitness Center for Anytime Workouts, Private Study Lounges for Quiet Focus, Co-Working Spaces & Meeting Rooms for Collaboration, Dedicated Study Areas to Help You Stay on Track, Private Bedrooms and Bathrooms, Fully Furnished with Modern Décor, In-Unit Washer & Dryer for Easy Laundry, Alexa-Enabled Smart Technology in Every Unit, Fully Equipped Kitchen with Stainless Steel Appliances, Granite Countertops for a Sleek Touch, High-Speed Wi-Fi and Wired Internet Access, Large Smart HDTV for Entertainment | Halo 46 lists the following features on its amenities page: Resort-Style Pool, Game Lounge and Social Spaces, Outdoor Grilling and Picnic Areas, Dog Park, 24-Hour Fitness Center, Private Study Lounges, Co-Working Spaces & Meeting Rooms, Dedicated Study Areas, Friendly Management & 24/7 Support, Resident Parking Available, Keyless Entry & Secure Package Lockers, Convenient Bull Runner Shuttle Bus Stop, Private Bedrooms and Bathrooms, Fully Furnished with Modern Décor, In-Unit Washer & Dryer, Alexa-Enabled Smart Technology, Fully Equipped Kitchen with Stainless Steel Appliances, Granite Countertops, High-Speed Wi-Fi and Wired Internet Access, Large Smart HDTV. | Relevant | Accurate |
| 3 | What amenities are featured for Hub On Campus Tampa? | Rooftop Sundeck, Pool & Hot Tub, Built-In Seating & Outdoor Lounge With BBQ Area, Breathtaking Views Of Tampa, Fitness Center With State-Of-The-Art Fitness Equipment, Spa With Sauna, Yoga Room, Fitness Classes and Spa nights, Fully Furnished With Custom Designed Furniture, Individual Keyed Bedrooms, Blackout Shades In Each Bedroom, Walk-In Closets With Built-In Closet Organizers, Custom Roller Shades In Living Room, Full-Size Washer & Dryer In Each Apartment, Wood-Style Flooring, 55” Smart TV In Each Living Room, USB Ports In Kitchen & Bedrooms, Insulated Interior Walls, Large Openable Windows With Energy Efficient Double Pane Glass, Private Terrace With Outdoor Furniture & Breathtaking Views, Premium Stainless Steel Appliances, Quartz Stone Countertops, Designer Cabinetry & Track Lighting, Clubroom With TVs, Lounge Space & Coffee Bar, Executive Business Area With Macs, PCs & Printers, Private Meeting Rooms With Study, Outdoor Study Area, Free High Speed Wi-Fi Throughout The Building, Controlled Access & Key FOB System, Parking Available In Access Controlled Garage, Secured Bike-Storage Available, Events, Giveaways, Pop-Up Shops, Event Sponsorships, Collaborations With Local Brands, Dog Park With Built-In Activities, Energy Efficient Appliances & Lighting, Programmable Thermostats, Double Pane Windows, Ceiling Fan, High-Efficiency Plumbing Fixtures |Hub On Campus Tampa features the following amenities: Premium Stainless Steel Appliances, Quartz Stone Countertops, Designer Cabinetry & Track Lighting, Meet + Study, Clubroom, Executive Business Area, Private Meeting Rooms, Outdoor Study Area, Free High Speed Wi-Fi, Controlled Access & Key FOB System, Parking, Secured Bike-Storage, Dog Park, Energy Efficient Appliances, Programmable Thermostats, Double Pane Windows, Blackout Shades, Ceiling Fan, High-Efficiency Plumbing Fixtures, Rooftop + Pool, Rooftop Sundeck, Hot Tub, Built-In Seating & Outdoor Lounge With BBQ Area, Fitness Center, Spa With Sauna, Yoga Room, Fully Furnished With Custom Designed Furniture, Individual Keyed Bedrooms, Walk-In Closets, Custom Roller Shades, Full-Size Washer & Dryer, Wood-Style Flooring, 55” Smart TV, USB Ports, Insulated Interior Walls, and Private Terrace. | Relevant | Accurate |
| 4 | What does 4050 Lofts showcase on its amenities page? | Signature JOE Coffee Bar, The 4050 Lofts Swim Club with Two Resort-Style Pools, Redesigned Boutique Clubhouse, Private Study Lounges, Pet-Friendly Community, Bull Runner Bus System with a Direct Route to Campus, Gated Community, Reserved Covered Parking, Ideal Location in the 42nd Street Neighborhood, Near USF, Open 24 Hours a Day, State-of-the-Art Cardio Machines, Circuit Weight Training, Resident Lounge Area, Outdoor Kitchen & Pool Table, Green Egg Grills, Pet-Friendly Living, Individual Leasing, Roommate Matching Available, FaceTime Tours Available, Hassle-Free Resident Liability Program, 24-Hour Package Lockers, Onsite Storage, 24-Hour Onsite Emergency Maintenance, Signature JIM Fitness Center, Signature JOE Coffee Bar with Starbucks Cafe Machine, Free Printing Upon Request, Private Study Lounges, Close to the University of South Florida & Hillsborough Community College, Bull Runner Direct Route to Campus, Spacious 3 & 4 Bedroom Layouts, Flat-Screen LCD TV in Every Bedroom, Full-Size Washer & Dryer in Every Home, Fully Furnished with Deluxe Modern Furniture, Private Bedrooms & Bathrooms, Private Balconies |4050 Lofts showcases the following amenities: * Free Printing Upon Request, * Private Study Lounges, * Bull Runner Direct Route to Campus, * Spacious 3 & 4 Bedroom Layouts, * Flat-Screen LCD TV in Every Bedroom, * Full-Size Washer & Dryer in Every Home, * Fully Furnished with Deluxe Modern Furniture, * Private Bedrooms & Bathrooms, * Private Balconies, * Pet-Friendly Community, * Signature JOE Coffee Bar, * The 4050 Lofts Swim Club with Two Resort-Style Pools, * Redesigned Boutique Clubhouse, * The JIM Fitness Center, * Gated Community, * Reserved Covered Parking. | Relevant | Partially accurate |
| 5 | What amenities are listed for Venue at North Campus? | Bull Market Convenience Store, Electric Bike Rentals, LEED Gold Certified, Study Room, Cyber Cafe, 2 Resort Style Pools, 2 State-of-the-Art Fitness Centers, Computer Lab with Free Printing, 24/7 On-site Maintenance, Bark Park, Starbucks Coffee Machine, Luxer One Parcel Locker, Zen Courtyard, After Hour Patrol Service, Bicycle Racks, Gated Community, Club House, Visitor Parking, Bull Runner Bus Stop, Charcoal Grills, Covered Parking, Sand Volleyball, Fire Pit, Valet Trash Service, Washer, Balcony, Electronic Key Fob Access, Furnished, Hardwood Floors, Dishwasher, Dryer, Air Conditioner, Refrigerator, Smart TV in Common Area, Vaulted Ceiling, Walk-in Closet |Venue at North Campus has the following amenities: Community Amenities: - Bull Market Convenience Store, - Electric Bike Rentals, - LEED Gold Certified, - Study Room, - Cyber Cafe, - 2 Resort Style Pools, - 2 State-of-the-Art Fitness Centers, - Computer Lab with Free Printing, - 24/7 On-site Maintenance, - Bark Park, - Starbucks Coffee Machine, - Luxer One Parcel Locker, - Zen Courtyard, - After Hour Patrol Service, - Bicycle Racks, - Gated Community, - Club House, - Visitor Parking, - Bull Runner Bus Stop, - Charcoal Grills, - Covered Parking, - Sand Volleyball, - Fire Pit, Other Amenities: - Valet Trash Service, - Washer, - Balcony, - Electronic Key Fob Access, - Furnished, - Hardwood Floors, - Dishwasher, - Dryer, - Air Conditioner, - Refrigerator, - Smart TV in Common Area, - Vaulted Ceiling, - Walk-in Closet | Relevant | Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** Which amenities does The Standard at Tampa highlight?

**What the system returned (before the fix):** The system listed its information as coming from four different sources rather than just the one for that specific question. However, I did check the answers and found that the information was accurate for a specific housing option. The system also missed Parking Garage, Bike Storage, Pet Friendly, On-Site Maintenance & Management, You Speak We Listen Program, Community Rewards, RentPlus Program, Rentable Storage, Standard Perks, EV Charging for this question, but overall did a good job of providing the correct information for most amenities.

**Root cause (tied to a specific pipeline stage):** This is a chunking + retrieval boundary
problem. The Standard's amenities page is long enough that chunking splits it into two chunks:
chunk 0 holds the first sections (Rooftop Fitness Center through PGA Golf Simulator and Shops and
Dining), and chunk 1 holds the final "Relax, We've Got You" section — which is exactly the
missing items (Parking Garage, Bike Storage, Pet Friendly, On-Site Maintenance, You Speak We
Listen, Community Rewards, RentPlus, Rentable Storage, Standard Perks, EV Charging). When I run
the query, retrieval returns chunk 0 as the #1 result (distance 0.279), but chunk 1 never makes
the top-5: its content is mostly services and perks, which the embedding model sees as less
similar to "amenities highlight" than the marquee amenities in chunk 0, so it ranks below chunks
from four *other* properties. The model can only ground its answer in the chunks it is given, so
the items that live only in chunk 1 are absent. The same fact explains the "four sources"
observation: top-k is fixed at 5 and The Standard contributed only one chunk to that top-5, so
the other four slots were filled by the nearest chunks from other properties (Station 42, Hub,
The Province). Because my source list is built programmatically from every retrieved chunk, all
four properties show up under "Retrieved from" even though my anti-mixing prompt rule kept their
amenities out of the actual answer.

**What I changed to fix it:** I made retrieval property-aware (`embed.py`). When a question names
exactly one known property, `detect_property()` recognizes it and `retrieve()` scopes the
ChromaDB query to that property with a metadata filter (`where={"property_name": ...}`), returning
*all* of that property's chunks instead of a raw top-5. This pulls in The Standard's chunk 1, so
the previously missing items (Parking Garage, Bike Storage, Pet Friendly, On-Site Maintenance,
Rentable Storage, EV Charging) now appear, and "Retrieved from" lists only The Standard — no
unrelated properties. Questions that name no property, or compare more than one, fall back to the
original top-k search so general queries still work. Two alternatives I considered but rejected:
raising the chunk-size target so the ~370-token list fits in one chunk (loses retrieval
specificity), or a distance cutoff on sources (the other properties' amenity-list chunks sit too
close in distance — 0.331 vs 0.279 — to separate cleanly that way).

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:** It helped me understand better the nature of my source documents and why a specific retrieval approach was more appropriate for this use case.

**One way your implementation diverged from the spec, and why:**
**Tuning note (after implementation):** Two adjustments came out of testing retrieval against the evaluation queries:
1. *Property-tagged embeddings.* Many chunks are bare amenity lists with no property name in them, so property-specific queries matched generic intro chunks of the *wrong* complex. I now prepend the property name to each chunk's text before embedding (the clean text is still stored for display), which keeps retrieval specific to the correct apartment — exactly the intent noted in the Chunking Strategy.
2. *Top-k 4 → 5.* For "Which amenities does The Standard at Tampa highlight?", the chunk actually listing the pool and multi-sport simulator ranked #5, just outside k=4. Raising k to 5 brings the answer chunk into context without diluting the well-separated queries.
---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1 — Building the embedding + retrieval stage (Milestone 4)**

- *What I gave the AI:* I gave Claude the Retrieval Approach section and the Architecture diagram from `planning.md`, and asked it to implement the embedding step (load the chunks from `chunks.json`, embed them with `all-MiniLM-L6-v2`, and store them in ChromaDB with metadata for each chunk — at minimum the source document name and the chunk's position in that document) plus a `retrieve(query, k)` function that returns the top-k chunks with their source info.
- *What it produced:* `embed.py` — a `build_index()` that embeds every chunk and loads it into a persistent ChromaDB collection, and a `retrieve()` that returns each hit's text, cosine distance, and source metadata. It configured the collection to use cosine distance (instead of Chroma's default squared-L2) so the distance scores line up with the 0–1-style relevance scale, and added a `smoke_test()` that runs my evaluation-plan queries and prints each chunk with its distance.
- *What I changed or overrode:* The first test run showed a "right topic, wrong source" failure — querying *The Standard at Tampa* returned Station 42 at #1 because the property name lived only in metadata, not in the embedded text. I directed it to prepend the property name to each chunk before embedding (keeping the clean text stored separately for display) rather than relying on metadata alone. I also overrode the planned top-k of 4 → 5 after seeing that the chunk actually listing The Standard's pool and golf simulator ranked #5, just outside the cutoff. Both changes came from reading the real distance scores, not from accepting the first output.

**Instance 2 — Fixing the single-property retrieval failure (Failure Case Analysis)**

- *What I gave the AI:* I described the failure case from my evaluation: a question naming one property (*"Which amenities does The Standard at Tampa highlight?"*) was returning chunks from four different properties and missing The Standard's second chunk entirely. I asked the AI to make retrieval property-aware so a single-property question returns that property's complete set of chunks.
- *What it produced:* `detect_property()`, which recognizes when a query names exactly one known property (read from the indexed metadata), and an update to `retrieve()` that scopes the ChromaDB query with a metadata filter (`where={"property_name": ...}`) to return *all* of that property's chunks, falling back to plain top-k otherwise.
- *What I changed or overrode:* I directed it to fall back to ordinary top-k when the query names zero properties (a general question) or more than one (a comparison), so the scoping doesn't break those cases. I also rejected two alternatives it raised: raising the chunk-size target so the full list fits in one chunk (loses retrieval specificity) and applying a distance cutoff to drop off-source chunks (the other properties' amenity lists sit too close in distance — ~0.331 vs ~0.279 — to separate cleanly).
