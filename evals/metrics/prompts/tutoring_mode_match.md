Evaluate whether the tutor response matches the **expected tutoring mode** (explain / verify / practice / solve).
Score on a continuous scale from 0 to 1.

## Mode expectations

| User intent (from Input) | Expected behavior |
|--------------------------|-------------------|
| Explain concept (什么是, 为什么, 讲解) | Concept explanation, examples, no full unrelated problem solution |
| Verify student work (我的解答, 批改, 检查) | Feedback on student's steps, error diagnosis |
| Practice (出题, 练习, 再来一题) | New problem(s) + hints, **not** full solutions upfront |
| Solve problem (解方程, 求, 计算) | Step-by-step solution with reasoning |

## Scoring

Score **1.0**: Response clearly fits the user's intent and mode.

Score **0.0**: Completely wrong mode (e.g. user asked for practice problems but got a lecture; user submitted work for grading but tutor ignored it and solved fresh).

Score **0.5–0.7**: Partial match (correct direction but mixed modes, e.g. explain + full solve when only explain was needed).

## Instructions
Think step by step. Infer intent from the Input messages.
