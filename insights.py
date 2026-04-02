import re


def generate_insights(spending_by_category: list, monthly_data: list, summary_stats: dict, client) -> str:
    """
    Generate personalized financial insights using Claude Sonnet.
    Returns an HTML string with bullet points.
    """
    total_income = summary_stats.get('total_income', 0)
    total_expense = summary_stats.get('total_expense', 0)
    net_savings = summary_stats.get('net_savings', 0)
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0

    # Build top categories text
    top_cats = spending_by_category[:5]
    top_cats_text = '\n'.join(
        f"  - {c['category']}: ${c['total']:,.2f}" for c in top_cats
    )

    # Build last 6 months trend
    recent_months = monthly_data[-6:] if len(monthly_data) >= 6 else monthly_data
    monthly_text = '\n'.join(
        f"  - {m['month']}: Income ${m['total_income']:,.2f}, Expenses ${m['total_expense']:,.2f}"
        for m in recent_months
    )

    prompt = f"""You are a knowledgeable personal finance advisor. Analyze the following financial data and provide 5-7 personalized, actionable insights and savings tips.

FINANCIAL SUMMARY:
- Total Income: ${total_income:,.2f}
- Total Expenses: ${total_expense:,.2f}
- Net Savings: ${net_savings:,.2f}
- Savings Rate: {savings_rate:.1f}%

TOP SPENDING CATEGORIES:
{top_cats_text if top_cats_text else '  No expense data available'}

MONTHLY TREND (last 6 months):
{monthly_text if monthly_text else '  No monthly data available'}

Please provide 5-7 specific, actionable insights based on this data. Format your response as HTML — use <ul> with <li> tags for each insight. Each insight should:
1. Identify a specific pattern or issue
2. Give a concrete, practical recommendation
3. Where possible, mention specific dollar amounts or percentages

Make the advice practical and motivating. Do not include any text outside the HTML list."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()

        # Ensure we have valid HTML — if the model returned plain text, wrap it
        if not raw.startswith('<'):
            lines = [line.strip() for line in raw.split('\n') if line.strip()]
            items = ''.join(f'<li>{line}</li>' for line in lines)
            raw = f'<ul>{items}</ul>'

        return raw
    except Exception as e:
        return (
            f'<ul>'
            f'<li>Unable to generate insights at this time. Error: {str(e)}</li>'
            f'<li>Please check your Anthropic API key and try again.</li>'
            f'</ul>'
        )
