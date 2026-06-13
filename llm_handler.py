import google.generativeai as genai
import os
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPTS
import re

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# 모델 인스턴스를 미리 생성해두면 함수 호출 시 매번 생성하지 않아도 되어 효율적입니다.
# (선택 사항: 만약 SYSTEM_PROMPTS가 동적으로 바뀐다면 기존처럼 함수 내부에 두셔도 됩니다.)
try:
    analyzer_model = genai.GenerativeModel(
        'gemini-3.5-flash',
        system_instruction=SYSTEM_PROMPTS["analyzer"]
    )
    qa_model = genai.GenerativeModel(
        'gemini-3.5-flash',
        system_instruction=SYSTEM_PROMPTS["qa"]
    )
except KeyError as e:
    print(f"⚠️ SYSTEM_PROMPTS 키를 찾을 수 없습니다: {e}")


async def analyze_player_stats(nickname: str, stats_data: dict) -> str:
    """
    Google Gemini API를 사용하여 플레이어 통계를 분석하고 인사이트를 제공합니다.
    """
    try:
        # 통계 데이터를 포맷팅
        stats_summary = f"""
플레이어: {nickname}
판수: {stats_data.get('total_games', 0)}
승률: {stats_data.get('win_rate', 0):.1f}%
MMR: {stats_data.get('mmr', 0)}
랭크: {stats_data.get('rank', 0)}위
평균 팀 킬: {stats_data.get('avg_tk', 0):.1f}
주캐릭터: {stats_data.get('main_character', '미정')}
"""
        
        prompt = f"""
다음은 게임 플레이어의 통계 데이터입니다:
{stats_summary}

이 데이터를 분석하여 플레이어의 강점, 약점, 그리고 개선 방안을 설명해주세요.
"""
        
        # 💡 핵심 수정: 비동기 환경에 맞게 generate_content_async와 await를 사용합니다.
        response = await analyzer_model.generate_content_async(prompt)
        
        # response와 response.text가 무사히 비어있지 않은지 검증
        if response and hasattr(response, 'text') and response.text:
            return response.text
        return "분석을 생성할 수 없습니다."
    
    except Exception as e:
        error_msg = str(e)
        
        # 429 에러(할당량 초과) 발생 시 처리
        if "429" in error_msg or "Quota exceeded" in error_msg:
            # 에러 메시지에서 "Please retry in 48.325s" 형태의 숫자를 찾아냅니다.
            match = re.search(r"retry in ([\d\.]+)[ss]?", error_msg)
            
            if match:
                # 소수점을 반올림하여 정수(예: 48)로 만듭니다.
                seconds = round(float(match.group(1)))
                return f"개발자는 거지입니다. 추후 더 나은 API 플랜을 구독할 것이니 지금은 **{seconds}초** 후에 다시 사용해주세요."
            else:
                # 혹시 시간을 못 찾을 경우를 대비한 기본 문구
                return "개발자는 거지입니다. 추후 더 나은 API 플랜을 구독할 것이니 지금은 잠시 후에 다시 사용해주세요."
                
        # 429 외의 다른 에러는 기존처럼 출력
        return f"❌ 오류 발생: {error_msg}"


async def answer_game_question(question: str, context: str = "") -> str:
    """
    Google Gemini API를 사용하여 게임 관련 질문에 답변합니다.
    """
    try:
        prompt = f"""
사용자가 이터널 리턴 게임에 대해 물어봤습니다:
질문: {question}

{f'추가 정보: {context}' if context else ''}

게임의 메타나 플레이 팁을 고려하여 답변해주세요.
"""
        
        # 💡 핵심 수정: 비동기 환경에 맞게 generate_content_async와 await를 사용합니다.
        response = await qa_model.generate_content_async(prompt)
        
        if response and hasattr(response, 'text') and response.text:
            return response.text
        return "답변을 생성할 수 없습니다."
    
    except Exception as e:
        error_msg = str(e)
        
        # 429 에러(할당량 초과) 발생 시 처리
        if "429" in error_msg or "Quota exceeded" in error_msg:
            # 에러 메시지에서 "Please retry in 48.325s" 형태의 숫자를 찾아냅니다.
            match = re.search(r"retry in ([\d\.]+)[ss]?", error_msg)
            
            if match:
                # 소수점을 반올림하여 정수(예: 48)로 만듭니다.
                seconds = round(float(match.group(1)))
                return f"개발자는 거지입니다. 추후 더 나은 API 플랜을 구독할 것이니 지금은 **{seconds}초** 후에 다시 사용해주세요."
            else:
                # 혹시 시간을 못 찾을 경우를 대비한 기본 문구
                return "개발자는 거지입니다. 추후 더 나은 API 플랜을 구독할 것이니 지금은 잠시 후에 다시 사용해주세요."
                
        # 429 외의 다른 에러는 기존처럼 출력
        return f"❌ 오류 발생: {error_msg}"