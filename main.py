import os
import json
import httpx
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

print("=== QuickReview App Starting ===")

load_dotenv()

app = FastAPI(title="QuickReview AI", description="数码产品评测分析助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
API_BASE = "https://api.siliconflow.cn/v1"
MODEL = "moonshotai/Kimi-K2.6"

SYSTEM_PROMPT = """你是一个专业的数码产品评测分析专家。你的任务是：

1. 根据用户提供的产品型号或链接，搜索并分析全网深度评测内容
2. 总结该产品的优缺点清单
3. 针对不同使用场景给出具体的购买建议

请严格按照以下 JSON 格式返回结果，不要输出任何其他内容：

{
  "product_name": "产品完整名称",
  "price_range": "价格区间",
  "summary": "一句话总结",
  "pros": [
    {"title": "优点标题", "detail": "详细说明"}
  ],
  "cons": [
    {"title": "缺点标题", "detail": "详细说明"}
  ],
  "scenarios": [
    {
      "name": "场景名称（如：学生党、程序员、摄影爱好者）",
      "recommendation": "是否推荐",
      "reason": "推荐理由或不推荐理由",
      "tips": "使用建议或注意事项"
    }
  ],
  "verdict": "最终购买建议总结"
}

如果无法获取到足够信息，请基于你的知识给出最佳分析，并在 summary 中说明信息局限性。"""


class AnalyzeRequest(BaseModel):
    query: str
    api_key: Optional[str] = None


@app.post("/api/analyze")
async def analyze_product(req: AnalyzeRequest):
    api_key = req.api_key or API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="请提供 SiliconFlow API Key（可在页面设置中填写，或配置环境变量 SILICONFLOW_API_KEY）",
        )

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="请输入产品型号或链接")

    user_prompt = f"""请分析以下数码产品：

产品型号/链接：{req.query}

请搜索该产品的专业评测（包括视频评测、文章评测等），综合分析后给出详细的优缺点清单和购买建议。"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "max_tokens": 4096,
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"API 调用失败: {response.text}",
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # 尝试解析 JSON（处理可能的 markdown 代码块包裹）
            content = content.strip()
            if content.startswith("```"):
                # 移除 ```json 和 ```
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            try:
                result = json.loads(content)
                return {"success": True, "data": result}
            except json.JSONDecodeError:
                # 如果 JSON 解析失败，返回原始文本让前端处理
                return {"success": True, "data": {"raw": content}}

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求超时，AI 分析耗时过长，请重试")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"网络请求失败: {str(e)}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/prices")
async def get_prices(product: str):
    """Scrape JD and Taobao for current product prices"""
    from urllib.parse import quote as url_quote
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    result = {"jd": [], "taobao": [], "pdd": []}

    # Scrape JD
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            url = f"https://search.jd.com/Search?keyword={url_quote(product)}&enc=utf-8"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")
                for item in soup.select("li.gl-item")[:6]:
                    name_el = item.select_one(".p-name a")
                    price_el = item.select_one(".p-price strong")
                    if name_el and price_el:
                        href = name_el.get("href", "")
                        if href.startswith("//"):
                            href = "https:" + href
                        result["jd"].append({
                            "name": name_el.get_text(strip=True)[:80],
                            "price": price_el.get_text(strip=True),
                            "url": href,
                        })
    except Exception as e:
        print(f"JD scrape error: {e}")

    # Scrape Taobao (best effort)
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            url = f"https://s.taobao.com/search?q={url_quote(product)}"
            resp = await client.get(url, headers={
                **headers,
                "Cookie": "lgc=1; thw=cn",
                "Referer": "https://www.taobao.com/",
            })
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")
                for item in soup.select("[data-index]"):
                    price_el = item.select_one(".price")
                    name_el = item.select_one(".title a")
                    link_el = item.select_one("a[href*='item.taobao.com']")
                    if price_el and name_el:
                        result["taobao"].append({
                            "name": name_el.get_text(strip=True)[:80],
                            "price": price_el.get_text(strip=True).split()[0] if price_el.get_text(strip=True) else "",
                            "url": "https:" + link_el.get("href", "") if link_el else "",
                        })
    except Exception as e:
        print(f"Taobao scrape error: {e}")

    return result


@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html on the root path"""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    if os.path.exists(frontend_path):
        with open(frontend_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # Fallback if frontend is not found (e.g. deployed in a different structure)
    return HTMLResponse(
        content="<h1>QuickReview API is running.</h1><p>Frontend files not found. Please deploy frontend separately or check file structure.</p>",
        status_code=200
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
