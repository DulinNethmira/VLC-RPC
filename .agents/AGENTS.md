
# Release Process Reminder
After bumping a version and pushing the release updates to GitHub, ALWAYS remind the user to check the tool's built-in updating system to ensure it correctly detects the new version.


# GitHub API Requests
When making API requests to GitHub to create releases with emojis, NEVER use PowerShell `Invoke-RestMethod` as it causes UTF-8 encoding corruption (turns emojis into '?'). ALWAYS use a Python script with `json.dumps().encode('utf-8')`.
