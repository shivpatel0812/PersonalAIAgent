"""LLM system prompts for the Find feature."""

EXTRACT_REQUEST_SYSTEM = """You help users find products, services, places, travel, clothing, or anything else.

Given the full conversation, produce a JSON object with exactly these fields:

{
  "subject": "<what the person is looking for, in their words, 1 short phrase>",
  "constraints": { "<key>": <value>, ... },
  "status": "ready" | "needs_clarification",
  "missing": ["<human-readable gap>", ...],
  "clarifying_question": "<one conversational question>" | null
}

Rules:
- Infer constraints ONLY from what the user said or clearly implied. Use whatever keys fit THIS request (budget, size, dates, style, location, material, brand, etc.). Do not use a fixed schema.
- "ready" means you could run a useful web search right now without guessing critical details the user would care about.
- "needs_clarification" when one missing detail would materially change search results. List gaps in "missing".
- When needs_clarification, ask exactly ONE question in "clarifying_question". Make it conversational, not a form. Set clarifying_question to null when ready.
- Fold every prior user and assistant message into subject and constraints. Latest message wins on conflicts.
- Do not classify into domains (no "flights", "shopping", etc.). Describe the subject plainly.
- Reply with valid JSON only. No markdown."""

BUILD_QUERY_SYSTEM = """Turn a structured find request into one web search query string optimized for finding purchasable items, bookable services, or actionable options.

Input JSON:
{ "subject": "...", "constraints": { ... } }

Output JSON:
{ "query": "<single search query, 5-15 words, no quotes>" }

Rules:
- Include subject and the most important constraints as natural language
- Append ONE action word at the end to steer toward actionable pages:
  - For physical products: "price"
  - For services: "book"
  - For places: "visit"
- Do NOT stack multiple shopping keywords (no "buy shop price purchase")
- Include brand names, specific models, or unique identifiers when mentioned
- Include size, color, material when specified
- For budget constraints, always include the price/budget in the query
- Avoid generic terms: "best", "top 10", "guide", "how to", "review"
- Make queries sound like shopping searches, not research queries
- Do not invent constraints not in the input
- Reply with valid JSON only

Examples:
Request: {subject: "mens polo shirt", constraints: {style: "professional", budget: "under $50", size: "medium"}}
Query: "mens polo shirt medium professional under $50 price"

Request: {subject: "water bottle", constraints: {}}
Query: "water bottle price"

Request: {subject: "water bottle", constraints: {budget: "under $40"}}
Query: "water bottle under $40 price"

Request: {subject: "ergonomic office chair", constraints: {budget: "$200-400", feature: "lumbar support"}}
Query: "ergonomic office chair lumbar support $200-400 price"

Request: {subject: "sushi restaurant", constraints: {location: "San Francisco", rating: "4+ stars"}}
Query: "sushi restaurant San Francisco 4 stars book"

Request: {subject: "Hydro Flask water bottle", constraints: {size: "32 oz"}}
Query: "Hydro Flask 32 oz water bottle price\""""

REFINE_SYSTEM = """The user was shown numbered search results for a find request. They reacted. Update the request and produce a new search query.

Input JSON:
{
  "request": { "subject": "...", "constraints": {...} },
  "results": [
    {"index": 1, "title": "...", "snippet": "...", "url": "..."},
    ...
  ],
  "user_feedback": "<their message>",
  "feedback_meta": { "type": "thumb", "index": 3, "value": "up" } | { "type": "refine", "ratings": [...] } | null,
  "preference_history": {
    "liked": ["stainless steel", "32oz", "CamelBak"],
    "disliked": ["plastic", "generic brand"],
    "all_ratings_summary": "5 total ratings across 2 rounds"
  } | null
}

Output JSON:
{
  "request": { "subject": "...", "constraints": {...}, "status": "ready", "missing": [], "clarifying_question": null },
  "query": "<new Tavily search query>",
  "assistant_message": "<optional 1-sentence acknowledgment>"
}

Rules:
- Interpret feedback naturally: "cheaper" → lower budget; "more like #3" → extract attributes from result 3 into constraints; "stainless steel" → add constraint.
- Thumb up on #N: note preferred attributes from that result in constraints.
- Thumb down on #N: note what to avoid if inferable.
- Batch ratings (type: "refine"): Multiple thumbs up/down provided at once.
  - Find common attributes across liked results (brand, price range, style, features).
  - Identify what to exclude from disliked results (certain brands, price points, styles).
  - Positive signals override negative when updating constraints.
- Use preference_history to avoid repeating disliked patterns and lean into liked ones.
- Preference patterns from earlier rounds are weaker signals than the latest ratings.
- Always set status to "ready". Do not ask clarifying questions.
- Append ONE action word at the end of the query: "price" for products, "book" for services, "visit" for places. Do NOT stack multiple shopping keywords.
- If feedback is ambiguous, make a reasonable assumption and say so in assistant_message.
- Reply with valid JSON only."""

REFINE_QUERY_SYSTEM = """You help refine vague product searches into specific, searchable products.

Given a search request, determine if it's generic/vague or specific:
- GENERIC: "water bottle", "running shoes", "laptop" (no brand, no model)
- SPECIFIC: "Hydro Flask 32oz", "Nike Pegasus 41", "MacBook Pro M3"

If GENERIC, suggest 2-3 specific, well-regarded products that match the request.
If SPECIFIC, return it unchanged.

Input JSON:
{
  "subject": "water bottle",
  "constraints": {"budget": "under $40"}
}

Output JSON for GENERIC query:
{
  "is_generic": true,
  "suggested_products": [
    "Hydro Flask 32oz Wide Mouth water bottle",
    "Stanley Quencher 40oz tumbler"
  ],
  "reasoning": "Generic category query - suggesting popular, well-reviewed options"
}

Output JSON for SPECIFIC query:
{
  "is_generic": false,
  "original_query": "Hydro Flask 32oz Wide Mouth",
  "reasoning": "Already specific - includes brand and model"
}

Rules:
- Only suggest real, well-known products (not made up)
- Consider constraints (budget, size, etc.) when suggesting
- Prefer products with strong reviews/reputation
- For electronics/tech, suggest current generation products
- Keep suggestions to 2-3 products max
- Reply with valid JSON only"""

FILTER_RESULTS_SYSTEM = """You are evaluating web search results for relevance and specificity.

Given a user's search request and a list of results, identify which results should be KEPT vs DROPPED.

DROP a result if it meets ANY of these criteria:

1. **Wrong item type** — Result is clearly not the product/service/thing type requested
   Example: Request is "polo shirt" but result is pants or shoes (not similar apparel)
   Note: Similar items are OK (e.g., t-shirt for polo shirt request if specific product)

2. **Catalog/category page** — Result shows multiple items instead of one specific offering

   **URL Catalog Patterns** (strong signal, verify with title before dropping):
   - /category/, /categories/, /c/, /collections/, /collection/
   - /shop/, /browse/, /search/, /filter/, /all-
   - catpage-, cat-, category-, collection- (in path or filename)
   - -catalog, -shop, -store, -list, -browse (in path)
   - /s/, /w/, /m/, /p/ when part of generic category structure (e.g., /w/womens-shoes/)

   Supporting Title/Content Signals (strengthen decision):
   - Title: Plural generic terms ("Men's Shirts", "Water Bottles"), "Collection", "Shop All"
   - Content: "browse our selection", "filter by", "sort by", "X items", "showing Y results"

   **IMPORTANT**: If URL contains catalog patterns AND title/content confirms it is a listing page, DROP. If the title looks like a specific product despite the URL pattern, KEEP.

3. **Article/guide/blog/listicle** — Editorial content, not a purchasable item
   URL Signals:
   - Contains: /blog/, /article/, /guide/, /review/, /reviews/, /how-to/
   - Contains: /best-, -best-, /top-, -top-
   - Domain is known content site: reddit.com, quora.com, medium.com

   Title Signals:
   - Starts with: "Best", "Top 10", "How to", "Review:", "Guide to"
   - Contains: "vs", "comparison", "roundup"

4. **Completely irrelevant** — No meaningful connection to the request
   Example: Request is "water bottle" but result is about water delivery service

KEEP a result if:
- Reasonably matches the requested item type (or very similar)
- Appears to be a specific single product/service/offering
- URL suggests detail page: /p/, /product/, /dp/, /item/, /pd/, or brand/model identifier
- Title is specific: includes brand name, model name, or specific identifiers
- Even if not perfect match, represents a specific purchasable item
- **When in doubt, KEEP** - better to show a potentially useful result than nothing

Respond with JSON:
{
  "filtered": [
    {
      "index": 0,
      "keep": true,
      "reason": "Specific product page - Nike Zoom Fly with price and model details"
    },
    {
      "index": 1,
      "keep": false,
      "reason": "Catalog page - URL contains 'catpage' and title shows generic 'Running Shoes' collection"
    }
  ]
}

**Evaluation Order**:
1. Check URL for catalog patterns — if found, check title to confirm it's a listing page before dropping
2. Check if article/blog/listicle by URL → DROP
3. Check if wrong item type → DROP if clearly different
4. If passes above, KEEP even if title/content seems generic

Balance: When in doubt, KEEP — better to show a potentially useful result than nothing. Prefer keeping specific product pages even if not perfect match over showing catalog/article pages."""

EXTRACT_PREFERENCES_SYSTEM = """Given a history of user ratings on search results, extract preference patterns.

Input: list of rated results with "up"/"down" values across multiple rounds.

Output JSON:
{
  "liked_attributes": ["stainless steel", "32oz size", "under $30", "CamelBak brand"],
  "disliked_attributes": ["plastic", "generic brand", "over $50"],
  "summary": "User prefers stainless steel water bottles from name brands, 32oz, under $30"
}

Rules:
- Only extract patterns with 2+ supporting signals (don't over-index on single ratings)
- Include: material, brand, price range, size, style, features
- Be concise — each attribute should be 1-4 words
- Reply with valid JSON only"""
