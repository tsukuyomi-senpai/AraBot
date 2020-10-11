from discord.ext.commands import Cog
from re import search
from asyncio import wait_for, TimeoutError

class EasterEggs(Cog):
	def __init__(self, client):
		self.bot = client

	@Cog.listener("on_message")
	async def imposter(self, msg):
		if not msg.author.bot and msg.author.voice and (chl:=msg.author.voice.channel) and (word:=search("\\b(impost[eo]r)\\b", msg.content.lower())):
			word = word.group(1)
			await msg.channel.send("<:KonoDioDa:676949860502732803>")
			await msg.channel.send(f"You have 15 seconds to find the {word}!\nPing the person you think is the {word} to vote")
			voted, votes = [], {}
			check = lambda vote: vote.author not in voted and vote.mentions and search("^<@!?\d{15,21}>$", vote.content) and vote.channel == msg.channel and vote.author.voice and vote.author.voice.channel == chl and vote.mentions[0] != vote.author
			async def ensure():
				while True:
					vote = await self.bot.wait_for("message", check=check)
					await vote.delete()
					voted.append(vote.mentions[0])
					votes[vote.mentions[0]] = votes.get(vote.mentions[0], 0) + 1
			try:
				await wait_for(ensure(), timeout=15)
			except TimeoutError:
				pass
			values = sorted(votes.values(), reverse=True)
			if len(votes) > 1 and values[0] != values[1]:
				imposter = max(votes, key=lambda m: votes[m])
				await msg.channel.send(f"{imposter.mention} was the {word}.")
				await imposter.move_to(None, reason="The " + word)
			else:
				await msg.channel.send("No one was ejected.")

def setup(client):
	client.add_cog(EasterEggs(client))