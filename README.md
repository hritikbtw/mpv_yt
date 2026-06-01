Search and play YouTube videos inside mpv using the native selection UI.

## Requirements
* yt-dlp (not used for search, but for playing)

## Installation

**For Vanilla mpv**

Place [youtube-search.lua](youtube-search.lua) and [ytbackend.py](ytbackend.py) in `~/.config/mpv/scripts/`.

**If You are using [uosc](https://github.com/tomasklaen/uosc)**

Place [youtube-search-uosc.lua](youtube-search-uosc.lua) and [youtube-search.lua](youtube-search.lua) in `~/.config/mpv/scripts/`.

> [!NOTE]
> Don't Place both `youtube-search-uosc.lua` and `ytbackend.py` in your $HOME/.config/scripts


## Keybinds
* `Alt+y` - Quick search, faster, less results
* `Alt+Shift+y` - Deep search, takes more time, ~50 results (configurable)
* `Alt+a` - Append to playlist


## Screenshots

**Default mpv**

<img src="https://github.com/user-attachments/assets/6e6f2004-47cd-41b0-b9e5-de77a86db988" width="79%" alt="search" />
<img src="https://github.com/user-attachments/assets/43ad322c-617e-438c-b0ee-b97e488a0311" width="79%" alt="vanilla results menu" />

**Mpv with uosc**

<img width="79%" alt="vanilla results menu" src="https://github.com/user-attachments/assets/2a8e345f-f61b-4e3d-88bc-cfa6e7179669" />
