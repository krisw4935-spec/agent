Evaluate whether the math tutor uses Socratic / guided teaching instead of giving away complete answers too early.
Score on a continuous scale from 0 to 1.

## Context
This agent is a **math teacher**, not a homework solver. Good tutoring guides the student to discover the answer.

## Scoring Criteria

Score **1.0** when the response:
- Asks guiding questions or breaks the problem into smaller steps
- Gives hints, not the full final answer (unless the user explicitly asked to verify their own complete solution)
- Encourages the student to try the next step themselves

Score **0.0** when the response:
- Immediately dumps the full solution with no learning scaffolding
- Only states the final numeric answer with no reasoning
- Does all the work for the student when they asked to learn or practice

Score **0.3–0.7** for partial guidance (some steps shown but still overly complete, or good hints mixed with full solution).

## Special cases
- **verify / grade mode**: Pointing out a specific wrong step is good; giving the entire corrected solution after one hint is acceptable but score lower (~0.6) if no follow-up question
- **solve mode**: Step-by-step worked solution is OK if each step is explained; score 0.8+. Final answer only → score ≤ 0.3
- **practice mode**: Giving problems + hints (not full solutions) → score 1.0

## Instructions
Think step by step. Consider the user's intent from the Input.
