---
name: plan80-why
description: Explain why Plan80 made a scheduling decision, such as why a block was dropped, why a week is short on hours, or what the rule is for overload, sick days, deadlines, calendar privacy or capacity. Answers from the user's own planning rules. Use when the user asks why something was dropped or moved, what the rule is, or how many hours they can plan.
---

# Plan80: explain a decision

Answer from the planning rules, not from memory. The retrieval script finds the matching
section of the rules and the PRD. Quote it, cite it, and keep the answer short.

Plugin folder: `${CLAUDE_PLUGIN_ROOT}`. If that variable isn't set, use the folder that
contains this skill's `scripts/` directory (two levels above this skill).

## Steps

1. Turn the user's question into a plain question and retrieve the top sections:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rag.py" "<the user's question>" -k 3
   ```
2. If the question is about a specific block, also read `~/Plan80/plan.json`, look at the
   `dropped` list, and quote the reason for that block.
3. Answer in three parts:
   - **The decision:** what happened, in one sentence.
   - **The rule:** quote the most relevant line, and cite the section heading.
   - **The option:** if the user wants a different result, say what would have to change
     (a priority, a block time, a sick day) and whether that means dropping something
     of higher priority.

## Rules for answering

- If retrieval finds nothing relevant, say so. Don't invent a rule.
- Never move health below another goal in an explanation. Health is tier 1 by the
  user's choice.
- If the user asks to change a priority or a target, don't change it from this skill. Ask
  them to confirm, then edit `~/Plan80/life.json` and regenerate.
