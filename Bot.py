import asyncio
import shutil
from os import path

import discord
import os
from discord.ext import tasks
from dotenv import load_dotenv

# Read config from .env file
load_dotenv()
basePath=os.getenv('basePath')
channelToListenOn=int(os.getenv('channelToListenOn'))
gatedWordsRole=int(os.getenv('gatedWordsRole'))
gatedWordsError=os.getenv('gatedWordsError')
gatedWords=os.getenv('gatedWords').split(",")
forbiddenWords=os.getenv('forbiddenWords').split(",")
cleanupThreshold=float(os.getenv('cleanupThreshold'))
apiKey=os.getenv('apiKey')

# Sets base path (current directory)
os.chdir(basePath)

# Main bot class
class KMergeBoxBot(discord.Client):
    # List of current / ongoing tasks
    currentTasks = {}
    # List of current low priority / ongoing tasks
    currentLowPriorityTasks = {}
    # Is cleanup happening
    currentlyCleaning = False
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
        # If requester has already submitted a task, respond with an error
        if message.author.id in self.currentTasks.keys() or message.author.id in self.currentLowPriorityTasks.keys():
            await message.channel.send(f'{message.author.mention} has already submitted a pending task (please try and submit it again later): {self.currentTasks[message.author.id].filename}')
            return

        # If message is a command, then run a regen
        splitCommand = message.content.lower().split(" ")
        if len(splitCommand) == 2 and splitCommand[0] == "!regen":
            self.currentTasks[message.author.id] = splitCommand[1]
            print(f'Rerunning {splitCommand[1]} submitted from {message.author}')
            await message.channel.send(f'Rerunning {splitCommand[1]} submitted from {message.author}')
            return

        # If message do not have exactly one attachment, ignore
        if len(message.attachments) != 1:
            return

        attachment = message.attachments[0]
        # If the attachment is not a yaml, ignore
        if not attachment.filename.endswith(".yaml"):
            return
        locToSaveTo = path.join(basePath,attachment.filename)
        # If the named merge already has been run, respond with an error
        if path.exists(locToSaveTo):
            await message.channel.send(f'The file {attachment.filename} already has been merged before. Please choose a different name {message.author.mention}.')
            return
        # If the file contains gated words, then don't do the merge unless the user has the designated role and even then run at lower priority
        data = (await attachment.read()).decode("utf-8")
        isGated = any(word in data.lower() for word in gatedWords)
        if isGated and not any(role.id == gatedWordsRole for role in message.author.roles):
            await message.channel.send(gatedWordsError)
            return
        # If the file contains banned words, don't run it
        if any(word in data.lower() for word in forbiddenWords):
            await message.channel.send(f'The file {attachment.filename} contains forbidden words and cannot be run.')
            return

        # Save the attachment
        await attachment.save(locToSaveTo)

        # Add merge job to queue and then respond to requester
        if isGated:
            self.currentLowPriorityTasks[message.author.id] = attachment.filename
        else:
            self.currentTasks[message.author.id] = attachment.filename

        print(f'Attachment submitted from {message.author}: {message.content} and saved to {locToSaveTo}')
        await message.channel.send(f'Task submitted for {message.author.mention}: {attachment.filename}')

    @tasks.loop(seconds=10)
    async def runMerges(self):
        # Check disk space free
        if self.currentlyCleaning == True:
            return
        total, used, free = shutil.disk_usage(__file__)
        if (used / total > cleanupThreshold):
            print("Running cleanup")
            asyncio.ensure_future(self.cleanupSpace())

        # If no jobs in queue, skip
        if len(self.currentTasks.keys()) == 0 and len(self.currentLowPriorityTasks.keys()) == 0:
            return
        if self.currentlyMerging == True:
            return
        self.currentlyMerging = True
        asyncio.ensure_future(self.runFirstItemInQueue())

    async def cleanupSpace(self):
        self.currentlyCleaning = True
        # Declare the merge job command
        commandToRun = f'sh ./cleanup.sh'
        # Start up the merge process, piping outputs ready to be collected once complete
        process = await asyncio.create_subprocess_shell(commandToRun, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
        # Wait for the merge to complete (no logs will be printed yet)
        stdout, stderr = await process.communicate()
        # Put the standard out and error into a single string
        resultText = f'STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}'
        # Print to logs (console and file)
        print(resultText)
        await asyncio.sleep(30)
        self.currentlyCleaning = False

    async def runFirstItemInQueue(self):
        # Get first task in the ordered dictionary
        firstTask = next(iter(self.currentTasks.items()), next(iter(self.currentLowPriorityTasks.items()), ""))
        if firstTask == "":
            self.currentlyMerging = False
            return
        attachment = firstTask[1]
        # Get the name without the extension
        nameWithoutExt = attachment.replace('.yaml', '')
        print(f'Starting merge: {nameWithoutExt}')
        # Declare the merge job command
        commandToRun = f'sh ./run.sh {nameWithoutExt}'
        # Start up the merge process, piping outputs ready to be collected once complete
        process = await asyncio.create_subprocess_shell(commandToRun, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        # Wait for the merge to complete (no logs will be printed yet)
        stdout, stderr = await process.communicate()
        # Put the standard out and error into a single string
        resultText = f'STDOUT: {stdout.decode()}, STDERR: {stderr.decode()}'
        # Print to logs (console and file)
        print(resultText)
        locToSaveTo = path.join(basePath, 'log.txt')
        with open(locToSaveTo, 'w') as fileToWrite:
            fileToWrite.write(resultText)
        # Get the channel to respond to
        channel = self.get_channel(channelToListenOn)
        # Respond with the logs as an attachment
        file = discord.File(locToSaveTo)
        await channel.send(f'<@{firstTask[0]}> - {nameWithoutExt} has finished', file=file)
        # Clear from the pending task queue
        del self.currentTasks[firstTask[0]]
        del self.currentLowPriorityTasks[firstTask[0]]
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