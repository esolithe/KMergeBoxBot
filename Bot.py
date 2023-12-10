import asyncio

import discord, subprocess
import os
from discord.ext import tasks
from os import path
from dotenv import load_dotenv

# Read config from .env file
load_dotenv()
basePath=os.getenv('basePath')
channelToListenOn=int(os.getenv('channelToListenOn'))
apiKey=os.getenv('apiKey')

# Main bot class
class KMergeBoxBot(discord.Client):
    # List of current / ongoing tasks
    currentTasks = {}
    # Is a merge running
    currentlyMerging = False

    # Start the merge watcher / runner in the background
    async def setup_hook(self) -> None:
        self.runMerges.start()

    # Log the logon event
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        # If channel is not the one specified in the .env file, ignore
        if not message.channel.id == channelToListenOn:
            return
        # If message sent from the bot, ignore
        if message.author.id == self.user.id:
            return
        # If message do not have exactly one attachment, ignore
        if len(message.attachments) != 1:
            return
        attachment = message.attachments[0]
        # If the attachment is not a yaml, ignore
        if not attachment.filename.endswith(".yaml"):
            return
        # If requester has already submitted a task, respond with an error
        if message.author.id in self.currentTasks.keys():
            await message.channel.send(f'{message.author.mention} has already submitted a pending task (please try and submit it again later): {self.currentTasks[message.author.id].filename}')
            return
        locToSaveTo = path.join(basePath,attachment.filename)
        # If the named merge already has been run, respond with an error
        if path.exists(locToSaveTo):
            await message.channel.send(f'The file {attachment.filename} already has been merged before. Please choose a different name {message.author.mention}.')
            return
        # Save the attachment
        await attachment.save(locToSaveTo)
        # Add merge job to queue and then respond to requester
        self.currentTasks[message.author.id] = attachment
        print(f'Attachment submitted from {message.author}: {message.content} and saved to {locToSaveTo}')
        await message.channel.send(f'Task submitted for {message.author.mention}: {attachment.filename}')

    @tasks.loop(seconds=10)
    async def runMerges(self):
        # If no jobs in queue, skip
        if len(self.currentTasks.keys()) == 0:
            return
        if self.currentlyMerging == True:
            return
        self.currentlyMerging = True
        asyncio.ensure_future(self.runFirstItemInQueue())

    async def runFirstItemInQueue(self):
        # Get first task in the ordered dictionary
        firstTask = next(iter(self.currentTasks.items()))
        attachment = firstTask[1]
        # Get the name without the extension
        nameWithoutExt = attachment.filename.replace('.yaml', '')
        print(f'Starting merge: {nameWithoutExt}')
        # Run the merge job
        # TODO Replace with an option which does not use shell=True
        result = subprocess.run(f'./run.sh {nameWithoutExt}', capture_output=True, text=True, shell=True)
        # Put the standard out and error into a single string
        resultText = f'STDOUT: {result.stdout}, STDERR: {result.stderr}'
        # Print to logs
        print(resultText)
        # Get the channel to respond to
        channel = self.get_channel(channelToListenOn)
        # If there are no errors, confirm it has finished, otherwise respond with the errors as an attachment
        locToSaveTo = path.join(basePath, 'log.txt')
        with open(locToSaveTo, 'w') as fileToWrite:
            fileToWrite.write(resultText)
        file = discord.File(locToSaveTo)
        await channel.send(f'<@{firstTask[0]}> - {nameWithoutExt} has finished', file=file)
        # Clear from the pending task queue
        del self.currentTasks[firstTask[0]]
        self.currentlyMerging = False
        print(f'Ending merge: {nameWithoutExt}')

    # Waits for the user to be logged on before starting the run merges task
    @runMerges.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()

# Runs the merge bot with the provided API key
intents = discord.Intents.default()
intents.message_content = True

client = KMergeBoxBot(intents=intents)
client.run(apiKey)
