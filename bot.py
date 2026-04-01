import discord
from discord.ext import commands, tasks
import aiohttp
import random
import os
from dotenv import load_dotenv
import urllib.parse
import asyncio

# --- 1. 환경변수 및 기본 설정 ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ER_API_KEY = os.getenv('ER_API_KEY')

ER_API_HEADERS = {
    "accept": "application/json",
    "x-api-key": ER_API_KEY
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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

CHARACTER_MAP = {}
ITEM_NAME_MAP = {} # 아이템 이름 -> 아이템 코드 
ITEM_DATA_MAP = {} # 아이템 코드 -> 스탯 데이터 저장소
CURRENT_SEASON = 37

# --- 3. 백그라운드 작업 및 초기 설정 ---
@tasks.loop(minutes=10)
async def change_status():
    new_status = random.choice(STATUS_LIST)
    await bot.change_presence(activity=discord.Game(name=new_status))

async def load_meta_data():
    global CHARACTER_MAP, ITEM_NAME_MAP, ITEM_DATA_MAP
    CHARACTER_MAP.clear()
    ITEM_NAME_MAP.clear()
    ITEM_DATA_MAP.clear()
    
    l10n_url = "https://open-api.bser.io/v1/l10n/Korean"

    async with aiohttp.ClientSession(headers=ER_API_HEADERS) as session:
        # 1. 언어팩(L10n) 파싱
        async with session.get(l10n_url) as res:
            if res.status == 200:
                data = await res.json()
                download_link = data['data']['l10Path']
                
                async with session.get(download_link) as text_res:
                    text_data = await text_res.text(encoding='utf-8')
                    
                    for line in text_data.splitlines():
                        if "┃" not in line:
                            continue
                            
                        key_part, name = line.split('┃', 1)
                        name = name.strip()
                        code_str = key_part.split('/')[-1]
                        
                        if not code_str.isdigit():
                            continue
                            
                        if key_part.startswith("Character/Name/"):
                            CHARACTER_MAP[int(code_str)] = name
                        elif key_part.startswith("Item/Name/"):
                            ITEM_NAME_MAP[name] = int(code_str)

        # 소모품(ItemConsumable)을 빼고 무기와 방어구만 남겼습니다.
        meta_types = ["Item", "ItemWeapon", "ItemArmor"]
        
        # 다운로드를 수행하는 미니 함수
        async def fetch_meta(m_type):
            url = f"https://open-api.bser.io/v2/data/{m_type}"
            async with session.get(url) as res:
                if res.status == 200:
                    return await res.json()
                return None

        # asyncio.gather를 사용해 3개의 API를 "동시에" 쏴서 시간을 확 단축시킵니다!
        results = await asyncio.gather(*(fetch_meta(m) for m in meta_types))
        
        for data in results:
            if data:
                for item in data.get('data', []):
                    code = item.get('code') or item.get('itemCode')
                    if code:
                        code = int(code)
                        if code not in ITEM_DATA_MAP:
                            ITEM_DATA_MAP[code] = item
                        else:
                            ITEM_DATA_MAP[code].update(item)
    print(f"✅ 메타데이터 로드 완료! (캐릭터 {len(CHARACTER_MAP)}명 / 아이템 {len(ITEM_NAME_MAP)}개)")
    print(ITEM_DATA_MAP)

@bot.event
async def on_ready():
    print(f'로그인 진행 중...')    
    await load_meta_data()
    change_status.start()
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
async def er_stats_overall(ctx, *, nickname=None):
    # 1. 입력값 검증 (!전적 닉네임)
    if not nickname:
        await ctx.send("명령어 형식이 틀렸습니다! `!전적 닉네임` 형태로 입력해주세요.\n예시: `!전적 조규식`")
        return
    
    nickname = nickname.strip()
    matching_mode = 3 # 랭크 게임 모드 코드 고정

    async with aiohttp.ClientSession(headers=ER_API_HEADERS) as session:        
        safe_nickname = urllib.parse.quote(nickname)
        user_url = f"https://open-api.bser.io/v1/user/nickname?query={safe_nickname}"
        
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

        # [STEP 2] 전체 전적 데이터 요청하기 
        stats_url = f"https://open-api.bser.io/v2/user/stats/uid/{user_id}/{CURRENT_SEASON}/{matching_mode}"
        
        async with session.get(stats_url) as stats_res:
            if stats_res.status != 200:
                if stats_res.status == 401:
                    await ctx.send("401 오류. API 키를 확인해주세요.")
                elif stats_res.status == 403:
                    await ctx.send("API 접근 권한이 없습니다. (403 Forbidden)")
                else:
                    await ctx.send(f"전적을 불러오는 데 실패했습니다. (Error: {stats_res.status})")
                return
            stats_data = await stats_res.json()
            user_stats = stats_data.get('userStats', [])
            
            # [STEP 3] 스쿼드 모드(matchingTeamMode: 3) & 랭크 모드 정밀 필터링
            overall_stat = next((stat for stat in user_stats 
                                 if stat.get('matchingTeamMode') == 3 and stat.get('matchingMode') == matching_mode), None)
            
            if not overall_stat or overall_stat.get('totalGames', 0) == 0:
                await ctx.send(f"해당 시즌에 '{nickname}' 님이 랭크 게임에서 플레이한 전적이 없습니다.")
                return

            # [STEP 4] 데이터 계산 및 추출
            total_games = overall_stat.get('totalGames', 0)
            wins = overall_stat.get('totalWins', overall_stat.get('wins', 0)) 
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            mmr = overall_stat.get('mmr', 0)
            rank = overall_stat.get('rank', 0)
            rank_percent = overall_stat.get('rankPercent', 0)
            avg_tk = overall_stat.get('averageTeamKills', overall_stat.get('totalTeamKills', 0) / max(total_games, 1))
            
            char_stats = overall_stat.get('characterStats', [])
            if char_stats:
                most_played = max(char_stats, key=lambda x: x.get('totalGames', 0))
                most_char_code = most_played.get('characterCode')
                most_char_name = CHARACTER_MAP.get(most_char_code, "알 수 없음")
            else:
                most_char_name = "기록 없음"
            
            # [STEP 5] 랭크 전용 결과 임베드 출력
            embed = discord.Embed(
                title=f"📊 {nickname} 님의 랭크 종합 통계", 
                description=f"**주캐릭터:** {most_char_name}",
                color=discord.Color.purple()
            )
            embed.add_field(name="랭크 점수(RP)", value=f"**{mmr}** RP", inline=False)
            embed.add_field(name="랭크 등수", value=f"**{rank}**위 (상위 {int(rank_percent*100)}%)", inline=False)
            embed.add_field(name="판수", value=f"**{total_games}**판", inline=True)
            embed.add_field(name="승률", value=f"**{win_rate:.1f}**%", inline=True)
            embed.add_field(name="평균 TK", value=f"**{avg_tk:.1f}**", inline=True)
            await ctx.send(embed=embed)

@bot.command(name='아이템')
async def item_stats(ctx, *, item_name=None):
    if not item_name:
        await ctx.send("명령어 형식이 틀렸습니다! `!아이템 장비이름` 형태로 입력해주세요.\n예시: `!아이템 여의봉`")
        return

    item_name = item_name.strip()
    item_code = ITEM_NAME_MAP.get(item_name)
    
    # "성법의" 와 "성 법 의" 같은 띄어쓰기 오타 방지용 재검색
    if not item_code:
        for name, code in ITEM_NAME_MAP.items():
            if name.replace(" ", "") == item_name.replace(" ", ""):
                item_code = code
                item_name = name
                break

    if not item_code or item_code not in ITEM_DATA_MAP:
        await ctx.send(f"'{item_name}'(을)를 찾을 수 없거나 스탯이 존재하지 않습니다. 띄어쓰기를 확인해주세요!")
        return

    item_info = ITEM_DATA_MAP[item_code]
    
    # 1. 등급별 색상 & 한글 매핑
    grade = item_info.get('itemGrade', 'Common')
    color_map = {
        "Common": discord.Color.light_gray(),
        "Uncommon": discord.Color.green(),
        "Rare": discord.Color.blue(),
        "Epic": discord.Color.purple(),
        "Legend": discord.Color.gold(),
        "Mythic": discord.Color.red()
    }
    grade_kor_map = {
        "Common": "일반", "Uncommon": "고급", "Rare": "희귀", 
        "Epic": "영웅", "Legend": "전설", "Mythic": "초월"
    }

    # 2. 유저가 읽기 편하게 영문 스탯키를 한글로 변환
    stat_translation = {
        "attackPower": "공격력",
        'attackPowerByLv': "레벨당 공격력", 
        "defense": "방어력",
        'defenseByLv': "레벨당 방어력",
        'skillAmp': "스킬증폭", 
        'skillAmpByLevel': "레벨당 스킬증폭", 
        'skillAmpRatio': "스킬증폭(%)", 
        'adaptiveForce': "적응형 능력치", 
        'adaptiveForceByLevel': "레벨당 적응형 능력치", 
        "maxHp": "최대 체력",
        'maxHpByLv': "레벨당 최대 체력", 
        "hpRegen": "체력 재생",
        "attackSpeedRatio": "공격 속도",
        'attackSpeedRatioByLv': "레벨당 공격 속도",
        "criticalStrikeChance": "치명타 확률",
        "criticalStrikeDamage": "치명타 피해량",
        "preventCriticalStrikeDamaged": "치명타 피해 감소",
        "coolDownReduction": "쿨다운 감소",
        "lifeSteal": "모든 피해 흡혈",
        "normalLifeSteal": "기본 공격 흡혈",
        "skillLifeSteal": "스킬 피해 흡혈",
        "sightRange": "시야범위",
        'attackRange': "기본공격 사거리",
        'penetrationDefense': "방어력 관통", 
        'penetrationDefenseRatio': "방어력 관통(%)",  
        'slowResistRatio': "둔화 효과 저항",
        'hpHealedIncreaseRatio': "치유 증가",
        'healerGiveHpHealRatio': "치유 증가?",
        'tacticalCooldownReduction': "전술스킬 쿨다운 감소",
        "moveSpeed": "이동 속도",
    }

    # 3. 데이터가 0이 아닌 스탯만 쏙쏙 뽑아내기
    stats_text = ""
    for stat_key, stat_kor in stat_translation.items():
        val = item_info.get(stat_key, 0)
        if val != 0:
            # 소수점 데이터(예: 0.15)가 무한정 길어지는 걸 방지
            if isinstance(val, float):
                stats_text += f"**{stat_kor}**: {val:g}\n"
            else:
                stats_text += f"**{stat_kor}**: {val}\n"

    if not stats_text:
        stats_text = "스탯이 존재하지 않는 재료 또는 소모품입니다."

    # 4. 결과 출력
    embed = discord.Embed(
        title=f"🔎 {item_name}", 
        description=f"**등급**: {grade_kor_map.get(grade, grade)}",
        color=color_map.get(grade, discord.Color.default())
    )
    
    embed.add_field(name="기본 스탯", value=stats_text, inline=False)
    await ctx.send(embed=embed)


bot.run(TOKEN)