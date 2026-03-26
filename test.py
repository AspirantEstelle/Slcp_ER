import discord
from discord.ext import commands, tasks
import aiohttp
import random
import os
from dotenv import load_dotenv
import urllib.parse
import asyncio  # 대기

# --- 1. 환경변수 및 기본 설정 ---
load_dotenv() # 토큰과 API를 보호하기
TOKEN = os.getenv('DISCORD_TOKEN')
ER_API_KEY = os.getenv('ER_API_KEY')

# 이터널 리턴 API 헤더 설정 (위로 끌어올림)
ER_API_HEADERS = {
    "accept": "application/json",
    "x-api-key": ER_API_KEY
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents) # 원래 !

# 이터널 리턴 스팀 앱 ID
ER_APP_ID = "1049590"

# --- 2. 데이터 사전 및 리스트 설정 ---
STATUS_LIST = [
    "루미아섬 관찰 중...",
    "알파와 영원회귀에 관해 논하는 중...",
    "현우에게 힘에의 의지를 설명하는 중...",
    "아무 이유 없이 오메가 때리는 중...",
    "차라투스트라와 루트 짜는 중...",
    "신인류와 위버멘쉬의 관계에 대해 생각 중..."
]

# --- 2. 데이터 사전 및 맵핑 ---
CHARACTER_MAP = {} # L10n API를 통해 자동으로 채워질 빈 사전
CURRENT_SEASON = 37
# 모드별 매칭 코드 (2: 일반, 3: 랭크)
MODE_MAP = {
    "일반": 2,  
    "랭크": 3   
}

# --- 3. 백그라운드 작업 및 초기 설정 ---
@tasks.loop(minutes=10)
async def change_status():
    new_status = random.choice(STATUS_LIST)
    await bot.change_presence(activity=discord.Game(name=new_status))

async def load_character_data():
    global CHARACTER_MAP
    CHARACTER_MAP.clear()
    
    # 캐릭터 이름은 언어팩(L10n) 데이터를 파싱하는 것이 가장 정확합니다.
    l10n_url = "https://open-api.bser.io/v1/l10n/Korean"

    async with aiohttp.ClientSession(headers=ER_API_HEADERS) as session:
        async with session.get(l10n_url) as res:
            if res.status == 200:
                data = await res.json()
                download_link = data['data']['l10Path']
                
                async with session.get(download_link) as text_res:
                    text_data = await text_res.text(encoding='utf-8')
                    
                    for line in text_data.splitlines():
                        # 'Character/Name/'으로 시작하고, 구분자 '┃'가 있는 데이터만 추출
                        if line.startswith("Character/Name/") and "┃" in line:
                            key_part, name = line.split('┃', 1)
                            code_str = key_part.split('/')[-1]
                            
                            if code_str.isdigit():
                                CHARACTER_MAP[int(code_str)] = name # 코드를 Key, 이름을 Value로 저장
                                
                print(f"✅ 총 {len(CHARACTER_MAP)-3}명의 실험체 메타데이터(v2 대응) 로드 완료!")
            else:
                print("❌ 메타데이터를 불러오지 못했습니다.")
                
@bot.event
async def on_ready():
    print(f'로그인 진행 중...')    
    await load_character_data()  # 1. 캐릭터 메타데이터 불러오기
    change_status.start()        # 2. 상태 메시지 변경 루프 시작
    print(f'로그인 완료: {bot.user}!')

# --- 4. 봇 명령어 ---

@bot.command(name='동접')
async def concurrent_players(ctx):
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={ER_APP_ID}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                player_count = data.get('response', {}).get('player_count', 0)
                
                embed = discord.Embed(
                    title="이터널 리턴 스팀 동시 접속자", 
                    description=f"현재 **{player_count:,}명**의 실험체가 영원회귀를 경험하고 있습니다!", 
                    color=discord.Color.gold()
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send("스팀 서버가 이상합니다. 잠시 후 다시 시도해주세요.")
                
@bot.command(name='전적')
async def er_stats_overall(ctx, *, args=None):
    # 1. 입력값 검증 (!전적 닉네임,게임모드)
    if not args or "," not in args:
        await ctx.send("명령어 형식이 틀렸습니다! `!전적 닉네임,게임모드` 형태로 입력해주세요.\n예시: `!전적 조규식,랭크`")
        return
    try:
        nickname, mode_name = [x.strip() for x in args.split(',')]
    except ValueError:
        await ctx.send("항목이 너무 많습니다. 쉼표(,)는 딱 한 번만 사용해세요.")
        return

    matching_mode = MODE_MAP.get(mode_name)
    if not matching_mode:
        await ctx.send(f"'{mode_name}'(은)는 알 수 없는 게임 모드입니다. '일반' 또는 '랭크'를 입력해주세요. 코발트는 아직 지원하지 않습니다.")
        return

    async with aiohttp.ClientSession(headers=ER_API_HEADERS) as session:        
        safe_nickname = urllib.parse.quote(nickname)
        user_url = f"https://open-api.bser.io/v1/user/nickname?query={safe_nickname}"
        print(f"{user_url}")
        
        async with session.get(user_url) as user_res:
            if user_res.status != 200:
                await ctx.send("API 서버 오류 또는 점검 중입니다.")
                return
            user_data = await user_res.json()
            if user_data.get('code') != 200:
                await ctx.send("존재하지 않는 닉네임입니다.")
                return
            try:
                user_id = user_data['user']['userId']
            except KeyError:
                await ctx.send("유저 정보를 불러올 수 없습니다. (API 구조 변경 가능성)")
                return
            print(user_data) # uid 출력

        # [STEP 2] 전체 전적 데이터 요청하기 
        stats_url = f"https://open-api.bser.io/v2/user/stats/uid/{user_id}/{CURRENT_SEASON}/{matching_mode}"
        print(stats_url)
        
        async with session.get(stats_url) as stats_res:
            if stats_res.status != 200:
                if stats_res.status == 401:
                    await ctx.send(f"401 오류.")
                elif stats_res.status == 403:
                    await ctx.send("API 접근 권한이 없습니다. (403 Forbidden)")
                else:
                    await ctx.send(f"전적을 불러오는 데 실패했습니다. (Error: {stats_res.status})")
                return
            stats_data = await stats_res.json()
            print(stats_data) # {'code': 401, 'message': 'Unauthorized'}
            user_stats = stats_data.get('userStats', [])
            
            # [STEP 3] 스쿼드 모드(matchingTeamMode: 3) & 요청한 게임모드(일반 2, 랭크 3) 정밀 필터링
            overall_stat = next((stat for stat in user_stats 
                                 if stat.get('matchingTeamMode') == 3 and stat.get('matchingMode') == matching_mode), None)
            
            if not overall_stat or overall_stat.get('totalGames', 0) == 0:
                await ctx.send(f"해당 시즌에 '{nickname}' 님이 {mode_name}에서 플레이한 전적이 없습니다.")
                return

            # [STEP 4] 데이터 계산 및 추출
            total_games = overall_stat.get('totalGames', 0)
            # API 버전에 따라 wins 또는 totalWins로 이름이 다를 수 있어 안전장치 추가
            wins = overall_stat.get('totalWins', overall_stat.get('wins', 0)) 
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            mmr = overall_stat.get('mmr', 0)
            rank = overall_stat.get('rank', 0)
            rank_percent = overall_stat.get('rankPercent', 0)
            # 평균값 직접 계산 (총 누적값을 판수로 나눔)
            avg_tk = overall_stat.get('averageTeamKills', overall_stat.get('totalTeamKills', 0) / max(total_games, 1))
            # 모스트(주캐릭터) 찾기: characterStats 중 판수가 가장 높은 실험체 색출
            char_stats = overall_stat.get('characterStats', [])
            if char_stats:
                most_played = max(char_stats, key=lambda x: x.get('totalGames', 0))
                most_char_code = most_played.get('characterCode')
                most_char_name = CHARACTER_MAP.get(most_char_code, "알 수 없음")
            else:
                most_char_name = "기록 없음"
            
            '''
        games_url = f"https://open-api.bser.io/v1/user/games/uid/{user_id}"
        async with session.get(games_url) as games_res:
            if stats_res.status != 200:
                if stats_res.status == 401:
                    await ctx.send(f"401 오류.")
                elif stats_res.status == 403:
                    await ctx.send("🚫 API 접근 권한이 없습니다. (403 Forbidden)")
                else:
                    await ctx.send(f"전적을 불러오는 데 실패했습니다. (Error: {stats_res.status})")
                return
            games_data = await games_res.json()
            '''
            
            # [STEP 5] 결과 임베드 출력
            embed = discord.Embed(
                title=f"📊 {nickname} 님의 {mode_name} 종합 통계", 
                description=f"**주캐릭터:** {most_char_name}",
                color=discord.Color.green() if mode_name == "일반" else discord.Color.purple()
            )
            # 랭크 게임일 때만 RP(MMR) 점수 필드 추가
            if mode_name == "랭크":
                embed.add_field(name="랭크 점수(RP)", value=f"**{mmr}** RP", inline=False)
                embed.add_field(name="랭크 등수", value=f"**{rank}**위 (상위 {int(rank_percent*100)}%)", inline=False)
            embed.add_field(name="판수", value=f"**{total_games}**판", inline=True)
            embed.add_field(name="승률", value=f"**{win_rate:.1f}**%", inline=True)
            embed.add_field(name="평균 TK", value=f"**{avg_tk:.1f}**", inline=True)
            await ctx.send(embed=embed)

bot.run(TOKEN)