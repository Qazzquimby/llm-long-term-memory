To create a seamless humanlike long term memory for an llm across serial conversation. Not a rag on a pre-existing dataset. It is intended that the system be invisible to the user, and require no tool use or other changed behavior from the Assistant.

"Assistant" is the llm talking to the user.

"Archivists" are separate llms doing memory tasks. The Assistant does not see Archivist chats, though changes the Archivists make will affect future Context given to the Assistant.


# Knowledge Base structure

ContextItem (base class for anything that can be presented as context)
- usefulness score. Item is periodically reviewed if it was used when it was supplied. Score increases and decreases cumulatively.
- qualitative strategic importance
- time created, time last updated
- retired_by, ContextItem, for use when merged into another item. If not null, this item should not be used.

MessageSummary (Subclass of ContextItem. A condensed paraphrasing of a block of memories. Summaries are later merged and condensed futher as they grow old)
- body
- related Facts
- related Entities

Entities (anything you might make into a wiki page. Not contextItems as they behave more like tags. Brought up when relevant to sufficient other context)
- aliases
- Brief, a ~2 sentence summary
- Facts tagged with this Entity
- MessageSummaries related to this Entity 

Facts (statements in memory)
- ~1 sentence body
- list of related Entities
- Supported Theories

## Possible later fact subtypes
Key issue here is temporary facts need to be properly updated or they become misinformation.

Questions (known unknowns, subtype of Fact)
- possible theories

Theories (speculative facts, subtype of Fact)
- evidence Facts
- relevant question

Objectives (terminal or belonging to a terminal objective, subtype of Fact)
- parent objective?
- child objective



# Context presentation

Whenever it is the Assistant's turn to answer, the memory system prepends context to the chat history, as described below.
The Context is only available for that message turn. In future message turns it will be replaced with a new Context. The LLM's visible message history may be shortened because MessageSummaries are provided for efficiency.

Input to fetch context:
- A recent block of n messages
- ? The previous context (Context weights towards being similar to recent context so the Assistant's behavior shifts gradually rather than erratically)

For each message, the Assistant llm is given a body of Context including
- Key Info
- MessageSummaries covering periods not in the visible chat history
- All facts, fact subtypes, entity summaries, and low level messages/message summaries are ranked by relevance, usefulness, importance, and salience. These can each be weighted with training to predict likelihood that the Item is later given a positive Usefulness score. Possibly prefer related items for a more cohesive picture. Prefer context included recently. Prefer not including redundant items such as a fact already contained in a visible summary, though it is sometimes appropriate.

Order as
- Relevant entity briefs
- Message summaries, starting from most long scale to most recent.
- Most relevant
	- Facts
	- Theories
	- Questions
	- Objectives
- Most recent message history

? Prior to presenting the Context, an Archivist could pick out items it deems irrelevant to remove. Those items are marked as unhelpful for the round. This doesn't save tokens (it spends more tokens on additional processing), but could possible improve Assistant performance with less noise. Could instead be useful earlier on while ranking.

When the Assistant tries to talk about something not well covered in context, they have a high risk of saying something stupid (due to being uninformed) or hallucinating detail.
As a possible solution:
- read the Assistant's new message. Fetch content relevant to the new message and quantify the amount of topic drift.
- If high, have an Archivist determine if the Assistant's message is underinformed or hallucinating given the new context. (Could possibly skip this step and always guess "yes" when the context difference is high)
- If yes, provide the new context and regenerate the Assistant's message.
This is time expensive because it cannot be done in parallel. It also requires a second Context Fetching step to be performed for each message. Look for a way to make this sufficiently efficient before implementing.

# Consolidation

Periodically, every 10 messages or so, Consolidate Memories, maintaining the Knowledge Base. There are many potential steps in Consolidation, but most only happen occasionally or when deemed needed.
Look at the messages the window, and some windows prior to it for context.

Consolidation happens asynchronously, parallel to the main chat, so there's no disruption

Maintenance, many doable in parallel
- Look at all context Items recently presented to the Assistant. Judge for each if it was relevant and useful. Update the Item's usefulness score up or down.
- Add new Facts present in the recent window that are not present in the context. Facts should be statements about the world, not event history. Hopefully trivial facts do not clog up the system due to the filtering systems in place.
	- Do the same for theories, questions, objectives
- Ask if any facts appear to be duplicates, and merge, or made out of date and updated. Update upstream summaries. 
- Ask if any entities listed appear to be duplicates, and merge, creating an alias, adjust fact tags
- If the total length of an entity's fact list is too long, produce an EntityFactSummary
- If the total length of MessageSummaries is too long, compress newer summaries into older summaries, keeping length limits.


# TODO

- add basic context ranking
- train weighted context ranking

- Handle rabbitholing. Higher level llm working off of summaries to notice?
- and or encourage llm giving up. Track importance of objective and how much has been spent on it. Objective tree?
- Temporary facts need a tracking system to avoid out of date information. Hopefully partly handled by consolidation updating facts.
- Run on vending benchmark