# Torn City Raspberry Pi Dashboard

A full-screen Rich terminal dashboard designed for a Raspberry Pi 3B and an
800x480 display. It shows live life, energy, nerve, happiness, profile, money,
net worth, chain, cooldown, and travel data from Torn API v2.
The expanded overview also includes city-bank value and maturity, vault and
faction balances, daily net worth, recovery timers, chain and medical cooldowns,
and unread message, event, award, and competition counts.

Colours use the Linux console's native 16-colour ANSI palette so life (blue),
energy (green), nerve (red), and happy (yellow) remain distinct on tty1.
The middle panels use white for ordinary values, green for healthy/ready states,
yellow for active timers or alerts, and grey for inactive zeroes.

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
  cd /home/pi/torn-dashboard
  exec .venv/bin/python dashboard.py
fi
```

Enable console autologin with `sudo raspi-config` under **System Options > Boot / Auto Login**.

The included `torn-dashboard.service` is an alternative background service, but
a normal system service does not automatically draw onto the physical TTY. The
console-autologin method above is recommended for the attached screen.

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
