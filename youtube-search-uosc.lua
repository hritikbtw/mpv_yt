-- youtube-search.lua
-- Search YouTube from within mpv and display results in the uosc menu.
local utils = require "mp.utils"
local msg   = require "mp.msg"
local input = require "mp.input"

-- Resolve the path to ytbackend.py relative to this script file.
local SCRIPT_DIR  = debug.getinfo(1, "S").source:match("^@?(.+/)") or "./"
local BACKEND     = utils.join_path(SCRIPT_DIR, "ytbackend.py")
local pending_cmd = nil

-- Parse one pipe-delimited line from backend: type|||id|||title|||channel|||date|||extra
local function parse_line(line, mode)
  local fields = {}
  for field in (line .. "|||"):gmatch("(.-)|||") do fields[#fields + 1] = field end
  if #fields < 6 or fields[2] == "" or fields[3] == "" then return nil end

  local url = fields[1] == "playlist" and "https://www.youtube.com/playlist?list=" .. fields[2] or "https://www.youtube.com/watch?v=" .. fields[2]
  local meta = {}
  for i = 4, 6 do if fields[i] ~= "" then meta[#meta + 1] = fields[i] end end

  return {
    title = fields[3],
    hint  = #meta > 0 and table.concat(meta, "  ·  ") or nil,
    value = { "loadfile", url, mode == "append" and "append-play" or "replace" }
  }
end

local function run_search(query, mode, deep)
  if not query or query == "" then return end
  if pending_cmd then mp.abort_async_command(pending_cmd) end

  local label = deep and "deep" or "quick"
  mp.osd_message("Searching YouTube (" .. label .. ")…", 30)

  local args = { BACKEND }
  if not deep then table.insert(args, "--no-continuation") end
  table.insert(args, query)

  local my_cmd
  my_cmd = mp.command_native_async({
    name = "subprocess", args = args, capture_stdout = true, capture_stderr = true, playback_only = false
  }, function(success, res, err)
    if pending_cmd == my_cmd then pending_cmd = nil; mp.osd_message("", 0) end
    if not success then return end

    if not res or res.status ~= 0 then
      msg.error("[yt-search] failed: " .. tostring(err or (res and res.status)))
      mp.osd_message("YouTube search failed", 3)
      return
    end

    local menu_items = {}
    for line in res.stdout:gmatch("[^\n]+") do
      local item = parse_line(line, mode)
      if item then table.insert(menu_items, item) end
    end

    if #menu_items == 0 then
      mp.osd_message("No results found", 3)
      return
    end

    local menu_data = {
      type = "youtube_search",
      title = string.format("Results for: %s (%s)", query, label),
      items = menu_items
    }

    mp.commandv("script-message-to", "uosc", "open-menu", utils.format_json(menu_data))
  end)
  pending_cmd = my_cmd
end

local function prompt_and_search(mode, deep)
  local prompt = "YouTube Search" .. (mode == "append" and " (add to playlist):" or (deep and " (deep):" or ":"))
  input.get({
    prompt       = prompt,
    history_path = utils.join_path(SCRIPT_DIR, ".yt-search-history"),
    submit       = function(query) run_search(query, mode, deep) end,
  })
end

mp.add_key_binding("Alt+y", "youtube-search-quick",  function() prompt_and_search("replace", false) end)
mp.add_key_binding("Alt+Y", "youtube-search-deep",   function() prompt_and_search("replace", true)  end)
mp.add_key_binding("Alt+a", "youtube-search-append", function() prompt_and_search("append",  false) end)
