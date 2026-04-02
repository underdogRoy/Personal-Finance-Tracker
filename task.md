Personal Finance Tracker with Insights
Description: Automatically categorizes your spending from transaction descriptions and provides personalized insights to help you save money.

Implementation:

Upload bank statements or manually enter transactions
Use LLM to categorize each transaction (food, transport, entertainment, etc.)
Analyze spending patterns over time
Generate personalized savings recommendations
Create visualizations showing where money goes
Input/Output:

Input: Transaction descriptions or CSV bank statements
Output: Categorized expenses, spending trends, and saving tips
Use Cases:

Students managing limited budgets
People trying to save for specific goals
Anyone wanting to understand their spending habits
APIs/Libraries Needed:

Free LLM for categorization and insights
Chart.js or Matplotlib for visualizations
CSV parser for bank statements
Simple database for storing history
Web framework for interface
Data Summary:
We will use the "Personal Finance Data" dataset by Ramya Pintchy (Kaggle), which contains
synthetic personal finance records spanning from January 2020 to December 2024. Key columns
include Date, Transaction Description, Category (e.g., Food & Drink, Rent), Amount, and Type
(Income vs. Expense). Our LLM pipeline will use Transaction Description, Amount, and Type as raw
inputs. Crucially, we will mask the dataset's existing Category column during processing to serve as
the "ground truth" for objectively evaluating our LLM's classification accuracy.
Methods:
The application will be built using a lightweight web framework like Flask. Our pipeline includes:
1. Data Ingestion: A Python script using pandas will clean, format, and batch the CSV data.
2. Categorization Engine: We will prompt an LLM API (e.g., Claude, via NEU access) to map
unstructured transaction descriptions to our predefined financial categories, enforcing a
structured JSON output.
3. Visualization & Storage: Categorized data will be saved to a SQLite database and visualized
via [Matplotlib / Streamlit charts] to display spending trends over time.
4. Insight Generation: A secondary LLM prompt will analyze aggregated monthly data to flag
spending anomalies and suggest practical saving tips.
Challenges include engineering robust prompts to prevent LLM hallucinations, reliably parsing
ambiguous transaction text, and managing API rate limits during development.
Grading Criteria
Your project will be evaluated on:

Functionality: Does it work as intended?
Creativity: Did you add unique features or improvements?
Use Cases: Is it useful? Does it solve real problems?
Expand the idea: The project descriptions are starting points only. You are strongly encouraged to add your own features, improve the user experience, or combine ideas to make something better.
1. Using only synthetic data means you don't know if it works on real transactions. Real bank statements have messy, abbreviated descriptions like "POS DEBIT 7-11 #3324" or "VENMO *JOHN D." The synthetic dataset likely has clean, readable text, so your LLM accuracy numbers won't reflect real-world performance.

Suggestion: Test a small batch (even 50–100 rows) of real or realistic transaction descriptions alongside the synthetic data. You could anonymize your own bank exports or find sample raw bank CSVs online to see how the LLM handles messy inputs.

2. Sending every transaction to an LLM API is slow and expensive at scale. If someone uploads a year of transactions (hundreds or thousands of rows), calling the API one-by-one will be painfully slow, and batching has token limits. The proposal doesn't address how this scales.

Suggestion: Add a simple rule-based or keyword classifier as a first pass (e.g., "Starbucks" → Food & Drink) and only send ambiguous transactions to the LLM. This cuts API costs, speeds things up, and still uses the LLM where it actually adds value.