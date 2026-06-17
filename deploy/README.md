# VPS Deployment (Hetzner CX23, Ubuntu)

The bot runs 24/7 on the `trading-bots` VPS as a systemd service.

## First-time setup

```bash
ssh root@167.233.126.228
git clone https://github.com/Urvish5500/OB-FVG-Bot.git
cd OB-FVG-Bot
apt install -y python3-venv python3-pip
python3 -m venv .venv
.venv/bin/pip install -r requirements-live.txt
# create .env with DATABASE_URL (copy from local: scp .env root@<ip>:/root/OB-FVG-Bot/.env)
cp deploy/ob-fvg-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ob-fvg-bot.service
```

## Monitoring

```bash
systemctl status ob-fvg-bot.service   # is it running?
tail -f /root/OB-FVG-Bot/bot.log       # live signal log
```

## Update after pushing new code

```bash
cd /root/OB-FVG-Bot && git pull && systemctl restart ob-fvg-bot.service
```
