# Playbook: script writer ("remix")

Goal: a new script on the user's own topic that borrows the *structure* of a reference video,
never its wording. Work in two passes. Do not skip the first.

## Pass 1: analyze the reference
Read the reference with `get_transcript` (timestamps on, stats on). Extract and show briefly:
- **Hook**: what happens in the first 3 seconds and which archetype it is.
- **Setup**: how the problem or tension is established.
- **Value points**: each beat, with its approximate timestamp.
- **Payoff**: where the promise of the hook is delivered.
- **CTA**: what the viewer is asked to do, and when.
- **Pacing**: words per minute (word count ÷ duration) and average beat length.

## Pass 2: write the new script
- Topic, niche and voice come from the user. Ask if the topic is missing.
- Keep the same beat order and roughly the same duration. Target word count =
  reference duration in minutes × reference words per minute (about 150 wpm if unknown).
- Every sentence must be new. Different examples, different phrasing, the user's own point of view.
- Write for the ear: short sentences, concrete nouns, no filler openers.

## Output
A table or list of beats. For each beat: time range, spoken line(s), on-screen text suggestion,
b-roll or visual suggestion. Then the full spoken script as one block for a teleprompter, with the
word count and estimated duration.

## Check (required)
Call `check_originality` with the full spoken script and the reference transcript id.
- `original`: report the overlap figure and finish.
- `borrowed` or `too_similar`: rewrite the phrases listed in `copied_phrases`, then check again.
Tell the user the final overlap figure. Remind them once that the script must not copy another
creator's work and that they are responsible for what they publish.
