# Steam Advisor Pro - Release vA1.2

## 🚀 Overview
This update refines the recommendation engine by standardizing the weighting system and improving the initial configuration experience. The scoring logic is now more intuitive and balanced by default.

### ✨ Key Changes

- **Standardized Weighting Scale**: 
  - All 4 weighting measures (Priority, Recency, Playtime, and Size) now use a consistent **1 to 5** range.
  - Removed redundant range descriptors from the UI for a cleaner look.
  
- **Balanced Defaults**: 
  - New installations now default to a weighting of **3** for all measures.
  - If no configuration is found, these defaults are automatically generated and saved to your `steam_advisor_config.json`.

- **Dynamic Scoring Thresholds**: 
  - The recommendation logic now calculates "Promote" and "Demote" thresholds dynamically based on the total sum of your current weights, ensuring recommendations stay accurate regardless of your custom settings.

### 🛠️ Technical Fixes
- Improved persistence logic to ensure weight settings are correctly recorded during the initial setup wizard.
- Updated the internal configuration dictionary to include the `weights` key by default.

---

## 📦 How to Update
1. Ensure **Steam is closed**.
2. Replace your current `SteamAdvisorPro.py` with the updated version.
3. Your existing configuration will be automatically updated with the new 1-5 weighting scale upon launch.

---

## ⚠️ Reminder
The `steam_advisor_config.json` file contains your private Steam API Key and SteamID. This file is now included in the `.gitignore` to prevent accidental uploads to GitHub. 

**Do not share your config file publicly.**

*Happy Gaming!*