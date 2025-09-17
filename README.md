# CQC Monitor MultiServer Discord Bot

A Discord bot for monitoring Elite:Dangerous CQC squadrons activity and posting updates to multiple servers/channels. Supports slash commands on discord and Docker deployment.

## Features
- Fetches CQC activity from https://sapi.demb.uk/api/leaderboard/cqc/platform/pc and posts updates as Discord embeds
- Discord Slash commands support
- Multi-server/channel support
- Graceful server/channel removal handling
- Docker and Docker Compose support

## Add CQC Monitor to your server

To add CQC Monitor to your server, click this [link](https://discord.com/oauth2/authorize?client_id=1414630165706706974&permissions=2147568640&integration_type=0&scope=bot)

On Discord, select which server you want the bot to be added to. After confirming, the bot will be added and you can interact with it via the slash commands.

## Own Setup

### Clone the repository
```sh
git clone https://github.com/heliaxx/cqc_monitor.git
cd cqc_monitor
```

### Configure the bot
1. Create a Discord application and get your bot's token on https://discord.com/developers/applications

2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Add your discord bot token to `.env`:
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   ```
### Run the bot using Docker Compose
- Ensure Docker is installed on your system: https://www.docker.com/products/docker-desktop/
- Use the provided `docker-compose.yml` file to start the bot:
    ```sh
    docker-compose up
    ```
- To run the bot in detached mode:
    ```sh
    docker-compose up -d
    ```
- To stop the bot:
    ```sh
    docker-compose down
    ```

## Slash Commands
The bot supports the following Discord slash commands:

- `/cqc_status` — Show current CQC bot status and statistics. (Admin only)
    - Displays the bot's operational status and server statistics.

- `/cqc_channel [#channel]` — Set the channel for sending CQC notifications. (Admin only)

- `/cqc_this_channel` — Set the current channel as the CQC notification channel. (Admin only)

- `/cqc_enable` — Turns on CQC activity notifications for the server. (Admin only)

- `/cqc_disable` — Turns off CQC activity notifications for the server. (Admin only)

- `/cqc_info` — Provides information about the CQC game mode in Elite Dangerous.

- `/cqc_bugs` — Provides tips and workarounds for common CQC bugs.

- `/cqc_help` — Lists all available commands and their descriptions.

## License
[Unlicense](./UNLICENSE) 
---

**Made by:** [Heliaxx](https://github.com/heliaxx)

With any inquiries, contact @heliaxx on Discord.