-- youtube-search.lua
-- Search YouTube from within mpv using the native input.select() UI.
local utils = require "mp.utils"
local msg   = require "mp.msg"
local input = require "mp.input"

-- Set console margins and font size on startup
local script_opts = mp.get_property_native("options/script-opts") or {}
script_opts["console-margin_x"], script_opts["console-margin_y"], script_opts["console-font_size"] = "15", "10", "24"
mp.set_property_native("options/script-opts", script_opts)

local SCRIPT_DIR  = debug.getinfo(1, "S").source:match("^@(.+/)") or "./"
local BACKEND     = utils.join_path(SCRIPT_DIR, "ytbackend.py")
local pending_cmd = nil

-- Parse one pipe-delimited line from backend: type|||id|||title|||channel|||date|||extra
local function parse_line(line)
  local fields = {}
  for field in (line .. "|||"):gmatch("(.-)|||") do fields[#fields + 1] = field end
  if #fields < 6 or fields[2] == "" or fields[3] == "" then return nil end

  local url = fields[1] == "playlist" and "https://www.youtube.com/playlist?list=" .. fields[2] or "https://www.youtube.com/watch?v=" .. fields[2]
  local meta = {}
  for i = 4, 6 do if fields[i] ~= "" then meta[#meta + 1] = fields[i] end end

  return {
    label = fields[3] .. (#meta > 0 and "  —  " .. table.concat(meta, "  · ") or ""),
    url = url
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

    local results = {}
    for line in res.stdout:gmatch("[^\n]+") do
      local item = parse_line(line)
      if item then table.insert(results, item) end
    end

    if #results == 0 then
      mp.osd_message("No results found", 3)
      return
    end

    local labels = {}
    for i, r in ipairs(results) do labels[i] = r.label end

    input.select({
      prompt  = "YouTube [" .. label .. "] " .. query .. " › ",
      items   = labels,
      submit  = function(idx)
        local url = results[idx].url
        msg.info("[yt-search] loading: " .. url)
        mp.commandv("loadfile", url, mode == "append" and "append-play" or "replace")
      end,
    })
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
