import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import pymongo  # Swapped from sqlite3 to pymongo for cloud persistence

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

# Connect to the Secure Cloud Database via Environment Variable
MONGO_URL = os.getenv("MONGO_URI")
client = pymongo.MongoClient(MONGO_URL)
db = client["guild_database"]
ledger_collection = db["contributions"]

@bot.event
async def on_ready():
    print(f"Guild Contribution Bot is ready. Logged in as {bot.user}")

@bot.group(invoke_without_command=True)
async def ledger(ctx):
    # Retrieve all members from the cloud and sort them by top donors
    cursor = ledger_collection.find().sort([("extra_donated", -1), ("total_deposited", -1)])
    rows = list(cursor)
    
    if not rows:
        await ctx.send("📋 The cloud guild ledger is currently empty.")
        return
    
    response = "🏰 **Guild Weekly Contribution Ledger** 🏰\n========================================\n"
    for index, user_data in enumerate(rows, start=1):
        username = user_data["username"]
        total = user_data["total_deposited"]
        progress = user_data["weekly_progress"]
        extra = user_data["extra_donated"]
        
        status = "✅ Met" if progress >= WEEKLY_REQUIREMENT else f"❌ Short by {WEEKLY_REQUIREMENT - progress:,}"
        medal = "👑 " if index == 1 and extra > 0 else "👤 "
        response += f"{medal}**{username}**\n   ↳ Progress: {progress:,} / {WEEKLY_REQUIREMENT:,} ({status})\n   ↳ Extra Donated: **{extra:,}** | Total Lifetime: {total:,}\n\n"
    await ctx.send(response)

@ledger.command(name="deposit")
async def ledger_deposit(ctx, username: str, amount: int):
    if amount <= 0:
        await ctx.send("❌ Deposit amount must be greater than 0.")
        return
    
    # Check if user already exists in the cloud database
    user_data = ledger_collection.find_one({"username": username})
    
    if user_data:
        old_total = user_data.get("total_deposited", 0)
        old_progress = user_data.get("weekly_progress", 0)
    else:
        old_total = 0
        old_progress = 0
        
    new_total = old_total + amount
    new_progress = old_progress + amount
    new_extra = (new_progress - WEEKLY_REQUIREMENT) if new_progress > WEEKLY_REQUIREMENT else 0

    # Save data permanently to the cloud
    ledger_collection.update_one(
        {"username": username},
        {"$set": {
            "total_deposited": new_total,
            "weekly_progress": new_progress,
            "extra_donated": new_extra
        }},
        upsert=True
    )
    
    msg = f"💰 **{username}** deposited **{amount:,}**!\n" + (f"🔥 Tier: Top Donor! Extra: **{new_extra:,}**" if new_extra > 0 else "")
    await ctx.send(msg)

@ledger.command(name="resetweek")
async def ledger_reset_week(ctx):
    # Wipes weekly metrics across the entire cloud collection simultaneously
    ledger_collection.update_many({}, {"$set": {"weekly_progress": 0, "extra_donated": 0}})
    await ctx.send("🔄 **Weekly Reset Complete!**")

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
