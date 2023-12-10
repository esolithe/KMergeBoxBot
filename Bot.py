import discord, subprocess
from discord.ext import tasks
import os
from os import path
from dotenv import load_dotenv

load_dotenv()

basePath=os.getenv('basePath')
channelToListenOn=int(os.getenv('channelToListenOn'))
apiKey=os.getenv('apiKey')

class KMergeBoxBot(discord.Client):
    currentTasks = {}

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.runMerges.start()

    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if not message.channel.id == channelToListenOn:
            return
        if message.author.id == self.user.id:
            return
        if len(message.attachments) != 1:
            return
        attachment = message.attachments[0]
        if not attachment.filename.endswith(".yaml"):
            return
        if message.author.id in self.currentTasks.keys():
            await message.channel.send(f'{message.author.mention} has already submitted a pending task (please try and submit it again later): {self.currentTasks[message.author.id].filename}')
            return
        locToSaveTo = path.join(basePath,attachment.filename)
        if path.exists(locToSaveTo):
            await message.channel.send(f'The file {attachment.filename} already has been merged before. Please choose a different name {message.author.mention}.')
            return
        await attachment.save(locToSaveTo)
        self.currentTasks[message.author.id] = attachment
        print(f'Attachment submitted from {message.author}: {message.content} and saved to {locToSaveTo}')
        await message.channel.send(f'Task submitted for {message.author.mention}: {attachment.filename}')

    @tasks.loop(seconds=10)
    async def runMerges(self):
        if len(self.currentTasks.keys()) == 0:
            return
        firstTask = next(iter(self.currentTasks.items()))
        attachment = firstTask[1]
        nameWithoutExt = attachment.filename.replace('.yaml', '')
        # TODO Replace with an option which does not use shell=True
        result = subprocess.run(f'./run.sh {nameWithoutExt}', capture_output=True, text=True, shell=True) # subprocess.run([f'./run.sh {nameWithoutExt}'], capture_output=True, text=True, shell=True)
        resultText = f'STDOUT: {result.stdout}, STDERR: {result.stderr}'
        print(resultText)
        del self.currentTasks[firstTask[0]]
        channel = self.get_channel(channelToListenOn)
        if (len(result.stderr) == 0):
            await channel.send(f'<@{firstTask[0]}> - {nameWithoutExt} has been merged successfully')
        else:
            locToSaveTo = path.join(basePath, 'log.txt')
            with open(locToSaveTo, 'w') as filetowrite:
                filetowrite.write(resultText)
            file = discord.File(locToSaveTo)
            await channel.send(f'<@{firstTask[0]}> - {nameWithoutExt} has failed to merge', file=file)

    @runMerges.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()

intents = discord.Intents.default()
intents.message_content = True

client = KMergeBoxBot(intents=intents)
client.run(apiKey)