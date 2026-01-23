# ai_manager.py
# V20.0 - New: 针对“纪要草稿”的 AI 总结引擎
import requests
import json
import config

def generate_summary(user_notes, context_text=""):
    """
    基于用户的纪要草稿 + 原始背景，生成最终总结
    """
    if not user_notes or len(user_notes) < 5:
        return "请先在上方输入一些会议纪要或待办事项，再让 AI 帮您总结。"

    url = f"{config.AI_CONFIG['api_url']}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.AI_CONFIG['api_key']}" 
    }

    # 🔥🔥🔥 核心：针对“讨论要点”和“待办”的定制 Prompt
    prompt = f"""
    你是一名资深的会议纪要整理专员。用户提供了一份会议的“草稿笔记”，其中可能包含：
    1. 讨论要点 (Discussion Points)
    2. 待办事项 (Action Items，通常用 [ ] 标记)
    
    请结合会议背景信息，将这份草稿整理成一段结构清晰、语言简练的【会议总结】。
    
    【会议背景】：
    {context_text[:500]}
    
    【用户草稿】：
    {user_notes[:2000]}
    
    【输出要求】：
    1. 生成一个“会议总结”段落，概括核心结论。
    2. 如果有待办事项，请单独列出并优化措辞，使其更具执行力。
    3. 语气专业、客观。不要包含“根据草稿...”等废话，直接输出结果。
    """

    data = {
        "model": config.AI_CONFIG['model'],
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['choices'][0]['message']['content']
        else:
            return f"AI 请求失败: {response.status_code} - {response.text}"
    except Exception as e:
        return f"AI 连接错误: {str(e)}"