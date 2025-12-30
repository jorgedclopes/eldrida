import requests
import discord
import openai
import os
import re
from openai import AsyncOpenAI

# export DISCORD_KEY=dummy_discord_token
# export OPENAI_API_KEY=dummy_openai_token
openai.api_key = os.getenv("OPENAI_API_KEY")
discord_token = os.getenv("DISCORD_KEY")

intent = discord.Intents.default()
intent.messages = True
intent.message_content = True
discord_client = discord.Client(intents=intent)


llm_client = AsyncOpenAI(
    # This is the default and can be omitted
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)


@discord_client.event
async def on_ready():
    print("Logged in as {0.user}".format(discord_client))


DISCORD_LIMIT = 2000
DISCORD_SAFE_LIMIT = 1500  # buffer before split
SECTION_PATTERNS = [
    r"\n\n---\n\n",          # Horizontal rule
    r"\n\n#{1,6} ",          # Markdown headers
    r"\n\n",                 # Paragraph break
]


def find_semantic_split(text, limit=DISCORD_SAFE_LIMIT):
    """
    Returns an index at which to split the text.
    The split occurs BEFORE a new semantic section starts.
    """
    if len(text) <= limit:
        return None

    candidates = []

    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, text):
            idx = match.start()
            if idx < limit:
                candidates.append(idx)

    if candidates:
        return max(candidates)

    # Fallback: unavoidable hard split
    return limit


class ModelHandler:
    def __init__(self):
        self.model_id = [model for model in self.list_models().split("\n") if model.startswith("openai")][0]

    def list_models(self):
        base_url = "https://openrouter.ai/api/v1"
        headers = {"Authorization": f"Bearer {openai.api_key}"}
        response = requests.get(f"{base_url}/models", headers=headers)
        self.free_models = [
            model for model in response.json()["data"] if model["id"].endswith("free")
        ]
        return "\n".join(model["id"] for model in self.free_models)

    def set_model(self, model_id):
        if model_id not in self.list_models().split("\n"):
            raise ValueError("Model not available")

        self.model_id = model_id


model_handler = ModelHandler()


BASE_COMMAND = "/Eldrida"


@discord_client.event
async def on_message(message):
    if message.author == discord_client.user or not str(message.content).startswith(
        BASE_COMMAND
    ):
        return

    command = message.content[len(BASE_COMMAND) :].strip()
    #print(f"{message.author} sent a message from {message.channel.name} in {message.guild.name}")
    print(f"{message.author} requested \"{command}\" from {message.channel.name} in {message.guild.name}")

    if command.startswith("model"):
        parts = command.split()

        if len(parts) == 1 or parts[1] == "get":
            await message.channel.send(f"🧠 Current model: `{model_handler.model_id}`")
            return

        if len(parts) == 1 or parts[1] == "list":
            await message.channel.send(
                "📚 Available models:\n" + model_handler.list_models()
            )
            return

        if parts[1] == "set" and len(parts) == 3:
            new_model = parts[2]
            try:
                model_handler.set_model(new_model)
                await message.channel.send(f"✅ Model changed to:\n`{new_model}`")
            except ValueError:
                await message.channel.send(
                    "❌ Unknown model.\n"
                    "Use `/Eldrida model list` to see available models."
                )
            return

    await llm_stream(message)

async def llm_stream(message):
    command = message.content[len(BASE_COMMAND) :].strip()
    openai_prompt = [{"role": "user", "content": command}]

    discord_msg = await message.channel.send("🧠 Thinking…")
    try:
        stream = await llm_client.responses.create(
            model=model_handler.model_id,
            input=openai_prompt,
            stream=True,
        )

        messages = [discord_msg]
        buffer = ""
        last_update = 0

        async for event in stream:
            if event.type == "response.output_text.delta":
                buffer += event.delta

            split_at = find_semantic_split(buffer)
            if split_at:
                chunk = buffer[:split_at]
                buffer = buffer[split_at:]

                await messages[-1].edit(content=chunk)
                new_msg = await message.channel.send("…")
                messages.append(new_msg)

            now = discord_client.loop.time()
            if now - last_update > 0.5:
                await messages[-1].edit(content=buffer or "…")
                last_update = now

        if buffer:
            await messages[-1].edit(content=buffer)

    except openai.RateLimitError as rle:
        await discord_msg.edit(
            content="❌ There was a problem invoking the model. Try again or contact admin."
        )
        raise rle
    except Exception as e:
        await discord_msg.edit(
            content="❌ There was a general problem. Please contact the admin."
        )


@discord_client.event
async def on_message_edit(before, after):
    if after.author == discord_client.user:
        return
    if after.author.bot: # do I really want this?
        return

    if before.content == after.content:
        return  # embed-only edits, ignore

    print("Before:", before.content)
    print("After:", after.content)


if __name__ == "__main__":
    discord_client.run(discord_token)
