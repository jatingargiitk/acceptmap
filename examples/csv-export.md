# Export the table as CSV

## Acceptance criteria

AC-1: The export starts with a header row of column names

AC-2: Values containing commas, quotes or newlines are escaped

**Scenario: empty table**

Given a table with no rows
When the user exports it
Then the download is an empty file
