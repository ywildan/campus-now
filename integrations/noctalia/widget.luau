--!nonstrict
-- Campus Now bar widget: reads next-class.sh JSON output and displays
-- the current/next class info in the bar with a tooltip.
--
-- Requires: next-class.sh (from ~/Projects/campus-now/scripts/)
-- Refreshes every 60 seconds.
-- Click opens http://localhost:8888

local SCRIPT = noctalia.expandPath("~/Projects/campus-now/scripts/next-class.sh")
local DASHBOARD_URL = "http://localhost:8888"

local function fetchAndRender()
  -- String form: array form of runAsync requires plugin_api 24; we target 9.
  noctalia.runAsync("bash " .. SCRIPT, function(result)
    if result.exitCode ~= 0 then
      barWidget.setText("! class")
      barWidget.setTooltip("Campus Now: script failed\n" .. (result.stderr or ""))
      return
    end

    local data, err = noctalia.json.decode(result.stdout)
    if not data then
      barWidget.setText("! parse")
      barWidget.setTooltip("Campus Now: JSON error\n" .. (err or "unknown"))
      return
    end

    barWidget.setText(data.text or "—")
    barWidget.setTooltip(data.tooltip or "No class info")
  end)
end

function update()
  noctalia.setUpdateInterval(60000)
  fetchAndRender()
end

function onClick()
  noctalia.runAsync({ "xdg-open", DASHBOARD_URL })
end
