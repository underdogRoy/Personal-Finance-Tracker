# Personal-Finance-Tracker

A web app that ingests transaction data, uses an LLM for intelligent categorization, and analyzes spending patterns to deliver personalized savings recommendations.

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API key (optional)

AI-powered categorization and insights require a Google API key. Get one free at [Google AI Studio](https://aistudio.google.com/app/apikey).

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=your_key_here
```

The app works without an API key using rule-based categorization.

### 3. Run the app

```bash
python app.py
```

Visit **http://localhost:5000** in your browser.

The 1,500-row sample dataset (`Personal_Finance_Dataset.csv`) loads automatically on first launch.

## Features

- **Dashboard** — spending summary cards, doughnut chart by category, monthly income vs. expenses bar chart
- **Transactions** — filterable/paginated table, add/delete entries, one-click AI re-categorization
- **Upload** — import your own CSV bank statement or paste CSV text
- **Insights** — AI-generated personalized savings recommendations based on your spending patterns

## CSV Format

For uploading your own transactions, the CSV should have at minimum:

| Column | Required |
|--------|----------|
| Date | Yes |
| Transaction Description | Yes |
| Amount | Yes |
| Type | No (defaults to Expense) |
| Category | No (auto-categorized if missing) |
