import json
import re

try:
    import anthropic as _anthropic_module
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

CATEGORIES = [
    'Food & Drink', 'Utilities', 'Rent', 'Entertainment', 'Health & Fitness',
    'Shopping', 'Travel', 'Investment', 'Salary', 'Other'
]

KEYWORD_RULES = {
    'Food & Drink': [
        'restaurant', 'food', 'cafe', 'coffee', 'starbucks', 'mcdonald', 'pizza',
        'burger', 'grocery', 'eating', 'dining', 'bakery', 'sushi', 'taco', 'deli',
        'bar', 'pub', 'sandwich', 'breakfast', 'lunch', 'dinner', 'meal'
    ],
    'Utilities': [
        'electric', 'water', 'gas', 'internet', 'phone', 'utility', 'utilities',
        'bill', 'cable', 'telecom', 'broadband', 'wifi', 'wireless', 'mobile', 'cell'
    ],
    'Rent': [
        'rent', 'lease', 'housing', 'apartment', 'mortgage', 'landlord', 'tenant', 'condo'
    ],
    'Entertainment': [
        'netflix', 'spotify', 'hulu', 'disney', 'movie', 'theatre', 'theater', 'game',
        'gaming', 'concert', 'ticket', 'streaming', 'cinema', 'show', 'comedy', 'music', 'play'
    ],
    'Health & Fitness': [
        'gym', 'doctor', 'pharmacy', 'medical', 'health', 'fitness', 'hospital', 'clinic',
        'dental', 'vision', 'prescription', 'yoga', 'workout', 'wellness', 'therapy'
    ],
    'Shopping': [
        'amazon', 'walmart', 'target', 'shop', 'store', 'purchase', 'retail', 'mall',
        'clothing', 'apparel', 'shoes', 'fashion', 'online', 'ebay', 'etsy'
    ],
    'Travel': [
        'uber', 'lyft', 'airline', 'hotel', 'flight', 'airbnb', 'taxi', 'transport',
        'bus', 'train', 'subway', 'metro', 'car', 'rental', 'parking', 'trip',
        'vacation', 'travel', 'booking'
    ],
    'Investment': [
        'invest', 'stock', 'crypto', 'fund', 'portfolio', 'dividend', 'trading',
        'brokerage', 'retirement', '401k', 'ira', 'etf', 'mutual'
    ],
    'Salary': [
        'salary', 'payroll', 'paycheck', 'wage', 'income', 'earning', 'compensation',
        'bonus', 'commission'
    ],
}


def rule_based_categorize(description: str):
    """Return category string if a keyword matches, else None."""
    lower = description.lower()
    for category, keywords in KEYWORD_RULES.items():
        for kw in keywords:
            if kw in lower:
                return category
    return None


def llm_categorize(description: str, amount: float, transaction_type: str, client) -> str:
    """Use Claude Haiku to categorize a single transaction. Returns category string."""
    categories_str = ', '.join(CATEGORIES)
    prompt = (
        f"Classify the following financial transaction into exactly one of these categories: {categories_str}.\n\n"
        f"Transaction Description: {description}\n"
        f"Amount: ${amount:.2f}\n"
        f"Type: {transaction_type}\n\n"
        f"Respond with only valid JSON in this format: {{\"category\": \"<category name>\"}}\n"
        f"Choose the single most appropriate category. Do not include any other text."
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        # Extract JSON even if there's surrounding text
        match = re.search(r'\{.*?"category"\s*:\s*"([^"]+)".*?\}', raw, re.DOTALL)
        if match:
            category = match.group(1).strip()
            if category in CATEGORIES:
                return category
        # Fallback: try full JSON parse
        data = json.loads(raw)
        category = data.get('category', 'Other')
        return category if category in CATEGORIES else 'Other'
    except Exception:
        return 'Other'


def categorize_transaction(description: str, amount: float, transaction_type: str, client=None):
    """
    Two-phase categorization.
    Returns (category: str, is_llm_used: bool)
    """
    category = rule_based_categorize(description)
    if category is not None:
        return category, False

    if client is not None:
        category = llm_categorize(description, amount, transaction_type, client)
        return category, True

    return 'Other', False


def batch_categorize_with_llm(transactions: list, client) -> list:
    """
    Batch categorize up to 20 transactions at a time with a single LLM call.
    Each item in transactions should be a dict with keys: id, description, amount, type.
    Returns list of {id, category} dicts.
    """
    results = []
    categories_str = ', '.join(CATEGORIES)

    for i in range(0, len(transactions), 20):
        batch = transactions[i:i + 20]
        lines = []
        for t in batch:
            lines.append(
                f"ID {t['id']}: \"{t['description']}\" | ${float(t['amount']):.2f} | {t['type']}"
            )
        transactions_text = '\n'.join(lines)

        prompt = (
            f"Classify each of the following financial transactions into exactly one of these categories:\n"
            f"{categories_str}\n\n"
            f"Transactions:\n{transactions_text}\n\n"
            f"Respond with only valid JSON — an array of objects with 'id' and 'category' keys, "
            f"one per transaction, in the same order. Example:\n"
            f'[{{"id": 1, "category": "Food & Drink"}}, {{"id": 2, "category": "Salary"}}]\n'
            f"Do not include any other text."
        )

        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = message.content[0].text.strip()
            # Extract JSON array
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                raw = match.group(0)
            data = json.loads(raw)
            for item in data:
                cat = item.get('category', 'Other')
                results.append({
                    'id': item['id'],
                    'category': cat if cat in CATEGORIES else 'Other'
                })
        except Exception:
            # Fall back: assign 'Other' for all in batch
            for t in batch:
                results.append({'id': t['id'], 'category': 'Other'})

    return results
