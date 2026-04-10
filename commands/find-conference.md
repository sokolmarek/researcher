# /find-conference

Find relevant academic conferences for paper submission.

## Form Fields
- **topic** (text, required): Paper topic or research area
- **filters** (text, optional): Constraints like "deadline after June 2026", "CORE A*", "in Europe", "IEEE only"

## Behavior
1. Routes to conference-finder skill
2. Searches for conferences matching the topic
3. Applies deadline, ranking, location, and publisher filters
4. Returns list of conferences with: name, dates, location, deadline, ranking, acceptance rate, publisher
5. Highlights upcoming deadlines
