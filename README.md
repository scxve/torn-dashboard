# Torn City Raspberry Pi Dashboard

Torn Dashboard made to work on a Raspberry Pi when connected to a 800x480 display, running the latest version of Ubuntu Server.
Uses a Limited Access Torn API Key which displays the following information:
 - Username
 - Life, Energy, Nerve and Happy (number and bar)
 - Player Stats: Level, Status, Cash on hand, Points and Current Networth
 - Fund Stats: Bank Investment, Bank Investment Progress, Vault, Faction Vault, Daily NW and Time until full life
 - Chain/Cooldowns: Current Chain, Chain Timer, Chain Cooldown, Drug Cooldown, Booster Cooldown, Medical Cooldown and Travel Status
 - Alerts: Messages, Events and Awards
 - Time Until: Energy Full, Nerve Full and Drug Cooldown Ready

API Updates every 30 seconds, timers update every 1 second so it doesn't look clunky (updates locally rather than pulling from the API every second, does the initial pull then locally will count down)

The dashboard was designed and tested at 800×480. Higher-resolution displays should work, but you may need to adjust the Linux console font so the terminal provides enough columns and rows. The display should be set to its native HDMI resolution, and the dashboard should be run full-screen.



I did use AI to assist with this project :)

## API key

Create a **Limited Access** key in Torn. Limited access is required for the cash,
points, and net-worth fields. The key is sent only to `https://api.torn.com` in
the `Authorization` header and is kept in the local `.env` file.

## Install

Copy this folder to `/home/pi/torn-dashboard`, then run:

```bash
cd /home/pi/torn-dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env
chmod 600 .env
```

Replace `replace_with_your_key` with your Torn API key, then test it:

```bash
.venv/bin/python dashboard.py
```

Press `Ctrl+C` to exit.

Run the included offline checks with:

```bash
.venv/bin/python -m unittest -v test_dashboard.py
```

## Start automatically in the visible terminal

For a desk display, the simplest option is console autologin followed by a shell
startup command. Add this to the end of `/home/pi/.bash_profile`:

```bash
if [ "$(tty)" = "/dev/tty1" ]; then
    cd "$HOME/torn-dashboard" || exit 1
    exec .venv/bin/python dashboard.py
fi
```

Enable console autologin with `sudo raspi-config` under **System Options > Boot / Auto Login**.

## Display tuning

The API is polled every 30 seconds while all countdown timers advance locally
once per second, so cached Torn responses do not make timers jump in chunks.

The layout targets approximately 100 columns by 30 rows. If the bottom is cut
off, reduce the console font with:

```bash
sudo dpkg-reconfigure console-setup
```

Choose a Terminus font near 14 px, then reboot. The API interval cannot be set
below 30 seconds. On request failures the dashboard preserves the last good
data and gradually backs off to a maximum 60-second retry interval.

## Using SSH

Personally I used SSH and FTP via the program Terminus which I recommend you get if you decide to do the same.

Once you have uploaded the files to your Pi execute the following commands for testing prior to making the script boot on launch:

```bash
cd ~/torn-dashboard

sudo openvt -c 1 -f -s -- bash -lc "cd '$PWD' && exec '$PWD/.venv/bin/python' '$PWD/dashboard.py'"
```

This will launch the script to tty1 which is the physical display connected to the Pi rather than booting it in your SSH window, and to stop the dashboard via ssh enter the following:

```bash
sudo pkill -f 'dashboard.py'
```
