# KMergeBoxBot
A basic Python bot for automating the merge box on the Kobold server

# Usage
- Checkout this repository
- Before running, a configuration file for the bot is needed - create a new .env file within the same directory.  It should contain the following fields.  Please populat the basePath with the merge directory, the channel to listen on with the channel ID and the API key with the API key to use with this application.
```env
basePath=""
channelToListenOn=000000000000000
forbiddenWordsRole=000000000000000
forbiddenWordsError="You are not allowed to perform this kind of merge without a specific role"
forbiddenWords="---,bad,dab"
cleanupThreshold=0.90
apiKey=""
```
- This bot should be run on Python 3.10 and up.  Please install the requirements provided in requirements.txt, then start the bot by running the main script.
