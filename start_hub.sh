#!/data/data/com.termux/files/usr/bin/bash
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

pkill -f "tengen_sampler.py|hub_watchdog.py|crown_hud.py" 2>/dev/null
sleep 1

nohup python3 ~/tengen_sampler.py > ~/sampler.log 2>&1 &
sleep 1
nohup python3 ~/hub_watchdog.py > ~/watchdog.log 2>&1 &
nohup python3 ~/crown_hud.py > ~/hud.log 2>&1 &
sleep 2

echo "=== OMA2 LEGION HUB // ACTIVE DAEMONS ==="
pgrep -af "tengen_sampler|hub_watchdog|crown_hud"
echo "=== HUD ONLINE: http://127.0.0.1:8088 ==="
