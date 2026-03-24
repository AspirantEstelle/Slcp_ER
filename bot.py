import discord
from discord.ext import commands, tasks
import aiohttp
import random
import os
from dotenv import load_dotenv

load_dotenv() # 토큰과 API를 보호하기
TOKEN = os.getenv('DISCORD_TOKEN')
ER_API_KEY = os.getenv('ER_API_KEY')

# 봇 기본 설정 (메시지 내용을 읽기 위한 인텐트 활성화)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 이터널 리턴 스팀 앱 ID
ER_APP_ID = "1049590"

STATUS_LIST = [
    "루미아섬 관찰 중...",
    "알파와 영원회귀에 관해 논하는 중...",
    "현우에게 힘에의 의지를 설명하는 중...",
    "아무 이유 없이 오메가 때리는 중...",
    "차라투스트라와 루트 짜는 중...",
    "신인류와 위버멘쉬의 관계에 대해 생각 중..."
]

@bot.event
async def on_ready():
    change_status.start()
    print(f'로그인 완료: {bot.user}!')

@tasks.loop(minutes=10)
async def change_status():
    # 리스트에서 무작위로 하나를 뽑습니다.
    new_status = random.choice(STATUS_LIST)
    await bot.change_presence(activity=discord.Game(name=new_status))
    

@bot.command(name='동접')
async def concurrent_players(ctx):
    # 스팀 동시접속자 API URL
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={ER_APP_ID}"
    
    # aiohttp를 사용하여 비동기로 데이터를 가져옵니다.
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_count = data.get('response', {}).get('player_count', 0)
                
                # 깔끔하게 보여주기 위해 임베드(Embed) 사용
                embed = discord.Embed(
                    title="이터널 리턴 스팀 동시 접속자", 
                    description=f"현재 **{player_count:,}명**의 실험체가 영원회귀를 경험하고 있습니다!", 
                    color=discord.Color.gold()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("스팀 서버가 이상합니다. 잠시 후 다시 시도해주세요.")

# 봇 실행 (발급받은 토큰을 문자열로 넣어주세요)
bot.run(TOKEN)