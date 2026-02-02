import os
import discord
import aiohttp
import asyncio
import datetime
import json
from dotenv import load_dotenv
from discord.ext import commands
import sys

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN not found!")
    sys.exit(1)

print("Bot token loaded.")

LEADERBOARD_URL = "https://sapi.demb.uk/api/leaderboard/cqc/platform/pc"
DIFF_URL = "https://sapi.demb.uk/api/diff/{action_id}"

class ServerDatabase:
    def __init__(self, db_file='servers.json'):
        self.db_file = db_file
        self.load_database()
    
    def load_database(self):
        try:
            with open(self.db_file, 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {'servers': {}}
            self.save_database()
    
    def save_database(self):
        with open(self.db_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_server(self, guild_id, channel_id, guild_name=None, channel_name=None):
        """Add or update server configuration"""
        self.data['servers'][str(guild_id)] = {
            'channel_id': channel_id,
            'enabled': True,
            'last_action_id': 0,
            'guild_name': guild_name,
            'channel_name': channel_name,
            'added_at': datetime.datetime.now().isoformat()
        }
        self.save_database()
        print(f"Added server: {guild_name} -> #{channel_name} ({channel_id})")
    
    def remove_server(self, guild_id):
        """Remove server when bot leaves"""
        if str(guild_id) in self.data['servers']:
            del self.data['servers'][str(guild_id)]
            self.save_database()
    
    def disable_server(self, guild_id):
        """Disable notifications for a server"""
        if str(guild_id) in self.data['servers']:
            self.data['servers'][str(guild_id)]['enabled'] = False
            self.save_database()
    
    def enable_server(self, guild_id):
        """Enable notifications for a server"""
        if str(guild_id) in self.data['servers']:
            self.data['servers'][str(guild_id)]['enabled'] = True
            self.save_database()
    
    def get_active_servers(self):
        """Get all active servers"""
        active = []
        for guild_id, config in self.data['servers'].items():
            if config.get('enabled', True):
                active.append({
                    'guild_id': int(guild_id),
                    'channel_id': config['channel_id'],
                    'last_action_id': config.get('last_action_id', 0),
                    'guild_name': config.get('guild_name', 'Unknown'),
                    'channel_name': config.get('channel_name', 'Unknown')
                })
        return active
    
    def update_last_action_id(self, guild_id, action_id):
        """Update the last processed action ID for a server"""
        if str(guild_id) in self.data['servers']:
            self.data['servers'][str(guild_id)]['last_action_id'] = action_id
            self.save_database()
    
    def get_server_count(self):
        """Get total number of servers"""
        return len([s for s in self.data['servers'].values() if s.get('enabled', True)])

# Initialize database
db = ServerDatabase()

# Bot setup with required intents
intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    print(f"Failed request {url}, status {resp.status}")
                    return None
                return await resp.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

async def fetch_leaderboard():
    return await fetch_json(LEADERBOARD_URL)

async def fetch_diff(action_id):
    return await fetch_json(DIFF_URL.format(action_id=action_id))

async def format_diff(data):
    if not data:
        return None, None
    
    squads = []
    timestamps = []

    # Squadrons you want to highlight: { "Name": "Emoji" }
    highlighted_squadrons = {
        "WE ROCK YOU ROLL": "🔸",
    }

    for change in data:
        squad = change.get("squadron_name", "Unknown")
        squad_tag = change.get("tag", "Unknown")
        diff = change.get("total_experience_diff", 0)
        ts = change.get("timestamp", "")

        emoji = highlighted_squadrons.get(squad, "🔹")
        squads.append(f"{emoji} {squad} ({squad_tag}) gained {diff:,} points")
        timestamps.append(ts)

    timestamp = timestamps[-1] if timestamps else None
    squads_text = "\n".join(squads) if squads else None
    return squads_text, timestamp

async def send_update_to_server(server_info, embed):
    """Send update to a specific server, handling errors gracefully"""
    try:
        channel = bot.get_channel(server_info['channel_id'])
        if not channel:
            print(f"Channel {server_info['channel_id']} not found for {server_info['guild_name']}. Removing server from database.")
            db.remove_server(server_info['guild_id'])
            return False
        await channel.send(embed=embed)
        print(f"Sent update to {server_info['guild_name']} -> #{server_info['channel_name']}")
        return True
    except discord.Forbidden:
        print(f"No permission in {server_info['guild_name']} -> #{server_info['channel_name']}")
        return False
    except discord.NotFound:
        print(f"Channel not found: {server_info['guild_name']} -> #{server_info['channel_name']}")
        db.remove_server(server_info['guild_id'])
        return False
    except Exception as e:
        print(f"Error sending to {server_info['guild_name']}: {e}")
        return False

async def monitoring_task():
    """Main monitoring loop"""
    await bot.wait_until_ready()
    print("Starting CQC monitoring task...")

    while not bot.is_closed():
        try:
            leaderboard = await fetch_leaderboard()
            if not leaderboard:
                print("Failed to fetch leaderboard")
                await asyncio.sleep(60)
                continue
            
            latest_action_id = leaderboard[0]["action_id"]
            active_servers = db.get_active_servers()
            
            if not active_servers:
                print("No active servers to monitor")
                await asyncio.sleep(60)
                continue
            
            updates_sent = 0
            
            # Check each server individually
            for server_info in active_servers:
                if latest_action_id > server_info['last_action_id']:
                    # Fetch and format the diff
                    diff = await fetch_diff(latest_action_id)
                    msg, ts = await format_diff(diff)
                    if msg:
                        embed = discord.Embed(
                            title="CQC Activity Detected",
                            description=msg,
                            color=discord.Color.green()
                        )
                        if ts:
                            try:
                                dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                                unix_ts = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
                                embed.description = f"{msg}\n\n 🕛 <t:{unix_ts}:f>"
                            except ValueError:
                                pass
                        # Send to this server
                        sent = await send_update_to_server(server_info, embed)
                        if not sent:
                            # If the server was removed, skip further processing for this server
                            continue
                        updates_sent += 1
                        db.update_last_action_id(server_info['guild_id'], latest_action_id)
            
            if updates_sent > 0:
                print(f"Sent {updates_sent} updates for action ID {latest_action_id}")
            else:
                print("No new activity")
                
        except Exception as e:
            print(f"Error in monitoring task: {e}")

        await asyncio.sleep(60)  # Check every minute

# Event handlers
@bot.event
async def on_ready():
    print(f"{bot.user} is ready!")
    print(f"Connected to {len(bot.guilds)} servers")
    print(f"Monitoring {db.get_server_count()} active channels")
    # Sync slash commands
    await bot.tree.sync()
    print("Slash commands synced.")
    # Generate invite link
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            use_application_commands=True
        ),
        scopes=['bot', 'applications.commands']
    )
    print(f"Bot invite link: {invite_url}")

@bot.event
async def on_guild_join(guild):
    """Automatically set up the bot when added to a new server"""
    print(f"Bot added to new server: {guild.name} ({guild.id})")
    
    # Try to find a suitable channel (look for 'general', 'bot', 'elite', etc.)
    suitable_channels = []
    
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            # Prioritize channels with relevant names
            channel_name_lower = channel.name.lower()
            if any(keyword in channel_name_lower for keyword in ['elite', 'cqc', 'bot', 'gaming']):
                suitable_channels.insert(0, channel)  # Put at front
            elif any(keyword in channel_name_lower for keyword in ['general', 'main', 'chat']):
                suitable_channels.append(channel)
            elif 'spam' not in channel_name_lower and 'log' not in channel_name_lower:
                suitable_channels.append(channel)
    
    if suitable_channels:
        channel = suitable_channels[0]
        db.add_server(guild.id, channel.id, guild.name, channel.name)
        
        # Send welcome message
        embed = discord.Embed(
            title="CQC Monitor Bot Active!",
            description=(
                "Thanks for adding the CQC Monitor Bot!\n\n"
                f"I will automatically post CQC activity updates in {channel.mention}.\n\n"
                "Note that only CMDRs in squadrons are tracked.\n\n"
                "**General Commands:**\n"
                "`/cqc_help` - View list of commands\n"
                "`/cqc_info` - Learn about CQC\n"
                "`/cqc_bugs` - Learn how to circumvent CQC's game breaking bugs\n\n"
                "**Admin Commands:**\n"
                "`/cqc_status` - View bot status\n"
                "`/cqc_channel` - Change notification channel\n"
                "`/cqc_this_channel` - Set current channel for notifications\n"
                "`/cqc_disable` - Disable notifications\n"
                "`/cqc_enable` - Enable notifications\n"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="CQC Monitor")

        try:
            await channel.send(embed=embed)
        except:
            print(f"Couldn't send welcome message to {guild.name}")
    else:
        print(f"No suitable channel found in {guild.name}")

@bot.event
async def on_guild_remove(guild):
    """Clean up when bot is removed from a server"""
    print(f"Bot removed from server: {guild.name} ({guild.id})")
    db.remove_server(guild.id)


# Slash commands using app_commands
@bot.tree.command(name="cqc_status", description="Check CQC bot status and statistics (Admin only)")
@discord.app_commands.guild_only()
async def cqc_status(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only an administrator can use this command. This incident will be reported.", ephemeral=True)
        return
    active_servers = db.get_active_servers()
    current_server = None
    for server in active_servers:
        if server['guild_id'] == interaction.guild.id:
            current_server = server
            break
    embed = discord.Embed(
        title="CQC Monitor Bot Status",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Global Stats",
        value=f"Connected to **{len(bot.guilds)}** total servers",
        inline=False
    )
    if current_server:
        channel = bot.get_channel(current_server['channel_id'])
        embed.add_field(
            name="This Server",
            value=f"Channel: {channel.mention if channel else 'Unknown'}\nStatus: Active\nLast Action: {current_server['last_action_id']}",
            inline=False
        )
    else:
        embed.add_field(
            name="This Server",
            value="Not configured",
            inline=False
        )
    embed.add_field(
        name="Update Frequency",
        value="Every 60 seconds",
        inline=True
    )
    embed.set_footer(text="CQC Monitor")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="cqc_channel", description="Set the channel for CQC notifications (Admin only)")
@discord.app_commands.describe(channel="Channel for CQC notifications (optional)")
@discord.app_commands.guild_only()
async def cqc_channel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only an administrator can use this command. This incident will be reported.", ephemeral=True)
        return
    target_channel = channel or interaction.channel
    if not target_channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(f"I don't have permission to send messages in {target_channel.mention}", ephemeral=True)
        return
    db.add_server(interaction.guild.id, target_channel.id, interaction.guild.name, target_channel.name)
    await interaction.response.send_message(f"CQC notifications will now be sent to {target_channel.mention}")


@bot.tree.command(name="cqc_enable", description="Enable CQC notifications (Admin only)")
@discord.app_commands.guild_only()
async def cqc_enable(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only an administrator can use this command. This incident will be reported.", ephemeral=True)
        return
    db.enable_server(interaction.guild.id)
    await interaction.response.send_message("CQC notifications enabled!")


@bot.tree.command(name="cqc_disable", description="Disable CQC notifications (Admin only)")
@discord.app_commands.guild_only()
async def cqc_disable(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only an administrator can use this command. This incident will be reported.", ephemeral=True)
        return
    db.disable_server(interaction.guild.id)
    await interaction.response.send_message("CQC notifications disabled.")


@bot.tree.command(name="cqc_info", description="Learn about Elite Dangerous CQC")
@discord.app_commands.guild_only()
async def cqc_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 What is Elite Dangerous CQC?",
        description=(
            "**Close Quarters Championship (CQC)** is Elite Dangerous' fast-paced arena combat mode.\n\n"
            "🕹 **Modes:**\n"
            "• Deathmatch > 2-8 players free for all\n"
            "• Team Deathmatch > 4-8 players, minimum 2v2\n"
            "• Capture the Flag > 4-8 players, minimum 2v2\n\n"
            "👥 **Squads:**\n"
            "• Form squads of up to 4 players\n"
            "• Squadmates spawn together\n"
            "• Non-exclusive matchmaking\n\n"
            "• For more info on CQC, visit https://elite-dangerous.fandom.com/wiki/CQC_Championship\n\n"
            "This bot tracks leaderboard changes and squadron activity!"
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Close Quarters Championship")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="cqc_bugs", description="Learn how to circumvent CQC's game breaking bugs")
@discord.app_commands.guild_only()
async def cqc_bugs(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📢 CQC Game Breaking Bugs",
        description=(
            "Here are some known game-breaking bugs in CQC and how to get around them:\n\n"
            "**1. Game ending screen error out** After a match ends, you get an error returning you back to the main menu. If there are any players who were left in the lobby and continue playing without error or quitting, you can no longer join them in this lobby.\n"
            "**2. Broken lobbies** You get put into a lobby of a gamemode with enough people to start the given mode (2 CMDRs for DM, 4 for TDM & CTF). If the lobby continues to display message - waiting for more players - it is most likely bugged and all players will need to leave it and requeue in order to let the old lobby disappear and a new one to be created.\n"
            "**3. De-Instance/Incompatible Clients** The games of 2 players will not work together no matter what, any attempts to get them into one squad will fail, if they are already in a game together, they will not see each other. This is always issue on one of the player's end and will be fixed when he restarts the game from desktop, however it is impossible to determine on who's side it is beforehand so both players should restart.\n"
        ),
        color=discord.Color.red()
    )
    embed.set_footer(text="Close Quarters Championship")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="cqc_this_channel", description="Set the current channel for CQC notifications (Admin only)")
@discord.app_commands.guild_only()
async def cqc_this_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only an administrator can use this command. This incident will be reported.", ephemeral=True)
        return
    channel = interaction.channel
    if not channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}", ephemeral=True)
        return
    db.add_server(interaction.guild.id, channel.id, interaction.guild.name, channel.name)
    await interaction.response.send_message(f"CQC notifications will now be sent to {channel.mention}")

@bot.tree.command(name="cqc_help", description="Show available CQC Monitor bot commands")
@discord.app_commands.guild_only()
async def cqc_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="CQC Bot Help & Commands",
        description=(
            "**General Commands:**\n"
            "`/cqc_help` - View list of commands\n"
            "`/cqc_info` - Learn about CQC\n"
            "`/cqc_bugs` - Learn how to circumvent CQC's game breaking bugs\n\n"
            "**Admin Commands:**\n"
            "`/cqc_status` - View bot status\n"
            "`/cqc_channel` - Change notification channel\n"
            "`/cqc_this_channel` - Set current channel for notifications\n"
            "`/cqc_disable` - Disable notifications\n"
            "`/cqc_enable` - Enable notifications\n"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="CQC Monitor")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Setup and run
async def setup_hook():
    bot.loop.create_task(monitoring_task())

bot.setup_hook = setup_hook

# Run the bot
try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("ERROR: Invalid Discord bot token!")
except Exception as e:
    print(f"Unexpected error: {e}")