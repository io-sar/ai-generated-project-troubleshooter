---
id: repair
version: v1
written_for: [claude-haiku-5-5]
eval_cases: none yet (M8)
---
## Repairing your previous answer

Your previous answer didn't match the required format. It is between `<previous_answer>`
tags, and each problem is listed between `<validation_errors>` tags, one per line, as a
field path and what is wrong with it.

Fix every listed problem and answer again with the complete, corrected JSON object. Keep
everything that was already correct. Don't add fields the schema doesn't ask for.

If no previous answer is shown, your last answer wasn't a valid JSON object at all. Answer
again with one JSON object that matches the schema.
