To create a seamless humanlike long term memory for an llm across serial conversation. Not a rag on a pre-existing dataset. It is intended that the system be invisible to the user, and require no tool use or other changed behavior from the Assistant.

"Assistant" is the llm talking to the user.

"Archivists" are separate llms doing memory tasks. The Assistant does not see Archivist chats, though changes the Archivists make will affect future Context given to the Assistant.


# Knowledge Base structure

KeyInfoSummary (potentially redundant given relevance and importance filtering of other context. Failsafe.)
- A length capped summary of everything the llm should know at all times

ContextItem (base class for anything that can be presented as context)
- usefulness score. Item is periodically reviewed if it was used when it was supplied. Score increases and decreases cumulatively.

Messages (straight from the chat)
- body
- sender
- associated Facts
- associated Entities
- containing Summary
- time sent

MessageSummary (condensed paraphrasing of a block of memories. Summaries can have any number of levels of compression. A Summary1 is a summary of raw data. A Summary2 is a summary of Summary1s. This intentionally puts more weight on more recent additions, like how long term memory fades.)
- text body
- contained Messages
- containing Summary

Entities (anything you might make into a wiki page)
- aliases
- Brief, a ~2 sentence summary
- if many facts, a EntityFactSummary (Dossier?). Facts not in the summary are presented normally in addition.
- Facts tagged with this Entity

EntityFactSummary
- A length capped summary of an entity's current Facts for cheaper presentation to the Assistant.
- summarized Facts

Facts (statements in memory)
- ~1 sentence body
- list of related Entities
- time created, time last updated
- 1-10 strategic importance
- 1-10 emotional salience

Questions (known unknowns, subtype of Fact)

Objectives (terminal or belonging to a terminal objective, subtype of Fact)
- owning Objective?

Theories (speculative facts, subtype of Fact)
- evidence Facts

# Context presentation

Whenever it is the Assistant's turn to answer, the memory system prepends context to the chat history, as described below.
The Context is only available for that message turn. In future message turns it will be replaced with a new Context. The LLM's visible message history may be shortened because MessageSummaries are provided for efficiency.

Input:
- A recent block of n messages
- The previous context (Context weights towards being similar to recent context so the Assistant's behavior shifts gradually rather than erratically)


For each message, the Assistant llm is given a body of Context including
- Key Info
- MessageSummaries covering periods not in the visible chat history
- All facts, fact subtypes, entity summaries, and low level messages/message summaries are ranked by relevance, usefulness, importance, and salience. These can each be weighted with training to predict likelihood that the Item is later given a positive Usefulness score. Possibly prefer related items for a more cohesive picture. Prefer context included recently. Prefer not including redundant items such as a fact already contained in a visible summary, though it is sometimes appropriate.

Order as
- Key info
- Message summaries, starting from most long scale to most recent.
- Relevant EntityFactSummaries
- Less relevant Entity Briefs
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