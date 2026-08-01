
# Release Process Reminder
After bumping a version and pushing the release updates to GitHub, ALWAYS remind the user to check the tool's built-in updating system to ensure it correctly detects the new version.


# GitHub API Requests
When making API requests to GitHub to create releases with emojis, NEVER use PowerShell `Invoke-RestMethod` as it causes UTF-8 encoding corruption (turns emojis into '?'). ALWAYS use a Python script with `json.dumps().encode('utf-8')`.

# GitHub Release Styling
When releasing a new version, make sure the title and the release notes are stylish. Using Emojis and everything. Always remember to release versions with a cool, unique Release title and Release Notes.
Eg Title : ✨ v4.8.0 - Massive Feature Update: Analytics & AniSkip
Eg Release Notes:
### 🚀 What's New in v4.8.0!
We've added a ton of highly requested features to make your anime tracking experience even better.
#### 📊 Your Anime Wrap (Analytics)
- **New Dashboard Tab**: View your total hours watched, unique titles, and today's stats.
- **Activity Graph**: A beautiful 7-day bar chart of your watch history.
- **Top Titles**: See which anime you've spent the most time on!
#### ⏭️ AniSkip Integration
- **Auto-Skip**: Automatically jump over Openings (OP) and Endings (ED).
- **Smart Detection**: Only skips if you're watching the correct episode based on AniList data.
#### ⭐ Auto-Score Popups
- Automatically prompts you to rate a series the moment you finish the final episode.
- **Custom Rating Formats**: Automatically matches your AniList preference.
#### 🍎 UI Enhancements
- **macOS-Style Toasts**: Replaced standard logs with sleek, animated dark-mode toast notifications!
### 🔧 Fixes & Tweaks
- Added new preferences toggles for Auto-Skip and Auto-Score.
- System Tray integration improvements.

Enjoy the new update! 🎉
