# blanc_gw_bot.py
# Imports
import discord
import os

from apiclient import discovery
from google.oauth2 import service_account
from dotenv import load_dotenv

# Environment Variables
load_dotenv()
BOT_REVIEW_EMOJI = '\U0001F50D'     # magnifying glass emoji
GUILD_TEST = os.getenv('DISCORD_GUILD_TEST')
GUILD_PROD = os.getenv('DISCORD_GUILD')
TOKEN = os.getenv('DISCORD_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = os.getenv('SPREADSHEET_RANGE')
AUTH = os.path.join(os.getcwd(), 'blanc-gw-sheet-credentials.json')

BOT_COMMAND_CHANNEL = {
    "test": int(os.getenv('BOT_COMMAND_TEST')),
    "prod": int(os.getenv('BOT_COMMAND_PROD'))
}

# Constants
PREFIX = '?'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
GW_DATA = []

client = discord.Client()

### Class for organizing spreadsheet data
class BlancGwInfo:
    def __init__(self, id, name, main_element, activity_check, checks, strikes, pass_used):
        self.id = id
        self.name = name
        self.main_element = main_element
        self.activity_check = activity_check
        self.checks = checks
        self.strikes = strikes
        self.pass_used = pass_used

    def get_total(self):
        return int(self.activity_check) + int(self.checks) + int(self.strikes)

### Util Methods
def load_data_from_spreadsheet(values):
    gw_data = []
    for row in values:
        # Skip if no name, placeholder name (e.g. -), or if it's the header row
        if ((row[1] != '' and row[1] != '-') and row[0] != '2022 Pass used?'):
            gw_data.append(BlancGwInfo(row[8], row[1], row[2], row[3], row[4], row[5], row[0] != "NO"))
    return gw_data

def does_message_need_processing(message, env):
    # Check if a message is a DM
    if isinstance(message.channel, discord.DMChannel):
        return True

    # Only process messages in the allowed channels otherwise
    if message.channel.id != BOT_COMMAND_CHANNEL[env]:
        return False

    return True

def get_gw_data(discord_id):
    matches = []
    for data in GW_DATA:
        if str(data.id) == str(discord_id):
            matches.append(data)
    return matches

def build_gw_info_dm(member_data):
    message = f'{len(member_data)} account(s) was/were found linked to your Discord username.\n'
    message = message + '------------------------------------\n'
    for data in member_data:
        total = data.get_total()
        message = message + f'__**{data.name}**__\n'
        message = message + f'**Main Element**: {data.main_element}\n'
        message = message + f'**Pass Used?**: {data.pass_used}\n'
        message = message + f'**Activity Check**: {data.activity_check}\n'
        message = message + f'**Checks**: {data.checks}\n'
        message = message + f'**Strikes**: {data.strikes}\n'
        message = message + f'**Checks/Strikes Total**: {total}\n'
        message = message + '------------------------------------\n'
    return message

### Discord Events
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    # Ignore message if the message author is the bot itself
    if (message.author == client.user):
        return

    # Mostly just checking if using bot in test env
    env = "prod"
    if message.guild:
        guild_name = message.guild.name
        if guild_name == GUILD_TEST:
            env = "test"
    print(f'Environment: {env}')

    # Check if message needs to be processed or not
    # Mostly checking if the message is in the appropriate channel/DMs
    if not does_message_need_processing(message, env):
        return

    # Decorator line to separate messages in terminal output
    print('=============================================')

    # Check if message matches command
    if message.content.startswith(PREFIX + 'gwinfo'):      
        print(f'[INFO] ?gwinfo invoked by {message.author.name}.')
        print(f'[INFO] Looking up GW info data for {message.author.name}.')

        member_data = get_gw_data(message.author.id)

        if len(member_data) == 0:
            print(f'[ERROR] GW data could not be found for {message.author.name} ({messsage.author.id}).')
            await message.channel.send('Your GW data cannot be found. Please check with FOs/Captains.')
            await message.add_reaction(BOT_REVIEW_EMOJI)
            return

        dm_message = build_gw_info_dm(member_data)
        print(f'[INFO] Sending DM to {message.author.name}.\n{dm_message}')
        user = await client.fetch_user(message.author.id)
        await user.send(dm_message)
        await message.add_reaction(BOT_REVIEW_EMOJI)
    else:
        return

# Try logging in to Google Sheets and get values from spreadsheet and starting Discord when data is loaded
try:
    # Log in to Google service account
    credentials = service_account.Credentials.from_service_account_file(AUTH, scopes=SCOPES)
    service = discovery.build('sheets', 'v4', credentials=credentials)

    # Access the Google Sheets API with the service account
    sheet = service.spreadsheets()

    # Retrieve the values in the guild spreadsheet in the given range
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
    else:
        GW_DATA = load_data_from_spreadsheet(values)

        # Start Discord client
        client.run(TOKEN)
except OSError as err:
    print(err)
