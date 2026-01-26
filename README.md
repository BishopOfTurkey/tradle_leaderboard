

# Tradle Leaderboard


## Features
 - [x] Allow adding of a tradle score. Which will be pasted in by the user.
 - [x] Store the results somewhere. Using npoint.io (https://npoint.io) - free, permanent storage, simple REST API, no signup required.
 - [x] Only allow users who have a special code are allowed to submit scores. Use npoint ID as the secret - passed via URL parameter (e.g., `?id=abc123`), then stored in a cookie for future visits.
 - [x] Make the page look like the IEA.
 - [x] Display a leaderboard with multiple sortable metrics:
   - Average score (lower is better, X/6 counts as 7)
   - Total points (1/6=6pts, 2/6=5pts... 6/6=1pt, X/6=0pts)
   - Win rate (% of games solved)
   - Games played
   - Current streak
 - [x] Initialise the repo.
 - [x] Add another results table. Each row is a single round. Each column is a players name. Show each players result (e.g. 2/6) in the cells. Make it a new tab under the leaderboard heading.
 - [x] Make the table headers sticky when scrolling
 - [x] Vendor all external assets.

## Technology stack
 - Alpine JS
 - Python backend (see [BACKEND.md](BACKEND.md))
 - Use git for version control
 - Use uv for python packaging


## Style notes
 - Clean white background
 - Sans-serif typography (Inter or system fonts)
 - Large bold headings, dark gray body text
 - Accent colors: teal, purple, green (from IEA charts)
 - Card containers with subtle borders
 - Generous white space
 - Minimal, professional, data-focused aesthetic


Trade score examples:
#Tradle #1419 5/6
🟩⬜⬜⬜⬜
🟩🟩🟨⬜⬜
🟩🟩🟩🟩⬜
🟩🟩🟩🟩🟨
🟩🟩🟩🟩🟩
https://oec.world/en/games/tradle

#Tradle #1418 X/6
🟩⬜⬜⬜⬜
🟩🟩🟨⬜⬜
🟩🟩🟩🟩⬜
🟩🟩🟩🟩🟨
🟩🟩🟩🟩🟨
🟩🟩🟩🟩🟨

https://oec.world/en/games/tradle
#Tradle #1418 1/6
🟩🟩🟩🟩🟩

