from jinja2 import Template
import pandas as pd

# 기업 정보 DataFrame
company_df = pd.DataFrame({
    'ticker': ['NVDA'],
    'company_name': ['NVIDIA'],
    'summary': ['Nvidia is a leader in GPU and AI processors.']
})

# selected_news 리스트
selected_news = [
    {
        'entities': ['나스닥 100 지수', 'NVIDIA'],
        'related_metrics': ['NVDA', '^NDX'],
        'summary': "Nvidia's market valuation surpassed $4 trillion for the first time...",
        'title': "Nvidia's market value tops $4 trillion",
        'url': 'https://finance.yahoo.com/news/nvidia-notches-4-trillion-record-201014422.html'
    },
    {
        'entities': ['NVIDIA', 'AMD'],
        'related_metrics': ['NVDA', 'AMD'],
        'summary': 'Nvidia Corp. and AMD have secured crucial US government assurances...',
        'title': 'Nvidia’s Huang Wins China Reprieve in Trade War Reversal',
        'url': 'https://finance.yahoo.com/news/nvidia-huang-wins-china-reprieve-185711731.html'
    },
    {
        'entities': ['NVIDIA'],
        'related_metrics': ['NVDA'],
        'summary': "Nvidia's commanding lead in the GPU market positions it to benefit...",
        'title': 'Should You Invest $10,000 in Nvidia Stock Right Now?',
        'url': 'https://finance.yahoo.com/news/invest-10-000-nvidia-stock-093000057.html'
    }
]

# HTML 템플릿 로드
with open("template.html", "r", encoding="utf-8") as f:
    html_template = f.read()

# 템플릿 렌더링
template = Template(html_template)
html_output = template.render(
    company_name=company_df.iloc[0]['company_name'],
    ticker=company_df.iloc[0]['ticker'],
    summary=company_df.iloc[0]['summary'],
    selected_news=selected_news
)

# 결과 저장
with open("nvidia_report.html", "w", encoding="utf-8") as f:
    f.write(html_output)
