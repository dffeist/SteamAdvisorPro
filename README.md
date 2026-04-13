\# Steam Advisor Pro A1.2



\## Version A1.2

\*\* Added game folder size to the weighted value algorithm used to make game move recommendations.

\*\* Added a new button to the main table allowing the user to adjust the weighting used by the recommendations algorithm for Assigned Priority, Last Played, Time Played, and Game Size.



\## Version A1.1

\*\* Added a (Boot Drive) identify at the top of the table. If one of your drives containing steam games is your boot drive, (Boot Drive) will now be displayed.

\*\* Added Boot Available space as a percentage at the top of the table.  This is only displayed if one of your drives is a boot drive.

\*\* Added Boot Reserve space as a percentage at the top of the table.  Default minimum is 15%.  User can now increase this value if they wish to have more space reserved on their boot drive.  Steam Advisor Pro will not copy games onto the boot drive if the Boot Reserve disk space specified would be violated. If Boot Reserve becomes less than Boot Available due to other drive activity, Boot Reserve will be displayed in Red.

\*\* Fixed a bug that allowed Edit Priority values to be outside of the 1 to 5 range or non Integer values.



\## Overview

Steam Advisor Pro is a storage management utility designed to help you optimize your gaming experience by intelligently managing where your Steam games are installed. 



As games grow in size, managing limited SSD space becomes a chore. This program scans your Steam libraries across two different drives (typically a fast SSD and a large HDD) and uses a scoring algorithm based on your personal \*\*Priority\*\*, \*\*Recent Activity\*\*, and \*\*Total Playtime\*\* to recommend which games should be moved to faster storage and which can be safely archived to a mechanical drive.



To keep your previous configuration, copy the .json file from your most recent prior version and paste a copy into this folder along side the updated version.

\---



\## Getting Started (First-Time Use)



\### 1. Close Steam

\*\*Crucial:\*\* Steam must be completely closed before running this application. Steam Advisor Pro moves game files and manifest files directly; if Steam is running, it may lock these files or overwrite changes, leading to library corruption.



\### 2. Initial Configuration

When you launch the program for the first time, it will detect that no configuration exists and prompt you to initialize.

\*   \*\*Enable Steam API. This is needed if you plan to pull from steam the number of hours you have played each game. This is used to help with game drive recommendations. If this is left unchecked your Steam API will not be needed and the Hours Played will not be displayed in the generated Table.

\*   \*\*HDD/SSD Steam Paths:\*\* Browse to the root of your Steam library folders (e.g., `D:\\SteamLibrary`).

\*   \*\*Steam API Key (Optional but Recommended):\*\* To get accurate playtime data, you can provide a Steam Web API key. (https://steamcommunity.com/dev/apikey)

\*   \*\*SteamID64:\*\* Your unique 17-digit Steam ID. (https://store.steampowered.com/  Click on your Profile - 17 digits at the end of the URL)



\---

\## Top of Table

Display of current drive space used and available



\## Feature \& Button Guide



\### Top Control Bar

\*   \*\*Move Selected:\*\* After selecting one or more games in the table, click this to begin the transfer. The program confirms your target drive has enough space and moves the game folder and the `.acf` manifest file so Steam recognizes the new location immediately upon relaunch. Note, if the target drive is your boot drive the program will not move the game(s) if this move results in your boot having less than the recommended 15% free space. The program will display recommended game(s) on the target drive to be first moved to free up additional space.

\*   \*\*Get Recommendations:\*\* Opens a "Smart" window. 

&#x20;   \*   \*\*Promote to SSD:\*\* Lists games currently on your HDD that have high scores (played recently or marked as high priority).

&#x20;   \*   \*\*Demote to HDD:\*\* Lists games on your SSD that have low scores (rarely played or low priority).

\*   \*\*Edit Priority:\*\* Allows you to assign a value from 1 (Low) to 5 (High) to the selected games. This directly impacts the "Smart Score." Initial default setting is 3. Multiple rows may be selected by shift or CTRL and clicking on the row(s),click the Edit Priority button and assigned the same value to all selected rows.

\*   \*\*Refresh:\*\* Rescans your library manifests to reflect any changes made outside the app.

\*   \*\*Hide Not Installed:\*\* Filters the list to remove games that are in your library but have 0 bytes of data on your local drives. Note, this will only hide games that have file sizes scanned. See below 'Show All Sizes', and 'Game Sizes' for further details.

\*   \*\*Settings:\*\* Re-opens the configuration window to update paths or API credentials.



\### The Game Table (Clicking on a Column Header will resort the table)

\*   \*\*AppID:\*\* The unique Steam identifier for the game.

\*   \*\*Game Name:\*\* The title of the game.

\*   \*\*Drive:\*\* Shows if the game is currently on the \*\*HDD\*\* or \*\*SSD\*\*.

\*   \*\*Priority:\*\* Your custom 1-5 rating.

\*   \*\*Last Played:\*\* Pulled from local Steam data; shows the last time the game was launched.

\*   \*\*Playtime:\*\* Total hours played. If an asterisk `\*` is present, it is using local data. If the API is enabled, it uses live cloud data.

\*   \*\*Game Size:\*\*

&#x20;   \*   \*\*☐ Game Size (Header):\*\* Clicking the checkbox in the header will trigger a background scan of \*\*all\*\* game folders to calculate their actual size on disk.

&#x20;   \*   \*\*☐ / ☑ (Cell):\*\* Click the checkbox next to an individual game to scan only that folder. Once scanned, the size is cached in your config file. A `↻` symbol indicates the game has been updated on Steam since your last scan.



\### Scoring Logic

The "Smart Recommendation" score (0-100) is calculated as follows:

1\.  \*\*Priority (40%):\*\* How important you said the game is.

2\.  \*\*Recency (35%):\*\* How recently you played the game (weighted heavily for games played in the last 90 days).

3\.  \*\*Usage (25%):\*\* Total playtime compared to your most-played games.



\---



\## Safety Features

\*   \*\*Steam Running Check:\*\* The app will refuse to start if `steam.exe` is detected in your process list.

\*   \*\*Indeterminate Progress:\*\* When scanning large batches of folders, a popup will keep you informed of the progress.

\*   \*\*Atomic Moves:\*\* The move process copies files before deleting the source to prevent data loss. \*\*Do not quit the program while a copy process is running. An interrupted copying process may end up with an incomplete folder on your target drive while the original should continue to exist in your original folder. 



\---



\## Troubleshooting

\*   \*\*Config Not Found:\*\* The program looks for `steam\_advisor\_config.json` in its own folder. Ensure you have write permissions to that directory.

\*   \*\*API Errors:\*\* Ensure your API key is valid and your Steam Profile is set to "Public" so the program can see your playtime data.

```





