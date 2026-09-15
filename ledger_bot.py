import discord
from discord.ext import commands
import sqlite3
from flask import Flask
from threading import Thread

# --- WEBSERVER FOR CLOUD HOSTING ---
app = Flask('')

@app.route('/')
def home():
    return "Ledger Bot is awake and running!"

def run_webserver():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_webserver)
    t.start()
# -----------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

WEEKLY_REQUIREMENT = 3000000

conn = sqlite3.connect("guild_ledger.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS guild_contributions (
        username TEXT PRIMARY KEY,
        total_deposited INTEGER DEFAULT 0,
        weekly_progress INTEGER DEFAULT 0,
        extra_donated INTEGER DEFAULT 0
    )
""")
conn.commit()

@bot.event
async def on_ready():
    print(f"Guild Contribution Bot is ready. Logged in as {bot.user}")

@bot.group(invoke_without_command=True)
async def ledger(ctx):
    cursor.execute("""
        SELECT username, total_deposited, weekly_progress, extra_donated 
        FROM guild_contributions 
        ORDER BY extra_donated DESC, total_deposited DESC
    """)
    rows = cursor.fetchall()
    if not rows:
        await ctx.send("📋 The guild ledger is currently empty.")
        return
    
    response = "🏰 **Guild Weekly Contribution Ledger** 🏰\n========================================\n"
    for index, row in enumerate(rows, start=1):
        username, total, progress, extra = row
        status = "✅ Met" if progress >= WEEKLY_REQUIREMENT else f"❌ Short by {WEEKLY_REQUIREMENT - progress:,}"
        medal = "👑 " if index == 1 and extra > 0 else "👤 "
        response += f"{medal}**{username}**\n   ↳ Progress: {progress:,} / {WEEKLY_REQUIREMENT:,} ({status})\n   ↳ Extra Donated: **{extra:,}** | Total Lifetime: {total:,}\n\n"
    await ctx.send(response)

@ledger.command(name="deposit")
async def ledger_deposit(ctx, username: str, amount: int):
    if amount <= 0:
        await ctx.send("❌ Deposit amount must be greater than 0.")
        return
    cursor.execute("SELECT total_deposited, weekly_progress, extra_donated FROM guild_contributions WHERE username = ?", (username,))
    row = cursor.fetchone()
    
    old_total, old_progress, old_extra = row if row else (0, 0, 0)
    new_total = old_total + amount
    new_progress = old_progress + amount
    new_extra = (new_progress - WEEKLY_REQUIREMENT) if new_progress > WEEKLY_REQUIREMENT else 0

    if row:
        cursor.execute("UPDATE guild_contributions SET total_deposited = ?, weekly_progress = ?, extra_donated = ? WHERE username = ?", (new_total, new_progress, new_extra, username))
    else:
        cursor.execute("INSERT INTO guild_contributions (username, total_deposited, weekly_progress, extra_donated) VALUES (?, ?, ?, ?)", (username, new_total, new_progress, new_extra))
    conn.commit()
    
    msg = f"💰 **{username}** deposited **{amount:,}**!\n" + (f"🔥 Tier: Top Donor! Extra: **{new_extra:,}**" if new_extra > 0 else "")
    await ctx.send(msg)

@ledger.command(name="resetweek")
async def ledger_reset_week(ctx):
    cursor.execute("UPDATE guild_contributions SET weekly_progress = 0, extra_donated = 0")
    conn.commit()
    await ctx.send("🔄 **Weekly Reset Complete!**")

# Starts the mini webserver first
keep_alive()

# Replace with your actual Discord Bot Token
bot.run("MTU0OTMyMzE1Mzc0OTE4ODcxOQ.GInSat.FSoJAONX4hmOLKjcOqf3eAkD4Zc70xwA1vs-R0")
